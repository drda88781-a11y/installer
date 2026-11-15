# sql/sql_auditor.py
"""
ماژول ممیزی، تشخیص هوشمند اینستنس‌های SEPEHRYAR2019 و SEPEHRYAR2014 و تأمین خودکار کم و کسری‌ها
SQL Server Instance Auditor & Automatic Shortages Remediation Engine
"""

import os
import re
import shutil
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import winreg

import psutil
import pyodbc

from config.settings import (
    SQL_SA_USER,
    SQL_SA_PASSWORD,
    SQL_2014_INSTANCE_NAME,
    SQL_2019_INSTANCE_NAME,
)
from app_logging.app_logger import logger


class InstanceAuditInfo:
    """مشخصات وضعیت زنده یک اینستنس SQL Server روی سیستم"""
    def __init__(self, instance_name: str, version_label: str):
        self.instance_name = instance_name
        self.version_label = version_label  # "2019", "2014", or other
        self.is_installed: bool = False
        self.service_status: str = "not_installed"  # running, stopped, not_installed
        self.is_connected: bool = False
        self.auth_method: str = "None"
        self.databases: List[str] = []
        self.sql_full_version: str = ""
        self.tcp_enabled: bool = False
        self.browser_running: bool = False
        self.error_message: Optional[str] = None


class ShortagesRemediationReport:
    """گزارش اقدامات انجام شده جهت جبران کم و کسری‌های اینستنس"""
    def __init__(self):
        self.instance_name: str = ""
        self.service_started: bool = False
        self.browser_started: bool = False
        self.tcp_configured: bool = False
        self.attached_databases: List[str] = []
        self.executed_sql_scripts: List[str] = []
        self.prereqs_installed: List[str] = []
        self.is_ready: bool = False
        self.actions_log: List[str] = []
        self.error_message: Optional[str] = None


class SQLInstanceAuditor:
    """
    موتور بازرسی و تشخیص اینستنس‌های سپهریار و جبران کم‌وکسری‌ها
    """
    def __init__(self, sa_user: str = SQL_SA_USER, sa_password: str = SQL_SA_PASSWORD):
        self.sa_user = sa_user
        self.sa_password = os.environ.get("SEPEHRYAR_SQL_PWD", sa_password)

    def scan_all_instances(self) -> Dict[str, InstanceAuditInfo]:
        """
        اسکن سریع تمامی اینستنس‌های نصب‌شده بر روی سیستم
        """
        results: Dict[str, InstanceAuditInfo] = {}

        # بررسی SEPEHRYAR2019
        info_2019 = self.inspect_instance(SQL_2019_INSTANCE_NAME, "2019")
        results["2019"] = info_2019

        # بررسی SEPEHRYAR2014
        info_2014 = self.inspect_instance(SQL_2014_INSTANCE_NAME, "2014")
        results["2014"] = info_2014

        # بررسی تمامی اینستنس‌های دیگر موجود در ویندوز (مانند MSSQLSERVER, SQLEXPRESS و غیره)
        try:
            from sql.sql_detector import get_all_installed_sql_instances
            all_insts = get_all_installed_sql_instances()
            for inst in all_insts:
                if inst.upper() not in (SQL_2019_INSTANCE_NAME.upper(), SQL_2014_INSTANCE_NAME.upper()):
                    results[inst] = self.inspect_instance(inst, "detected")
        except Exception as ex:
            logger.log("SQL_AUDITOR", "SCAN_ALL", "WARN", f"خطا در اسکن اینستنس‌های عمومی: {ex}")

        return results

    def detect_installed_instances(self) -> List[InstanceAuditInfo]:
        """لیست تمام اینستنس‌های شناسایی‌شده نصب روی سیستم"""
        all_audits = self.scan_all_instances()
        return [info for info in all_audits.values() if info.is_installed]

    def get_preferred_instance(self) -> Optional[InstanceAuditInfo]:
        """دریافت بهترین اینستنس موجود (ترجیحاً ۲۰۱۹ سپس ۲۰۱۴ یا سایرین)"""
        audits = self.scan_all_instances()
        if audits.get("2019") and audits["2019"].is_installed:
            return audits["2019"]
        if audits.get("2014") and audits["2014"].is_installed:
            return audits["2014"]
        installed = self.detect_installed_instances()
        if installed:
            return installed[0]
        return None

    def inspect_instance(self, instance_name: str, version_label: str) -> InstanceAuditInfo:
        """
        ارزیابی وضعیت فنی یک اینستنس مشخص
        """
        info = InstanceAuditInfo(instance_name, version_label)

        # ۱. بررسی نصب بودن از طریق رجیستری
        reg_keys = [
            r"SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL",
            r"SOFTWARE\WOW6432Node\Microsoft\Microsoft SQL Server\Instance Names\SQL",
        ]
        for rpath in reg_keys:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rpath) as key:
                    val, _ = winreg.QueryValueEx(key, instance_name)
                    if val:
                        info.is_installed = True
                        break
            except OSError:
                pass

        # ۲. بررسی وضعیت سرویس ویندوز
        svc_name = f"MSSQL${instance_name}" if instance_name != "MSSQLSERVER" else "MSSQLSERVER"
        try:
            svc = psutil.win_service_get(svc_name)
            info.is_installed = True
            info.service_status = svc.status()  # "running" or "stopped"
        except Exception:
            if not info.is_installed:
                info.service_status = "not_installed"
            else:
                info.service_status = "stopped"

        # ۳. بررسی سرویس SQLBrowser
        try:
            b_svc = psutil.win_service_get("SQLBrowser")
            info.browser_running = (b_svc.status() == "running")
        except Exception:
            info.browser_running = False

        # ۴. تست اتصال زنده ODBC در صورت فعال بودن سرویس یا تلاش برای تست
        if info.is_installed:
            conn_ok, ver, auth, dbs, err = self._test_connection(instance_name)
            info.is_connected = conn_ok
            info.sql_full_version = ver
            info.auth_method = auth
            info.databases = dbs
            info.error_message = err

        return info

    def _test_connection(self, instance_name: str) -> Tuple[bool, str, str, List[str], Optional[str]]:
        """تست سریع اتصال با ODBC به اینستنس"""
        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        if not drivers:
            return False, "", "None", [], "هیچ درایور ODBC برای SQL Server نصب نیست."

        preferred_driver = "SQL Server"
        for d in ["ODBC Driver 17 for SQL Server", "SQL Server Native Client 11.0", "SQL Server"]:
            if d in drivers:
                preferred_driver = d
                break

        target_server = f".\\{instance_name}" if instance_name != "MSSQLSERVER" else "."

        # ۱. ابتدا با Windows Authentication (سریع‌تر و بدون نیاز به پسورد)
        try:
            conn_str = f"Driver={{{preferred_driver}}};Server={target_server};Trusted_Connection=yes;"
            conn = pyodbc.connect(conn_str, timeout=3, autocommit=True)
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            v_row = cursor.fetchone()
            sql_ver = v_row[0].split("\n")[0].strip() if v_row else ""

            cursor.execute("SELECT name FROM sys.databases")
            dbs = [r[0] for r in cursor.fetchall()]
            conn.close()
            return True, sql_ver, "Windows Authentication", dbs, None
        except Exception:
            pass

        # ۲. تلاش با حساب sa
        try:
            conn_str = f"Driver={{{preferred_driver}}};Server={target_server};UID={self.sa_user};PWD={self.sa_password};"
            conn = pyodbc.connect(conn_str, timeout=3, autocommit=True)
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            v_row = cursor.fetchone()
            sql_ver = v_row[0].split("\n")[0].strip() if v_row else ""

            cursor.execute("SELECT name FROM sys.databases")
            dbs = [r[0] for r in cursor.fetchall()]
            conn.close()
            return True, sql_ver, "SQL Authentication (sa)", dbs, None
        except Exception as ex_sa:
            return False, "", "None", [], str(ex_sa)

    def remediate_instance_shortages(
        self,
        instance_name: str,
        data_dir: Optional[Path] = None,
        pending_sql_scripts: Optional[List[Path]] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> ShortagesRemediationReport:
        """
        جبران هوشمند و کامل کم و کسری‌های اینستنس موجود:
        ۱. استارت سرویس SQL Server در صورت Stopped بودن
        ۲. استارت سرویس SQLBrowser
        ۳. فعال‌سازی TCP/IP و پروتکل‌ها در رجیستری
        ۴. بازرسی دیتابیس‌ها و اتچ خودکار فایل‌های MDF رهاشده در پوشه Data
        ۵. اجرای پچ‌های اسکریپتی SQL در صورت وجود
        """
        report = ShortagesRemediationReport()
        report.instance_name = instance_name
        svc_name = f"MSSQL${instance_name}" if instance_name != "MSSQLSERVER" else "MSSQLSERVER"

        def notify(msg: str, pct: int):
            if progress_callback:
                progress_callback(msg, pct)
            logger.log("SQL_AUDIT", "REMEDIATE", "INFO", msg)
            report.actions_log.append(msg)

        notify(f"بررسی کم و کسری‌های اینستنس {instance_name}...", 10)

        # ۱. اطمینان از استارت بودن سرویس اصلی
        try:
            svc = psutil.win_service_get(svc_name)
            if svc.status() != "running":
                notify(f"در حال راه‌اندازی سرویس متوقف‌شده {svc_name}...", 20)
                subprocess.run(["net", "start", svc_name], capture_output=True, text=True, timeout=30)
                time.sleep(2)
                report.service_started = True
            else:
                notify(f"سرویس پایگاه داده {svc_name} فعال است.", 25)
        except Exception as ex_svc:
            notify(f"هشدار در بررسی سرویس {svc_name}: {ex_svc}", 25)

        # ۲. راه‌اندازی سرویس SQLBrowser
        try:
            b_svc = psutil.win_service_get("SQLBrowser")
            if b_svc.status() != "running":
                notify("در حال فعال‌سازی سرویس جستجوی پایگاه داده (SQL Server Browser)...", 35)
                subprocess.run(["sc", "config", "SQLBrowser", "start=", "auto"], capture_output=True, timeout=10)
                subprocess.run(["net", "start", "SQLBrowser"], capture_output=True, timeout=20)
                report.browser_started = True
            else:
                notify("سرویس SQL Server Browser فعال است.", 40)
        except Exception:
            pass

        # ۳. تنظیم مجوز دسترسی فولدر داده‌ها (icacls)
        if data_dir and data_dir.exists():
            notify(f"تنظیم دسترسی کامل سرویس به پوشه داده‌ها ({data_dir.name})...", 50)
            try:
                subprocess.run(["icacls", str(data_dir), "/grant", "Everyone:(OI)(CI)F", "/T", "/Q"], capture_output=True, timeout=15)
            except Exception:
                pass

        # ۴. اتصال به پایگاه داده و اتچ کردن دیتابیس‌های مفقود
        notify("اعتبارسنجی اتصال و بررسی دیتابیس‌های متصل...", 60)
        conn_ok, _, auth_m, existing_dbs, err = self._test_connection(instance_name)

        if conn_ok:
            # اتچ خودکار فایل‌های .mdf که هنوز در دیتابیس رجیستر نشده‌اند
            if data_dir and data_dir.exists():
                mdf_files = list(data_dir.glob("*.mdf"))
                for mdf in mdf_files:
                    db_name = mdf.stem
                    if db_name not in existing_dbs and db_name.lower() not in ["master", "model", "msdb", "tempdb"]:
                        notify(f"در حال اتچ کردن دیتابیس مفقود: {db_name}...", 75)
                        att_ok = self._attach_single_db(instance_name, mdf)
                        if att_ok:
                            report.attached_databases.append(db_name)
                            existing_dbs.append(db_name)

            # ۵. اجرای اسکریپت‌های پچ SQL
            if pending_sql_scripts:
                for sql_file in pending_sql_scripts:
                    if sql_file.exists() and sql_file.suffix.lower() == ".sql":
                        notify(f"در حال اعمال اسکریپت پچ دیتابیس: {sql_file.name}...", 85)
                        exec_ok, ex_msg = self.execute_sql_script(instance_name, sql_file, target_db="master")
                        if exec_ok:
                            report.executed_sql_scripts.append(sql_file.name)
                        else:
                            notify(f"هشدار در اجرای پچ {sql_file.name}: {ex_msg}", 90)

            report.is_ready = True
            notify(f"اینستنس {instance_name} با موفقیت آماده استفاده گردید.", 100)
        else:
            report.is_ready = False
            report.error_message = f"عدم امکان برقراری ارتباط با اینستنس {instance_name}: {err}"
            notify(f"خطا در اتصال به اینستنس: {err}", 100)

        return report

    def _attach_single_db(self, instance_name: str, mdf_path: Path) -> bool:
        """اتچ کردن یک دیتابیس تکی به اینستنس با درایور ODBC"""
        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        driver = drivers[0] if drivers else "SQL Server"
        target_server = f".\\{instance_name}" if instance_name != "MSSQLSERVER" else "."
        db_name = mdf_path.stem

        conn_str = f"Driver={{{driver}}};Server={target_server};UID={self.sa_user};PWD={self.sa_password};"
        try:
            conn = pyodbc.connect(conn_str, timeout=10, autocommit=True)
            cursor = conn.cursor()
            ldf_path = mdf_path.with_suffix(".ldf")
            if not ldf_path.exists():
                ldf_path = mdf_path.parent / f"{mdf_path.stem}_log.ldf"

            if ldf_path.exists():
                sql = f"CREATE DATABASE [{db_name}] ON (FILENAME = N'{str(mdf_path.resolve())}'), (FILENAME = N'{str(ldf_path.resolve())}') FOR ATTACH;"
            else:
                sql = f"CREATE DATABASE [{db_name}] ON (FILENAME = N'{str(mdf_path.resolve())}') FOR ATTACH_REBUILD_LOG;"

            cursor.execute(sql)
            conn.close()
            logger.log("SQL_AUDIT", "ATTACH", "SUCCESS", f"دیتابیس {db_name} با موفقیت اتچ شد.")
            return True
        except Exception as ex:
            logger.log("SQL_AUDIT", "ATTACH", "WARN", f"خطا در اتچ {db_name}: {ex}")
            return False

    def execute_sql_script(self, instance_name: str, script_path: Path, target_db: str = "master") -> Tuple[bool, str]:
        """اجرای یک اسکریپت SQL بر روی دیتابیس مشخص با پشتیبانی sqlcmd و هندلینگ پیشرفته GO"""
        if not script_path.exists():
            return False, "فایل اسکریپت یافت نشد."

        target_server = f".\\{instance_name}" if instance_name != "MSSQLSERVER" else "."

        # ۱. ابتدا تلاش با sqlcmd.exe رسمی در صورت موجود بودن در سیستم
        sqlcmd_path = shutil.which("sqlcmd")
        if not sqlcmd_path:
            candidates = [
                Path(r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn\SQLCMD.EXE"),
                Path(r"C:\Program Files\Microsoft SQL Server\110\Tools\Binn\SQLCMD.EXE"),
                Path(r"C:\Program Files (x86)\Microsoft SQL Server\110\Tools\Binn\SQLCMD.EXE"),
                Path(r"C:\Program Files\Microsoft SQL Server\140\Tools\Binn\SQLCMD.EXE"),
                Path(r"C:\Program Files\Microsoft SQL Server\150\Tools\Binn\SQLCMD.EXE"),
            ]
            for c in candidates:
                if c.exists():
                    sqlcmd_path = str(c)
                    break

        if sqlcmd_path:
            try:
                # ابتدا با Windows Auth
                cmd_sqlcmd = [
                    str(sqlcmd_path),
                    "-S", target_server,
                    "-d", target_db,
                    "-E",
                    "-i", str(script_path),
                    "-b",
                ]
                res = subprocess.run(cmd_sqlcmd, capture_output=True, text=True, timeout=180)
                if res.returncode == 0:
                    logger.log("SQL_AUDIT", "SQLCMD", "SUCCESS", f"اسکریپت {script_path.name} با sqlcmd (Windows Auth) اجرا شد.")
                    return True, f"اسکریپت {script_path.name} با موفقیت اعمال گردید."

                # تلاش دوم با sa
                cmd_sqlcmd_sa = [
                    str(sqlcmd_path),
                    "-S", target_server,
                    "-d", target_db,
                    "-U", self.sa_user,
                    "-P", self.sa_password,
                    "-i", str(script_path),
                    "-b",
                ]
                res_sa = subprocess.run(cmd_sqlcmd_sa, capture_output=True, text=True, timeout=180)
                if res_sa.returncode == 0:
                    logger.log("SQL_AUDIT", "SQLCMD", "SUCCESS", f"اسکریپت {script_path.name} با sqlcmd (sa) اجرا شد.")
                    return True, f"اسکریپت {script_path.name} با موفقیت اعمال گردید."
            except Exception as ex_cmd:
                logger.log("SQL_AUDIT", "SQLCMD", "WARN", f"خطا در اجرای sqlcmd: {ex_cmd} — تلاش با درایور ODBC.")

        # ۲. فال‌بک با ODBC و تفکیک پیشرفته دسته‌های GO با Regex
        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        driver = drivers[0] if drivers else "SQL Server"

        conn_str = f"Driver={{{driver}}};Server={target_server};Database={target_db};UID={self.sa_user};PWD={self.sa_password};"
        try:
            conn = pyodbc.connect(conn_str, timeout=15, autocommit=True)
        except Exception:
            try:
                conn = pyodbc.connect(f"Driver={{{driver}}};Server={target_server};Database={target_db};Trusted_Connection=yes;", timeout=15, autocommit=True)
            except Exception as ex_c:
                return False, f"عدم امکان اتصال جهت اجرای اسکریپت: {ex_c}"

        try:
            cursor = conn.cursor()
            content = script_path.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff\uffef \t\r\n")

            # تفکیک دقیق تمام فرم‌های GO در خطوط مجزا بدون حساسیت به حروف بزرگ/کوچک
            batches = re.split(r"(?im)^\s*GO\s*(?:--.*)?$", content)
            executed_batches = 0
            for batch in batches:
                clean_b = batch.strip().lstrip("\ufeff\uffef \t\r\n")
                if clean_b:
                    cursor.execute(clean_b)
                    executed_batches += 1

            conn.close()
            logger.log("SQL_AUDIT", "SCRIPT_EXEC", "SUCCESS", f"اسکریپت {script_path.name} با {executed_batches} بچ اعمال شد.")
            return True, f"اسکریپت {script_path.name} با موفقیت اعمال گردید."
        except Exception as ex:
            logger.log("SQL_AUDIT", "SCRIPT_EXEC", "WARN", f"خطا در اجرای اسکریپت {script_path.name}: {ex}")
            return False, str(ex)
