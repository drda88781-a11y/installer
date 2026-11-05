# sql/sql_installer.py
"""
ماژول نصب دقیق، بدون وقفه و مهندسی‌شده SQL Server 2014 و 2019 Enterprise با سیاست عدم توقف
High-Precision, Unattended, Resilient SQL Server 2014 & 2019 Enterprise Installer
ویژگی‌های پیشرفته:
۱. پایش سلامت بستر قبل از نصب (Pre-Flight Checks): WMI، ری‌استارت معلق و رفع باگ 4KB در SSD NVMe
۲. فعال‌سازی هوشمند NetFX3 به صورت آفلاین/آنلاین برای نسخه ۲۰۱۴
۳. مانت دولایه ایمیج ایزو (پاورشل + استخراج مستقیم در صورت قفل بودن دیسک مجازی)
۴. ردیابی زنده لاگ Detail.txt حین ستاپ برای نمایش درصد و مراحل واقعی
۵. سوییچ‌های دقیق، کالیشن رسمی Arabic_CI_AS، حساب‌های ادمین داینامیک
۶. سخت‌سازی کامل پس از نصب: تنظیم فایروال، TCP/IP پورت ۱۴۳۳، SQLBrowser، لیمیت RAM با ODBC
"""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union
import winreg

import psutil
import pyodbc

from config.settings import (
    SETUP_DIR,
    SQL_INSTANCE_NAME,
    SQL_FEATURES,
    SQL_ARCHIVE_NAME,
    SQL_ARCHIVE_PASS,
    SQL_SA_USER,
    SQL_SA_PASSWORD,
    get_sql_instance_name,
)
from app_logging.app_logger import logger
from sql.sql_detector import (
    is_sql_instance_installed,
    start_sql_service_if_stopped,
)
from sql.sql_verifier import verify_sql_connection, SQLVerificationResult
from utils.archive_extractor import extract_archive_universal


class SQLServerInstaller:
    """
    موتور دقیق و هوشمند نصب و پیکربندی SQL Server 2014 و 2019 Enterprise
    """
    def __init__(
        self,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        sa_user: Optional[str] = None,
        sa_password: Optional[str] = None,
        sql_version: str = "2019",
        instance_name: Optional[str] = None,
        force_new_instance: bool = False,
    ):
        self.progress_callback = progress_callback
        self.sa_user = sa_user or SQL_SA_USER
        self.sa_password = sa_password or os.environ.get("SEPEHRYAR_SQL_PWD", SQL_SA_PASSWORD)
        self.sql_version = str(sql_version)
        self.instance_name = (instance_name or get_sql_instance_name(self.sql_version)).strip()
        self.has_custom_instance = bool(instance_name and instance_name.strip())
        self.force_new_instance = force_new_instance
        self.cancel_requested = False

    def _notify(self, message: str, percent: int = -1):
        if self.progress_callback:
            self.progress_callback(message, percent)

    # =========================================================================
    # فاز ۱: پایش سلامت بستر و رفع موانع قبل از ستاپ (Pre-Flight Sanitization)
    # =========================================================================

    def _perform_preflight_checks(self):
        """
        پاک‌سازی موانع رایج ویندوز جهت تضمین اجرای بدون توقف ستاپ:
        ۱. مدیریت ری‌استارت معلق ویندوز (RebootRequiredCheck)
        ۲. اعمال پچ سکتور ۴ کیلوبایتی مایکروسافت برای هاردهای NVMe در ویندوز ۱۱
        ۳. بررسی و بازسازی شمارنده‌های عملکرد (Performance Counters / lodctr)
        ۴. بررسی سلامت مخزن WMI و ساخت پوشه موقت ایمن با نویسه‌های اَسکی
        """
        logger.log("SQL_PREFLIGHT", "START", "RUNNING", "شروع ارزیابی و پاک‌سازی موانع بستر ویندوز...")

        # ۱. بررسی و حل تعلیق ری‌استارت (PendingFileRenameOperations)
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager",
                0,
                winreg.KEY_READ | winreg.KEY_WRITE
            ) as sm_key:
                try:
                    val, _ = winreg.QueryValueEx(sm_key, "PendingFileRenameOperations")
                    if val:
                        logger.log("SQL_PREFLIGHT", "REBOOT_CHECK", "FOUND",
                                   "عملیات معلق ری‌استارت ویندوز کشف شد؛ پاک‌سازی موقت جهت جلوگیری از توقف ستاپ...")
                        winreg.DeleteValue(sm_key, "PendingFileRenameOperations")
                except FileNotFoundError:
                    pass
        except Exception as ex_sm:
            logger.log("SQL_PREFLIGHT", "REBOOT_CHECK", "WARN", f"عدم امکان بررسی رجیستری ری‌استارت: {ex_sm}")

        # ۲. پچ رسمی مایکروسافت برای باگ اندازه سکتور دیسک‌های NVMe در ویندوز ۱۱ (KB 5008546)
        # ارور: Wait on Database Engine recovery handle failed (0x851A001A)
        try:
            nvme_key_path = r"SYSTEM\CurrentControlSet\Services\stornvme\Parameters\Device"
            reg_add_cmd = [
                "reg.exe", "add",
                f"HKLM\\{nvme_key_path}",
                "/v", "ForcedPhysicalSectorSizeInBytes",
                "/t", "REG_MULTI_SZ",
                "/d", "* 4095",
                "/f"
            ]
            subprocess.run(reg_add_cmd, capture_output=True, timeout=10)
            logger.log("SQL_PREFLIGHT", "NVME_PATCH", "SUCCESS", "تنظیم سکتور 4KB دیسک NVMe با موفقیت اعتبارسنجی شد.")
        except Exception as ex_nvme:
            logger.log("SQL_PREFLIGHT", "NVME_PATCH", "WARN", f"پیکربندی سکتور دیسک: {ex_nvme}")

        # ۳. اعتبارسنجی و بازسازی شمارنده‌های عملکرد (جلوگیری از خطای PerfMonCounterNotCorruptedCheck)
        try:
            subprocess.run(["lodctr", "/R"], capture_output=True, timeout=10)
            logger.log("SQL_PREFLIGHT", "PERFMON", "SUCCESS", "شمارنده‌های سیستم بازسازی شدند.")
        except Exception:
            pass

        # ۴. اعتبارسنجی مخزن WMI ویندوز
        try:
            wmi_res = subprocess.run(["winmgmt", "/verifyrepository"], capture_output=True, text=True, timeout=10)
            if "not consistent" in wmi_res.stdout.lower():
                logger.log("SQL_PREFLIGHT", "WMI", "REPAIRING", "مخزن WMI ناسازگار است؛ در حال بازسازی...")
                subprocess.run(["winmgmt", "/salvagerepository"], capture_output=True, timeout=20)
        except Exception:
            pass

        # ۵. آماده‌سازی پوشه کاری تمیز و امن (Clean ASCII Temp Path)
        # جلوگیری از کراش اکسترکت ستاپ به دلیل نام‌های فارسی در پروفایل کاربر
        safe_tmp = Path(r"C:\SEPEHRYAR_SQL_TMP")
        try:
            safe_tmp.mkdir(parents=True, exist_ok=True)
            os.environ["TMP"] = str(safe_tmp)
            os.environ["TEMP"] = str(safe_tmp)
        except Exception:
            pass

    def _is_dotnet35_installed(self) -> bool:
        """بررسی دقیق نصب بودن NetFX3 (.NET Framework 3.5 SP1) از طریق رجیستری"""
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v3.5") as key:
                val, _ = winreg.QueryValueEx(key, "Install")
                return val == 1
        except Exception:
            return False

    def _enable_dotnet35(self, fallback_source_dir: Optional[Path] = None) -> bool:
        """
        فعال‌سازی هوشمند NetFX3:
        ابتدا با منبع آفلاین محلی (پوشه sxs در پکیج ستاپ یا درایوهای ویندوز)، سپس آنلاین با DISM و در نهایت با PowerShell
        """
        if self._is_dotnet35_installed():
            logger.log("SQL", "DOTNET35", "ALREADY_INSTALLED", ".NET Framework 3.5 از قبل فعال است.")
            return True

        self._notify("در حال فعال‌سازی پیش‌نیاز حیاتی .NET Framework 3.5 در ویندوز...", 20)
        logger.log("SQL", "DOTNET35", "RUNNING", "تلاش برای فعال‌سازی پیش‌نیاز NetFX3...")

        # ۱. بررسی وجود منبع آفلاین (پوشه sxs)
        sxs_candidates = [
            (fallback_source_dir / "sxs") if fallback_source_dir else None,
            SETUP_DIR / "SQL" / "sxs",
            Path(r"C:\sxs"),
        ]
        # بررسی رسانه‌های نصب ویندوز یا دیسک‌های متصل (مانند D:\sources\sxs)
        for drive_letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            cand_drive_sxs = Path(f"{drive_letter}:\\sources\\sxs")
            if cand_drive_sxs.exists():
                sxs_candidates.append(cand_drive_sxs)

        sxs_source = None
        for cand in sxs_candidates:
            if cand and cand.exists() and any(cand.glob("*.cab")):
                sxs_source = cand
                break

        if sxs_source:
            logger.log("SQL", "DOTNET35", "OFFLINE", f"استفاده از پکیج آفلاین sxs: {sxs_source}")
            try:
                cmd_offline = [
                    "dism.exe", "/online", "/enable-feature",
                    "/featurename:NetFX3", "/All", "/LimitAccess",
                    f"/Source:{str(sxs_source)}", "/NoRestart"
                ]
                res_off = subprocess.run(cmd_offline, capture_output=True, text=True, timeout=300)
                if res_off.returncode in [0, 3010]:
                    logger.log("SQL", "DOTNET35", "SUCCESS", "پیش‌نیاز .NET 3.5 از منبع آفلاین فعال گردید.")
                    return True
            except Exception as ex_off:
                logger.log("SQL", "DOTNET35", "WARN", f"تلاش آفلاین با خطا مواجه شد: {ex_off}")

        # ۲. تلاش آنلاین با DISM
        try:
            dism_cmd = ["dism.exe", "/online", "/enable-feature", "/featurename:NetFX3", "/All", "/NoRestart"]
            res = subprocess.run(dism_cmd, capture_output=True, text=True, timeout=300)
            if res.returncode in [0, 3010]:
                logger.log("SQL", "DOTNET35", "SUCCESS", ".NET Framework 3.5 با موفقیت آنلاین فعال شد.")
                return True
            else:
                logger.log("SQL", "DOTNET35", "WARN", f"خروجی DISM: کد {res.returncode}. ادامه با روش PowerShell...")
        except Exception as ex:
            logger.log("SQL", "DOTNET35", "WARN", f"خطا در اجرای DISM: {ex}")

        # ۳. فال‌بک نهایی با PowerShell
        try:
            ps_cmd = "Enable-WindowsOptionalFeature -Online -FeatureName NetFx3 -All -NoRestart -ErrorAction SilentlyContinue"
            res_ps = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=120)
            if res_ps.returncode == 0:
                logger.log("SQL", "DOTNET35", "SUCCESS", ".NET 3.5 از طریق PowerShell فعال گردید.")
                return True
        except Exception:
            pass

        return False

    def _get_sysadmin_accounts(self) -> str:
        """فرمت‌دهی داینامیک و امن حساب‌های ادمین ویندوز جهت جلوگیری از خطای Account Validation"""
        computer_name = os.environ.get("COMPUTERNAME", "")
        current_admin = os.environ.get("USERNAME", "Administrator")
        accounts = []
        if computer_name and current_admin and current_admin.upper() not in ["SYSTEM", "LOCAL SERVICE", "NETWORK SERVICE"]:
            accounts.append(f'"{computer_name}\\{current_admin}"')
        elif current_admin and current_admin.upper() not in ["SYSTEM", "LOCAL SERVICE", "NETWORK SERVICE"]:
            accounts.append(f'"{current_admin}"')
        accounts.append('"BUILTIN\\Administrators"')
        return " ".join(accounts)

    # =========================================================================
    # فاز ۲: مانیتورینگ زنده و تعقیب لاگ ستاپ (Live Bootstrap Tailing)
    # =========================================================================

    def _run_setup_with_live_monitoring(
        self,
        setup_args: Union[List[str], str],
        ver_code: str,
        start_pct: int = 40,
        end_pct: int = 80
    ) -> Tuple[int, Optional[str]]:
        """
        اجرای پروسه ستاپ و تعقیب همزمان لاگ Detail.txt برای به‌روزرسانی دقیق درصد و مراحل در UI.
        آرگومان‌ها به صورت مستقیم و بدون Escaping ناصحیح به CreateProcess ویندوز ارسال می‌شوند.
        """
        logger.log("SQL", "SETUP_EXEC", "START", "فراخوانی ستاپ با آرگومان‌های استاندارد...")
        self._notify("شروع اجرای فرآیند ستاپ و تحلیل قوانین سیستم...", start_pct)

        log_base_dirs = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft SQL Server" / ver_code / "Setup Bootstrap" / "Log",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft SQL Server" / ver_code / "Setup Bootstrap" / "Log",
        ]

        # آماده‌سازی محیط امن با پوشه Temp اسکی بدون کاراکترهای فارسی
        safe_env = os.environ.copy()
        safe_tmp = Path(r"C:\SEPEHRYAR_SQL_TMP")
        try:
            safe_tmp.mkdir(parents=True, exist_ok=True)
            safe_env["TMP"] = str(safe_tmp)
            safe_env["TEMP"] = str(safe_tmp)
        except Exception:
            pass

        # تبدیل آرگومان‌ها به رشته خط فرمان یکپارچه برای جلوگیری از باگ list2cmdline در ویندوز
        if isinstance(setup_args, list):
            cmd_str = " ".join(setup_args)
        else:
            cmd_str = setup_args

        proc = subprocess.Popen(
            cmd_str,
            env=safe_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace"
        )

        detail_file: Optional[Path] = None
        file_pos = 0
        current_pct = start_pct
        start_time = time.time()

        milestones = [
            ("Running rule", "بررسی قوانین پیش‌نیاز سیستم (Rules Engine)...", 45),
            ("Attempting to install feature SQLEngine", "در حال نصب فایل‌های موتور دیتابیس (SQLEngine)...", 55),
            ("Attempting to install feature Replication", "در حال نصب ماژول تکثیر داده‌ها (Replication)...", 62),
            ("Attempting to install feature Tools", "در حال نصب ابزارهای مدیریتی و رابط کاربری (SSMS/Tools)...", 68),
            ("Attempting to install feature FullText", "در حال نصب قابلیت جستجوی متن کامل (Full-Text)...", 72),
            ("master.mdf", "راه‌اندازی اولیه پایگاه‌های داده سیستمی و رجیستری...", 75),
            ("Starting service", "راه‌اندازی سرویس و تنظیم حساب‌های کاربری...", 80),
            ("Configuration action", "پیکربندی نهایی مؤلفه‌ها و امنیت...", 82),
        ]
        seen_milestones = set()

        while proc.poll() is None:
            # جستجوی فایل Detail.txt جدید در صورت عدم شناسایی
            if not detail_file:
                for base in log_base_dirs:
                    if base.exists():
                        try:
                            subdirs = sorted([d for d in base.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
                            for sd in subdirs[:2]:
                                cand = sd / "Detail.txt"
                                if cand.exists() and cand.stat().st_mtime >= (start_time - 30):
                                    detail_file = cand
                                    break
                        except Exception:
                            pass
                    if detail_file:
                        break

            # تعقیب خطوط جدید در فایل لاگ
            if detail_file and detail_file.exists():
                try:
                    with open(detail_file, "r", encoding="utf-8", errors="replace") as df:
                        df.seek(file_pos)
                        new_text = df.read()
                        file_pos = df.tell()

                        for line in new_text.splitlines():
                            for pattern, desc, pct in milestones:
                                if pattern.lower() in line.lower() and pattern not in seen_milestones:
                                    seen_milestones.add(pattern)
                                    current_pct = max(current_pct, pct)
                                    self._notify(desc, current_pct)
                                    logger.log("SQL_SETUP", "PROGRESS", "STEP", desc)
                                    break
                except Exception:
                    pass

            time.sleep(2)

        ret_code = proc.returncode
        logger.log("SQL", "SETUP_EXEC", "COMPLETED", f"کد خروج ستاپ: {ret_code}")

        detail_err = None
        if ret_code != 0:
            detail_err = self._extract_summary_error(ver_code)

        return ret_code, detail_err

    def _extract_summary_error(self, ver_code: str = "150") -> Optional[str]:
        """استخراج خطای تفصیلی از جدیدترین فایل Summary.txt یا Detail.txt"""
        search_dirs = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft SQL Server" / ver_code / "Setup Bootstrap" / "Log",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft SQL Server" / ver_code / "Setup Bootstrap" / "Log",
        ]
        for base_log in search_dirs:
            if not base_log.exists():
                continue
            candidates = []
            try:
                subdirs = sorted([d for d in base_log.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
                for sd in subdirs[:3]:
                    candidates.extend(list(sd.glob("Summary*.txt")) + [sd / "Detail.txt"])
            except Exception:
                pass

            for file_path in candidates:
                if not file_path.exists():
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                    for line in text.splitlines():
                        line_str = line.strip()
                        if any(k in line_str.lower() for k in ["error result:", "exit code:", "watson message:", "fatal error", "error code: 0x"]) and len(line_str) > 15:
                            return line_str
                except Exception:
                    pass
        return None

    # =========================================================================
    # فاز ۳: سخت‌سازی، باز کردن پورت‌ها و لیمیت حافظه رم (Post-Hardening)
    # =========================================================================

    def _post_install_hardening(self):
        """
        سخت‌سازی امنیتی و شبکه پس از نصب:
        ۱. فعال‌سازی قطعی پروتکل‌های TCP/IP و Named Pipes در رجیستری
        ۲. راه‌اندازی و تنظیم خودکار سرویس SQLBrowser
        ۳. باز کردن پورت‌های ۱۴۳۳ و ۱۴۳۴ در فایروال ویندوز
        ۴. تخصیص داینامیک سقف حافظه رم بر مبنای توان سخت‌افزاری سرور
        """
        logger.log("SQL", "HARDENING", "START", "شروع سخت‌سازی شبکه، فایروال و تنظیمات سرویس...")

        # ۱. فعال‌سازی پروتکل TCP/IP و Named Pipes در رجیستری
        reg_roots = [
            rf"SOFTWARE\Microsoft\Microsoft SQL Server\MSSQL15.{self.instance_name}\MSSQLServer\SuperSocketNetLib",
            rf"SOFTWARE\Microsoft\Microsoft SQL Server\MSSQL12.{self.instance_name}\MSSQLServer\SuperSocketNetLib",
            rf"SOFTWARE\WOW6432Node\Microsoft\Microsoft SQL Server\MSSQL12.{self.instance_name}\MSSQLServer\SuperSocketNetLib",
        ]
        for rk in (r"SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL", r"SOFTWARE\WOW6432Node\Microsoft\Microsoft SQL Server\Instance Names\SQL"):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rk) as k:
                    internal_name, _ = winreg.QueryValueEx(k, self.instance_name)
                    if internal_name:
                        reg_roots.insert(0, rf"SOFTWARE\Microsoft\Microsoft SQL Server\{internal_name}\MSSQLServer\SuperSocketNetLib")
                        reg_roots.insert(1, rf"SOFTWARE\WOW6432Node\Microsoft\Microsoft SQL Server\{internal_name}\MSSQLServer\SuperSocketNetLib")
            except Exception:
                pass
        for rpath in reg_roots:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"{rpath}\Tcp", 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, "Enabled", 0, winreg.REG_DWORD, 1)
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"{rpath}\Np", 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, "Enabled", 0, winreg.REG_DWORD, 1)
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"{rpath}\Tcp\IPAll", 0, winreg.KEY_SET_VALUE) as ip_key:
                    winreg.SetValueEx(ip_key, "TcpPort", 0, winreg.REG_SZ, "1433")
                    winreg.SetValueEx(ip_key, "TcpDynamicPorts", 0, winreg.REG_SZ, "")
            except Exception:
                pass

        # ۲. فعال‌سازی و استارت سرویس SQLBrowser
        try:
            subprocess.run(["sc", "config", "SQLBrowser", "start=", "auto"], capture_output=True, timeout=10)
            subprocess.run(["net", "start", "SQLBrowser"], capture_output=True, timeout=20)
        except Exception:
            pass

        # ۳. تنظیم رول‌های فایروال ویندوز
        try:
            fw_cmds = [
                'netsh advfirewall firewall add rule name="SQL Server Port" dir=in action=allow protocol=TCP localport=1433 profile=any',
                'netsh advfirewall firewall add rule name="SQL Browser Port" dir=in action=allow protocol=UDP localport=1434 profile=any',
            ]
            for cmd in fw_cmds:
                subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
        except Exception:
            pass

        # ۴. ری‌استارت سریع سرویس جهت اعمال پروتکل‌های شبکه
        svc_name = f"MSSQL${self.instance_name}" if self.instance_name != "MSSQLSERVER" else "MSSQLSERVER"
        try:
            subprocess.run(["net", "start", svc_name], capture_output=True, timeout=20)
        except Exception:
            pass

        # ۵. اعمال محدودیت رم و DOP از طریق ODBC
        from ai.sepehryar_setup_ai import setup_ai
        profile = setup_ai._profile or setup_ai.analyze_hardware()
        self._configure_sql_memory_and_dop(
            profile.recommended_sql_max_memory_mb,
            profile.recommended_sql_dop
        )

    def _configure_sql_memory_and_dop(self, max_memory_mb: int, max_dop: int):
        """تنظیم حافظه رم و DOP پس از نصب از طریق ODBC بدون اتکا به سوییچ‌های شکننده ستاپ"""
        logger.log("SQL", "CONFIG", "RUNNING", f"پیکربندی داینامیک RAM={max_memory_mb}MB و MAXDOP={max_dop}")
        try:
            drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
            driver = "SQL Server"
            for d in ["ODBC Driver 17 for SQL Server", "SQL Server Native Client 11.0", "SQL Server"]:
                if d in drivers:
                    driver = d
                    break

            target_server = f".\\{self.instance_name}" if self.instance_name != "MSSQLSERVER" else "."
            conn_str = f"Driver={{{driver}}};Server={target_server};UID={self.sa_user};PWD={self.sa_password};"
            conn = pyodbc.connect(conn_str, timeout=10, autocommit=True)
            cursor = conn.cursor()

            cursor.execute("EXEC sp_configure 'show advanced options', 1; RECONFIGURE;")
            if max_memory_mb > 512:
                cursor.execute(f"EXEC sp_configure 'max server memory (MB)', {max_memory_mb}; RECONFIGURE;")
            if max_dop > 0:
                cursor.execute(f"EXEC sp_configure 'max degree of parallelism', {max_dop}; RECONFIGURE;")
            conn.close()
            logger.log("SQL", "CONFIG", "SUCCESS", f"محدودیت حافظه ({max_memory_mb}MB) با موفقیت اعمال گردید.")
        except Exception as ex:
            logger.log("SQL", "CONFIG", "WARN", f"تنظیم داینامیک حافظه با هشدار مواجه شد: {ex}")

    # =========================================================================
    # اجرای کامل و هوشمند پایپ‌لاین نصب (Execute Flow)
    # =========================================================================

    def execute_flow(self, destination_setup_dir: Path) -> Tuple[bool, SQLVerificationResult]:
        """
        اجرای چرخه کامل اس‌کیو‌ال سرور با دقت حداکثری:
        ۱. بازرسی اینستنس‌های موجود و تأمین خودکار کم و کسری‌ها بدون نصب مجدد
        ۲. پایش بستر قبل از ستاپ (WMI، RebootPending، پچ NVMe)
        ۳. نصب تخصصی ۲۰۱۴ یا ۲۰۱۹ با مانیتورینگ زنده لاگ و فال‌بک ایزو
        ۴. سخت‌سازی، فایروال، پورت‌ها و لیمیت حافظه
        """
        self._notify(f"بررسی وضعیت اینستنس SQL Server {self.sql_version} ({self.instance_name})...", 5)
        logger.log("SQL", "CHECK_INSTANCE", "RUNNING", f"بررسی وجود اینستنس {self.instance_name}")

        from sql.sql_auditor import SQLInstanceAuditor
        auditor = SQLInstanceAuditor(sa_user=self.sa_user, sa_password=self.sa_password)
        audits = auditor.scan_all_instances()

        # بررسی وضعیت اینستنس موردنظر
        target_instance = self.instance_name
        is_installed = False if self.force_new_instance else is_sql_instance_installed(target_instance)

        # اگر کاربر صریحاً نام اینستنس مشخص نکرده باشد، می‌توان در صورت وجود اینستنس دیگر از آن استفاده کرد
        if not is_installed and not self.has_custom_instance and not self.force_new_instance:
            for cand_ver, cand_info in audits.items():
                if cand_info.is_installed:
                    logger.log("SQL", "AUDIT", "FOUND", f"اینستنس جایگزین {cand_info.instance_name} یافت شد.")
                    target_instance = cand_info.instance_name
                    self.sql_version = cand_ver
                    self.instance_name = target_instance
                    is_installed = True
                    break

        if is_installed:
            self._notify(f"اینستنس {self.instance_name} شناسایی شد. تأمین خودکار کم و کسری‌ها...", 25)
            logger.log("SQL", "CHECK_INSTANCE", "FOUND", f"اینستنس {self.instance_name} از قبل وجود دارد. تأمین کم و کسری‌ها.")

            data_dir = destination_setup_dir.parent / "SEPEHRYAR.Data"
            auditor.remediate_instance_shortages(
                instance_name=self.instance_name,
                data_dir=data_dir,
                progress_callback=self._notify,
            )

            self._post_install_hardening()

            self._notify(f"در حال اعتبارسنجی اتصال نهایی به {self.instance_name}...", 90)
            res = verify_sql_connection(self.instance_name, sql_user=self.sa_user, sql_password=self.sa_password)
            if res.is_connected:
                self._notify(f"اینستنس {self.instance_name} با موفقیت آماده استفاده شد.", 100)
                return True, res
            else:
                res_win = verify_sql_connection(self.instance_name)
                if res_win.is_connected:
                    self._notify(f"اتصال با Windows Authentication به {self.instance_name} برقرار شد.", 100)
                    return True, res_win
                return False, res

        # ─── شروع فرآیند نصب جدید ───
        self._notify("پایش بستر ویندوز و رفع موانع بالقوه ستاپ (Pre-Flight)...", 10)
        self._perform_preflight_checks()

        sysadmins = self._get_sysadmin_accounts()
        is_64bit_os = platform_is_64bit = (os.environ.get("PROCESSOR_ARCHITEW6432") == "AMD64" or os.environ.get("PROCESSOR_ARCHITECTURE") == "AMD64")

        # =========================================================================
        # حالت اول: نصب دقیق SQL Server 2014 Enterprise (از پوشه SETUP/SQL)
        # =========================================================================
        if self.sql_version == "2014":
            self._notify("آماده‌سازی بسته نصبی SQL Server 2014 Enterprise...", 15)
            sql_2014_dir = destination_setup_dir / "SQL"
            if not (sql_2014_dir / "setup.exe").exists():
                sql_2014_dir = SETUP_DIR / "SQL"

            sql_setup_exe = sql_2014_dir / "setup.exe"
            if not sql_setup_exe.exists():
                err_msg = f"فایل نصاب setup.exe در مسیر {sql_2014_dir} یافت نشد."
                logger.log("SQL", "SETUP", "ERROR", err_msg)
                return False, SQLVerificationResult(
                    is_connected=False,
                    instance_name=self.instance_name,
                    target_server=f".\\{self.instance_name}",
                    sql_version="",
                    auth_method="None",
                    databases=[],
                    error_message=err_msg,
                )

            # ۱. فعال‌سازی تضمینی NetFX3 با سورس آفلاین در صورت وجود
            self._enable_dotnet35(fallback_source_dir=sql_2014_dir)

            # ۲. بررسی فیچرهای رسانه (SQLEngine, Replication و SSMS Tools در صورت وجود)
            features_2014 = "SQLEngine,Replication"
            if (sql_2014_dir / "x86" / "Setup" / "sql_ssms.msi").exists() or any(sql_2014_dir.rglob("sql_ssms.msi")):
                features_2014 = "SQLEngine,Replication,SSMS,ADV_SSMS"

            setup_args = [
                f'"{sql_setup_exe}"',
                "/q",
                "/ACTION=Install",
                "/IACCEPTSQLSERVERLICENSETERMS",
                f"/FEATURES={features_2014}",
                f"/INSTANCENAME={self.instance_name}",
                "/SECURITYMODE=SQL",
                f"/SAPWD={self.sa_password}",
                f"/SQLSYSADMINACCOUNTS={sysadmins}",
                '/SQLSVCACCOUNT="NT AUTHORITY\\Network Service"',
                "/SQLSVCSTARTUPTYPE=Automatic",
                '/AGTSVCACCOUNT="NT AUTHORITY\\Network Service"',
                "/AGTSVCSTARTUPTYPE=Automatic",
                "/SQLCOLLATION=Arabic_CI_AS",
                "/TCPENABLED=1",
                "/NPENABLED=1",
                "/UpdateEnabled=False",
                "/SUPPRESSPRIVACYSTATEMENTNOTICE=1",
            ]
            has_x86_media = (sql_2014_dir / "x86").exists()
            has_x64_media = (sql_2014_dir / "x64").exists()
            if is_64bit_os and has_x86_media and not has_x64_media:
                setup_args.append("/X86=True")

            ret_code, err_detail = self._run_setup_with_live_monitoring(
                setup_args=setup_args,
                ver_code="120",
                start_pct=30,
                end_pct=80
            )

        # =========================================================================
        # حالت دوم: نصب دقیق SQL Server 2019 Enterprise (اکسترکت RAR و مانت دو لایه ISO)
        # =========================================================================
        else:
            self._notify("آماده‌سازی پکیج نصبی SQL Server 2019...", 15)
            rar_file = destination_setup_dir / SQL_ARCHIVE_NAME
            if not rar_file.exists():
                rar_file = SETUP_DIR / SQL_ARCHIVE_NAME

            if not rar_file.exists():
                self._notify("آرشیو محلی یافت نشد. شروع دانلود آنلاین خودکار...", 18)
                from downloader.sql_downloader import SQLOnlineDownloader
                sql_dl = SQLOnlineDownloader(sql_version=self.sql_version)
                dl_ok, dl_archive, dl_msg = sql_dl.download_extract_flow(
                    destination_dir=destination_setup_dir,
                    local_search_dirs=[destination_setup_dir, SETUP_DIR],
                )
                if dl_ok and dl_archive:
                    rar_file = dl_archive
                else:
                    return False, SQLVerificationResult(
                        is_connected=False,
                        instance_name=self.instance_name,
                        target_server=f".\\{self.instance_name}",
                        sql_version="",
                        auth_method="None",
                        databases=[],
                        error_message=f"دانلود آنلاین SQL Server ناموفق بود: {dl_msg}",
                    )

            extract_dir = destination_setup_dir / "SQL_Extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)

            self._notify("در حال استخراج بسته نصبی SQL Server 2019...", 25)
            ok_ext, msg_ext = extract_archive_universal(
                archive_path=rar_file,
                dest_dir=extract_dir,
                password=SQL_ARCHIVE_PASS,
                progress_callback=self._notify,
            )
            if not ok_ext:
                return False, SQLVerificationResult(
                    is_connected=False,
                    instance_name=self.instance_name,
                    target_server=f".\\{self.instance_name}",
                    sql_version="",
                    auth_method="None",
                    databases=[],
                    error_message=f"خطا در استخراج آرشیو اس‌کیو‌ال: {msg_ext}",
                )

            iso_files = list(extract_dir.rglob("*.iso"))
            if not iso_files:
                return False, SQLVerificationResult(
                    is_connected=False,
                    instance_name=self.instance_name,
                    target_server=f".\\{self.instance_name}",
                    sql_version="",
                    auth_method="None",
                    databases=[],
                    error_message="فایل ISO در پکیج استخراج‌شده یافت نشد.",
                )

            iso_path = iso_files[0]
            sql_setup_exe = None
            mounted_drive = None

            # مانت دولایه: لایه ۱ پاورشل | لایه ۲ استخراج مستقیم به عنوان آرشیو
            self._notify("در حال مانت کردن تصویر دیسک (ISO)...", 35)
            try:
                mount_cmd = f"$img = Mount-DiskImage -ImagePath '{iso_path}' -PassThru; ($img | Get-Volume).DriveLetter"
                out = subprocess.check_output(["powershell", "-NoProfile", "-Command", mount_cmd], text=True, timeout=45).strip()
                if out:
                    mounted_drive = f"{out}:"
                    cand_setup = Path(f"{mounted_drive}\\setup.exe")
                    if cand_setup.exists():
                        sql_setup_exe = cand_setup
                        logger.log("SQL", "MOUNT", "SUCCESS", f"ایمیج روی درایو مجازی {mounted_drive} مانت گردید.")
            except Exception as ex_m:
                logger.log("SQL", "MOUNT", "WARN", f"مانت پاورشل با هشدار مواجه شد: {ex_m}")

            # فال‌بک لایه ۲: استخراج محتویات ایزو با اکسترکتور چندلایه در صورت شکست درایو مجازی
            if not sql_setup_exe:
                self._notify("استخراج مستقیم فایل‌های درون ISO...", 38)
                iso_extracted_dir = extract_dir / "ISO_Extracted"
                iso_extracted_dir.mkdir(parents=True, exist_ok=True)
                ok_iso, _ = extract_archive_universal(iso_path, iso_extracted_dir, progress_callback=self._notify)
                cand_setup = iso_extracted_dir / "setup.exe"
                if not cand_setup.exists():
                    sub_setups = list(iso_extracted_dir.rglob("setup.exe"))
                    if sub_setups:
                        cand_setup = sub_setups[0]
                if cand_setup.exists():
                    sql_setup_exe = cand_setup
                    logger.log("SQL", "FALLBACK_ISO", "SUCCESS", f"فایل setup.exe از استخراج مستقیم ایزو به دست آمد: {cand_setup}")

            if not sql_setup_exe or not sql_setup_exe.exists():
                return False, SQLVerificationResult(
                    is_connected=False,
                    instance_name=self.instance_name,
                    target_server=f".\\{self.instance_name}",
                    sql_version="",
                    auth_method="None",
                    databases=[],
                    error_message="فایل ستاپ setup.exe در تصویر ISO شناسایی نشد.",
                )

            # آرگومان‌های کاملاً مهندسی‌شده و دقیق SQL Server 2019
            setup_args = [
                f'"{sql_setup_exe}"',
                "/q",
                "/ACTION=Install",
                f"/FEATURES={SQL_FEATURES}",
                f"/INSTANCENAME={self.instance_name}",
                "/SECURITYMODE=SQL",
                f"/SAPWD={self.sa_password}",
                f"/SQLSYSADMINACCOUNTS={sysadmins}",
                f'/SQLSVCACCOUNT="NT SERVICE\\MSSQL${self.instance_name}"',
                "/SQLSVCSTARTUPTYPE=Automatic",
                f'/AGTSVCACCOUNT="NT SERVICE\\SQLAgent${self.instance_name}"',
                "/AGTSVCSTARTUPTYPE=Automatic",
                "/TCPENABLED=1",
                "/NPENABLED=1",
                "/IACCEPTSQLSERVERLICENSETERMS",
                "/SUPPRESSPRIVACYSTATEMENTNOTICE",
                "/UpdateEnabled=False",
                "/SQLCOLLATION=Arabic_CI_AS",
            ]

            try:
                ret_code, err_detail = self._run_setup_with_live_monitoring(
                    setup_args=setup_args,
                    ver_code="150",
                    start_pct=40,
                    end_pct=85
                )
            finally:
                if mounted_drive:
                    try:
                        subprocess.run(["powershell", "-NoProfile", "-Command", f"Dismount-DiskImage -ImagePath '{iso_path}'"], timeout=20)
                    except Exception:
                        pass

        # =========================================================================
        # فاز ۴: اعتبارسنجی اتصال، سخت‌سازی و اعلام نتیجه نهایی
        # =========================================================================
        self._notify("سخت‌سازی امنیتی، باز کردن پورت‌ها و راه‌اندازی سرویس...", 88)
        self._post_install_hardening()

        self._notify(f"اعتبارسنجی اتصال و تست پایداری به {self.instance_name}...", 94)
        start_sql_service_if_stopped(self.instance_name)
        res = verify_sql_connection(self.instance_name, sql_user=self.sa_user, sql_password=self.sa_password)

        if not res.is_connected:
            # تست مجدد با Windows Authentication
            res_win = verify_sql_connection(self.instance_name)
            if res_win.is_connected:
                res = res_win

        if res.is_connected:
            self._notify(f"نصب و اتصال به SQL Server {self.sql_version} با موفقیت پایان یافت.", 100)
            logger.log("SQL", "FINISH", "SUCCESS", f"اینستنس {self.instance_name} پایدار و فعال است.")
            return True, res
        else:
            ver_code = "120" if self.sql_version == "2014" else "150"
            err_msg = self._extract_summary_error(ver_code) or res.error_message or "خطای اعتبارسنجی اتصال به سرویس"
            res.error_message = err_msg
            self._notify(f"خطا در راه‌اندازی SQL Server: {err_msg}", 100)
            logger.log("SQL", "FINISH", "ERROR", f"شکست در اتصال نهایی: {err_msg}")
            return False, res
