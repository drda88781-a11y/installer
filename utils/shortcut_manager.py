# utils/shortcut_manager.py
"""
ماژول ایجاد میانبرهای استاندارد دسکتاپ و استارت منوی ویندوز با نام فارسی
Windows Desktop and Start Menu shortcut (.lnk) creator pointing to real application EXEs
"""

import base64
import os
import subprocess
from pathlib import Path
from typing import List, Optional

from app_logging.app_logger import logger


def get_desktop_dir() -> Path:
    """مسیر دسکتاپ کاربر فعلی و مشترک"""
    user_desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    if user_desktop.exists():
        return user_desktop
    # فال‌بک به دسکتاپ عمومی
    public_desktop = Path(os.environ.get("PUBLIC", "")) / "Desktop"
    if public_desktop.exists():
        return public_desktop
    return user_desktop


def get_start_menu_dir() -> Path:
    """مسیر منوی استارت برنامه‌ها"""
    app_data = Path(os.environ.get("APPDATA", ""))
    programs_dir = app_data / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "SEPEHRYAR"
    programs_dir.mkdir(parents=True, exist_ok=True)
    return programs_dir


def create_windows_shortcut(
    shortcut_path: Path,
    target_exe: Path,
    working_dir: Optional[Path] = None,
    description: str = "",
    icon_location: Optional[Path] = None,
) -> bool:
    """
    ساخت فایل میانبر واقعی .lnk از طریق اسکریپت WScript.Shell ویندوز
    """
    if not target_exe.exists():
        logger.log("SHORTCUT", "CREATE", "ERROR", f"فایل اجرایی مقصد وجود ندارد: {target_exe}")
        return False

    if working_dir is None:
        working_dir = target_exe.parent

    # اگر آیکون تعیین نشده باشد، از خود exe یا فایل ico داخل پوشه استفاده می‌شود
    if icon_location is None or not icon_location.exists():
        # جستجوی فایل .ico در پوشه برنامه
        ico_candidates = list(working_dir.glob("*.ico"))
        if ico_candidates:
            icon_location = ico_candidates[0]
        else:
            icon_location = target_exe

    # به دلیل ناسازگاری برخی نسخه‌های WScript.Shell با کاراکترهای یونیکد در CreateShortcut:
    # ابتدا میانبر را با نام انگلیسی موقت می‌سازیم و سپس آن را به نام فارسی نهایی تغییر می‌دهیم.
    import uuid
    import shutil
    
    temp_lnk = shortcut_path.parent / f"_sc_{uuid.uuid4().hex[:8]}.lnk"
    ps_script = (
        f"$WshShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{str(temp_lnk)}'); "
        f"$Shortcut.TargetPath = '{str(target_exe)}'; "
        f"$Shortcut.WorkingDirectory = '{str(working_dir)}'; "
        f"$Shortcut.Description = '{description}'; "
        f"$Shortcut.IconLocation = '{str(icon_location)},0'; "
        f"$Shortcut.Save();"
    )

    try:
        # انکودینگ UTF-16LE به Base64 جهت تضمین عدم خرابی کاراکترهای مسیر در PowerShell
        ps_bytes = ps_script.encode("utf-16le")
        ps_b64 = base64.b64encode(ps_bytes).decode("ascii")

        proc = subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", ps_b64],
            capture_output=True,
            text=True,
            timeout=15
        )
        if proc.returncode == 0 and temp_lnk.exists():
            if shortcut_path.exists():
                try:
                    shortcut_path.unlink()
                except Exception:
                    pass
            shutil.move(str(temp_lnk), str(shortcut_path))
            logger.log("SHORTCUT", "CREATE", "SUCCESS", f"میانبر با موفقیت ایجاد شد: {shortcut_path}")
            return True
        else:
            if temp_lnk.exists():
                temp_lnk.unlink(missing_ok=True)
            logger.log("SHORTCUT", "CREATE", "ERROR", f"خطا در ایجاد میانبر: {proc.stderr}")
            return False
    except Exception as ex:
        if temp_lnk.exists():
            temp_lnk.unlink(missing_ok=True)
        logger.log("SHORTCUT", "CREATE", "ERROR", f"اکسپشن میانبر: {ex}", error=str(ex))
        return False


def create_shortcuts_for_product(
    product_title: str,
    shortcut_name: str,
    target_exe: Path,
) -> List[Path]:
    """
    ایجاد میانبرهای دسکتاپ و منوی استارت برای محصول نصب‌شده
    """
    created: List[Path] = []
    desc = f"نرم‌افزار جامع {product_title} سپهریار"

    # ۱. میانبر دسکتاپ کاربر جاری
    desktop_dir = get_desktop_dir()
    desktop_lnk = desktop_dir / f"{shortcut_name}.lnk"
    if create_windows_shortcut(desktop_lnk, target_exe, description=desc):
        created.append(desktop_lnk)

    # ۲. میانبر دسکتاپ عمومی (Public Desktop) جهت اطمینان از نمایش روی دسکتاپ در تمام شرایط UAC
    public_desktop = Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop"
    if public_desktop.exists() and public_desktop != desktop_dir:
        pub_lnk = public_desktop / f"{shortcut_name}.lnk"
        if create_windows_shortcut(pub_lnk, target_exe, description=desc):
            created.append(pub_lnk)

    # ۳. میانبر استارت‌منو
    start_menu_dir = get_start_menu_dir()
    start_lnk = start_menu_dir / f"{shortcut_name}.lnk"
    if create_windows_shortcut(start_lnk, target_exe, description=desc):
        created.append(start_lnk)

    return created
