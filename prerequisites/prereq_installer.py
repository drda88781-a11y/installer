# prerequisites/prereq_installer.py
"""
ماژول شناسایی، اعتبارسنجی و نصب پیش‌نیازهای نرم‌افزاری، گزارش‌سازها و فونت‌ها
Detection, validation, and installation of runtime prerequisites, reports, and fonts
"""

import ctypes
import os
import shutil
import subprocess
import winreg
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional

from config.settings import SETUP_DIR, BASE_DIR
from app_logging.app_logger import logger


class PrereqStatus(Enum):
    PENDING = "در انتظار"
    CHECKING = "در حال بررسی..."
    ALREADY_INSTALLED = "قبلاً نصب شده"
    INSTALLING = "در حال نصب..."
    COMPLETED = "نصب شد"
    FAILED = "ناموفق"


@dataclass
class PrereqItem:
    id: str
    title_fa: str
    status: PrereqStatus
    status_message: str
    installer_path: Optional[Path] = None
    is_required: bool = True


class PrerequisiteManager:
    """
    مدیریت هوشمند بررسی وضعیت و نصب بدون نیاز به اجرای مکرر
    """
    def __init__(self, callback: Optional[Callable[[str, PrereqStatus, str], None]] = None):
        self.callback = callback
        self.items: List[PrereqItem] = [
            PrereqItem(
                id="crystal_reports",
                title_fa="کریستال ریپورتز (Crystal Reports 10.5 / 2008)",
                status=PrereqStatus.PENDING,
                status_message="در انتظار بررسی",
                installer_path=self._find_crystal_msi(),
            ),
            PrereqItem(
                id="stimulsoft",
                title_fa="استیمول‌سافت (Stimulsoft Reports.Net 2013.2)",
                status=PrereqStatus.PENDING,
                status_message="در انتظار بررسی",
                installer_path=self._find_stimulsoft_msi(),
            ),
            PrereqItem(
                id="farsi_fonts",
                title_fa="فونت‌های فارسی سیستم (IRANSans و Arad)",
                status=PrereqStatus.PENDING,
                status_message="در انتظار بررسی",
                installer_path=None,
            ),
        ]

    def _notify(self, item_id: str, status: PrereqStatus, message: str):
        for it in self.items:
            if it.id == item_id:
                it.status = status
                it.status_message = message
                break
        if self.callback:
            self.callback(item_id, status, message)

    def _get_crystal_msi_files(self) -> List[Path]:
        """
        دریافت بسته‌های نصبی کریستال ریپورتز متناسب با معماری برنامه:
        از آنجا که هسته اجرایی سپهریار (Hesabdari.exe) ۳۲ بیتی (x86) است،
        بسته x86 حیاتی‌ترین بخش برای جلوگیری از کراش گزارشات (BadImageFormatException) است.
        در سیستم‌های ۶۴ بیتی، هر دو پکیج نصب می‌شوند.
        """
        msis: List[Path] = []
        p_x86 = SETUP_DIR / "CrystalReports10_5" / "CRRedist2008_x86.msi"
        p_x64 = SETUP_DIR / "CrystalReports10_5" / "CRRedist2008_x64.msi"

        if p_x86.exists():
            msis.append(p_x86)
        if p_x64.exists():
            msis.append(p_x64)
        return msis

    def _find_crystal_msi(self) -> Optional[Path]:
        files = self._get_crystal_msi_files()
        return files[0] if files else None

    def _find_stimulsoft_msi(self) -> Optional[Path]:
        candidates = [
            SETUP_DIR / "Stimulsoft Reports.Net 2013.2.1700" / "Stimulsoft Reports.Net 2013.2.msi",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def is_crystal_reports_installed(self) -> bool:
        """بررسی رجیستری برای کریستال ریپورتز"""
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Business Objects\10.5\Crystal Reports"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Business Objects\10.5\Crystal Reports"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\SAP BusinessObjects\Crystal Reports for .NET Framework 4.0"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\SAP BusinessObjects\Crystal Reports for .NET Framework 4.0"),
        ]
        for root, subkey in reg_paths:
            try:
                with winreg.OpenKey(root, subkey):
                    return True
            except Exception:
                pass

        # بررسی در لیست برنامه‌های Uninstall
        uninstall_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]
        for upath in uninstall_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, upath) as ukey:
                    num_subkeys = winreg.QueryInfoKey(ukey)[0]
                    for i in range(num_subkeys):
                        try:
                            sub_name = winreg.EnumKey(ukey, i)
                            with winreg.OpenKey(ukey, sub_name) as skey:
                                disp_name, _ = winreg.QueryValueEx(skey, "DisplayName")
                                if "crystal reports" in disp_name.lower():
                                    return True
                        except Exception:
                            pass
            except Exception:
                pass

        return False

    def is_stimulsoft_installed(self) -> bool:
        """بررسی رجیستری برای استیمول‌سافت"""
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Stimulsoft"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Stimulsoft"),
        ]
        for root, subkey in reg_paths:
            try:
                with winreg.OpenKey(root, subkey):
                    return True
            except Exception:
                pass

        uninstall_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]
        for upath in uninstall_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, upath) as ukey:
                    num_subkeys = winreg.QueryInfoKey(ukey)[0]
                    for i in range(num_subkeys):
                        try:
                            sub_name = winreg.EnumKey(ukey, i)
                            with winreg.OpenKey(ukey, sub_name) as skey:
                                disp_name, _ = winreg.QueryValueEx(skey, "DisplayName")
                                if "stimulsoft" in disp_name.lower():
                                    return True
                        except Exception:
                            pass
            except Exception:
                pass

        return False

    def install_crystal_reports(self) -> bool:
        """بررسی و نصب سایلنت کریستال ریپورتز (با اولویت نسخه ۳۲ بیتی برای برنامه سپهریار)"""
        self._notify("crystal_reports", PrereqStatus.CHECKING, "در حال بررسی وضعیت نصب...")
        logger.log("PREREQ", "CRYSTAL_REPORTS", "CHECKING", "بررسی وضعیت Crystal Reports در سیستم")

        msi_list = self._get_crystal_msi_files()
        if not msi_list:
            if self.is_crystal_reports_installed():
                self._notify("crystal_reports", PrereqStatus.ALREADY_INSTALLED, "قبلاً روی سیستم نصب شده است.")
                return True
            self._notify("crystal_reports", PrereqStatus.FAILED, "فایل نصبی CRRedist یافت نشد.")
            logger.log("PREREQ", "CRYSTAL_REPORTS", "ERROR", "فایل نصبی Crystal Reports یافت نشد.")
            return False

        if self.is_crystal_reports_installed():
            self._notify("crystal_reports", PrereqStatus.ALREADY_INSTALLED, "قبلاً روی سیستم نصب شده است.")
            logger.log("PREREQ", "CRYSTAL_REPORTS", "SKIPPED", "Crystal Reports از قبل نصب است.")
            return True

        self._notify("crystal_reports", PrereqStatus.INSTALLING, "در حال نصب سایلنت کریستال ریپورتز (x86/x64)...")
        overall_ok = True
        installed_names = []

        for msi_path in msi_list:
            try:
                logger.log("PREREQ", "CRYSTAL_REPORTS", "INSTALLING", f"نصب فایل {msi_path.name}")
                cmd = ["msiexec.exe", "/i", str(msi_path), "/qn", "/norestart"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if res.returncode in [0, 3010]:
                    installed_names.append(msi_path.name)
                    logger.log("PREREQ", "CRYSTAL_REPORTS", "SUCCESS", f"نصب {msi_path.name} با کد {res.returncode}")
                else:
                    overall_ok = False
                    logger.log("PREREQ", "CRYSTAL_REPORTS", "WARN", f"خروج {msi_path.name} با کد {res.returncode}")
            except Exception as ex:
                overall_ok = False
                logger.log("PREREQ", "CRYSTAL_REPORTS", "WARN", f"خطا در نصب {msi_path.name}: {ex}")

        if overall_ok:
            msg = f"کریستال ریپورتز با موفقیت نصب شد ({', '.join(installed_names)})."
            self._notify("crystal_reports", PrereqStatus.COMPLETED, msg)
            return True
        else:
            self._notify("crystal_reports", PrereqStatus.FAILED, "خطا در اجرای پکیج‌های نصبی Crystal Reports")
            return False

    def install_stimulsoft(self) -> bool:
        """بررسی و نصب سایلنت استیمول‌سافت"""
        self._notify("stimulsoft", PrereqStatus.CHECKING, "در حال بررسی وضعیت نصب...")
        logger.log("PREREQ", "STIMULSOFT", "CHECKING", "بررسی وضعیت Stimulsoft Reports")

        if self.is_stimulsoft_installed():
            self._notify("stimulsoft", PrereqStatus.ALREADY_INSTALLED, "قبلاً روی سیستم نصب شده است.")
            logger.log("PREREQ", "STIMULSOFT", "SKIPPED", "Stimulsoft از قبل نصب است.")
            return True

        msi_path = self._find_stimulsoft_msi()
        if not msi_path or not msi_path.exists():
            self._notify("stimulsoft", PrereqStatus.FAILED, "فایل نصبی Stimulsoft یافت نشد.")
            logger.log("PREREQ", "STIMULSOFT", "ERROR", "فایل نصبی Stimulsoft یافت نشد.")
            return False

        self._notify("stimulsoft", PrereqStatus.INSTALLING, "در حال نصب سایلنت Stimulsoft...")
        logger.log("PREREQ", "STIMULSOFT", "INSTALLING", f"نصب فایل {msi_path}")

        try:
            cmd = ["msiexec.exe", "/i", str(msi_path), "/qn", "/norestart"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if res.returncode in [0, 3010]:
                self._notify("stimulsoft", PrereqStatus.COMPLETED, "با موفقیت نصب شد.")
                logger.log("PREREQ", "STIMULSOFT", "SUCCESS", "نصب Stimulsoft انجام شد.", exit_code=res.returncode)
                return True
            else:
                self._notify("stimulsoft", PrereqStatus.FAILED, f"خطای کد خروج {res.returncode}")
                logger.log("PREREQ", "STIMULSOFT", "ERROR", f"کد خروج: {res.returncode}", exit_code=res.returncode)
                return False
        except Exception as ex:
            self._notify("stimulsoft", PrereqStatus.FAILED, str(ex))
            logger.log("PREREQ", "STIMULSOFT", "ERROR", f"اکسپشن: {ex}", error=str(ex))
            return False

    def install_farsi_fonts(self) -> bool:
        """بررسی و ثبت فونت‌های فارسی در رجیستری ویندوز"""
        self._notify("farsi_fonts", PrereqStatus.CHECKING, "در حال بررسی و ثبت فونت‌ها...")
        logger.log("PREREQ", "FONTS", "CHECKING", "ثبت فونت‌های فارسی سیستم")

        fonts_installed = 0
        windir = os.environ.get("WINDIR", r"C:\Windows")
        win_fonts_dir = Path(windir) / "Fonts"

        # جستجوی فونت‌های موجود در SETUP و ریشه
        font_files: List[Path] = []

        iransans_dir = SETUP_DIR / "IRANSans"
        if iransans_dir.exists():
            font_files.extend(list(iransans_dir.rglob("*.ttf")))
            font_files.extend(list(iransans_dir.rglob("*.otf")))

        bfont_dir = SETUP_DIR / "Farsi Font B_2"
        if bfont_dir.exists():
            font_files.extend(list(bfont_dir.rglob("*.ttf")))
            font_files.extend(list(bfont_dir.rglob("*.otf")))

        arad_font = BASE_DIR / "AradVF.ttf"
        if arad_font.exists():
            font_files.append(arad_font)

        self._notify("farsi_fonts", PrereqStatus.INSTALLING, f"ثبت {len(font_files)} فونت فارسی...")

        for font_path in font_files:
            try:
                dest_file = win_fonts_dir / font_path.name
                if not dest_file.exists():
                    shutil.copy2(font_path, dest_file)

                # ثبت در رجیستری ویندوز
                font_name = font_path.stem
                if font_path.suffix.lower() == ".ttf":
                    reg_font_name = f"{font_name} (TrueType)"
                else:
                    reg_font_name = f"{font_name} (OpenType)"

                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
                        0,
                        winreg.KEY_SET_VALUE
                    ) as key:
                        winreg.SetValueEx(key, reg_font_name, 0, winreg.REG_SZ, font_path.name)
                except Exception:
                    # در صورت عدم دسترسی ادمین به HKLM، در HKCU ثبت می‌شود
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
                        0,
                        winreg.KEY_SET_VALUE
                    ) as key:
                        winreg.SetValueEx(key, reg_font_name, 0, winreg.REG_SZ, str(dest_file))

                # فراخوانی AddFontResourceW ویندوز
                try:
                    ctypes.windll.gdi32.AddFontResourceW(str(dest_file if dest_file.exists() else font_path))
                except Exception:
                    pass

                fonts_installed += 1
            except Exception as ex:
                logger.log("PREREQ", "FONTS", "WARN", f"خطا در ثبت فونت {font_path.name}: {ex}")

        # اطلاع به کل ویندوز جهت رفرش فونت‌ها
        try:
            HWND_BROADCAST = 0xFFFF
            WM_FONTCHANGE = 0x001D
            ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0, 0, 1000, None)
        except Exception:
            pass

        msg = f"{fonts_installed} فونت با موفقیت ثبت شد."
        if not font_files or fonts_installed != len(font_files):
            msg += " ثبت همه فونت‌های موردنیاز انجام نشد."
            self._notify("farsi_fonts", PrereqStatus.FAILED, msg)
            logger.log("PREREQ", "FONTS", "ERROR", msg)
            return False
        self._notify("farsi_fonts", PrereqStatus.COMPLETED, msg)
        logger.log("PREREQ", "FONTS", "SUCCESS", msg)
        return True

    def install_all(self) -> bool:
        """اجرای ترتیبی نصب تمام پیش‌نیازها با تصمیم‌گیری هوش مصنوعی"""
        from ai.sepehryar_setup_ai import setup_ai
        needed_prereqs = setup_ai.check_prerequisites()
        
        r1 = self.install_crystal_reports()
        r2 = self.install_stimulsoft()
        
        r3 = True
        if "SystemFonts" in needed_prereqs:
            r3 = self.install_farsi_fonts()
        else:
            self._notify("farsi_fonts", PrereqStatus.ALREADY_INSTALLED, "فونت‌ها توسط AI شناسایی و تایید شد.")
            logger.log("PREREQ", "FONTS", "SKIPPED", "فونت‌ها از قبل نصب شده‌اند (تشخیص AI)")
            
        return r1 and r2 and r3
