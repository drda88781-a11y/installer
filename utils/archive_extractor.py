# utils/archive_extractor.py
"""
ماژول جامع و چندلایه استخراج آرشیوهای به‌روزرسانی و مدیریت پروسه‌های قفل‌کننده
Multi-tier universal archive extractor (ZIP, RAR, 7Z, SQL) and process unlocking manager
"""

import os
import sys
from pathlib import Path
import shutil
import subprocess
import time
from typing import Callable, Dict, List, Optional, Tuple
import winreg
import zipfile

import psutil

from app_logging.app_logger import logger


class ArchiveInspectionResult:
    """گزارش ارزیابی محتوای بسته به‌روزرسانی قبل از استخراج"""
    def __init__(self):
        self.archive_path: Optional[Path] = None
        self.file_type: str = "UNKNOWN"  # ZIP, RAR, 7Z, SQL, UNKNOWN
        self.is_valid: bool = False
        self.total_size_bytes: int = 0
        self.total_files_count: int = 0
        self.has_files_folder: bool = False
        self.has_data_folder: bool = False
        self.mdf_files: List[str] = []
        self.ldf_files: List[str] = []
        self.sql_files: List[str] = []
        self.exe_files: List[str] = []
        self.version_hint: str = "نامشخص"
        self.message: str = ""
        self.warnings: List[str] = []


def find_archive_tool() -> Optional[Tuple[str, Path]]:
    """
    یافتن هوشمند ابزارهای اکسترکت نصب شده در سیستم (WinRAR یا 7-Zip یا UnRAR)
    خروجی: (نوع ابزار 'winrar'/'7z', مسیر فایل اجرایی)
    """
    # ۰. جستجو در ابزارهای داخلی همراه اینستالر (Bundled Tools)
    current_dir = Path(__file__).resolve().parent
    base_dir = current_dir.parent
    bundled = [
        ("winrar", current_dir / "UnRAR.exe"),
        ("winrar", base_dir / "assets" / "bin" / "UnRAR.exe"),
    ]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        bundled.insert(0, ("winrar", meipass / "UnRAR.exe"))
        bundled.insert(1, ("winrar", meipass / "assets" / "bin" / "UnRAR.exe"))
        bundled.insert(2, ("winrar", meipass / "utils" / "UnRAR.exe"))

    for kind, p in bundled:
        if p.exists() and p.is_file():
            return kind, p

    # ۱. جستجو در مسیرهای مستقیم معروف
    candidates = [
        ("winrar", Path(r"C:\Program Files\WinRAR\UnRAR.exe")),
        ("winrar", Path(r"C:\Program Files\WinRAR\WinRAR.exe")),
        ("winrar", Path(r"C:\Program Files (x86)\WinRAR\UnRAR.exe")),
        ("winrar", Path(r"C:\Program Files (x86)\WinRAR\WinRAR.exe")),
        ("7z", Path(r"C:\Program Files\7-Zip\7z.exe")),
        ("7z", Path(r"C:\Program Files (x86)\7-Zip\7z.exe")),
    ]
    for kind, p in candidates:
        if p.exists() and p.is_file():
            return kind, p

    # ۲. جستجو در رجیستری ویندوز (App Paths)
    reg_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\WinRAR.exe", "winrar"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\7z.exe", "7z"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\WinRAR.exe", "winrar"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\7z.exe", "7z"),
    ]
    for root, rpath, kind in reg_keys:
        try:
            with winreg.OpenKey(root, rpath) as key:
                val, _ = winreg.QueryValueEx(key, "")
                if val and Path(val).exists():
                    return kind, Path(val)
        except OSError:
            pass

    # ۳. بررسی متغیر محیطی PATH
    for cmd, kind in [("unrar", "winrar"), ("winrar", "winrar"), ("7z", "7z")]:
        which_p = shutil.which(cmd)
        if which_p:
            return kind, Path(which_p)

    return None


def inspect_archive(archive_path: Path) -> ArchiveInspectionResult:
    """
    بررسی دقیق محتوای فایل بسته بدون نیاز به استخراج کامل:
    - تشخیص فایل‌های ZIP
    - تشخیص فایل‌های RAR
    - تشخیص اسکریپت‌های مستقیم SQL Patch (.sql)
    """
    res = ArchiveInspectionResult()
    res.archive_path = archive_path

    if not archive_path.exists():
        res.message = "فایل یا پوشه انتخاب‌شده در مسیر مشخص‌شده وجود ندارد."
        return res

    if archive_path.is_dir():
        res.file_type = "DIR"
        res.is_valid = True
        all_entries = list(archive_path.rglob("*"))
        files = [f for f in all_entries if f.is_file()]
        res.total_files_count = len(files)
        res.total_size_bytes = sum(f.stat().st_size for f in files)
        res.has_files_folder = any(d.is_dir() and d.name.lower() == "files" for d in all_entries)
        res.has_data_folder = any(d.is_dir() and d.name.lower() == "data" for d in all_entries)
        res.mdf_files = [f.name for f in files if f.suffix.lower() == ".mdf"]
        res.ldf_files = [f.name for f in files if f.suffix.lower() == ".ldf"]
        res.sql_files = [f.name for f in files if f.suffix.lower() == ".sql"]
        res.exe_files = [f.name for f in files if f.suffix.lower() == ".exe"]
        res.message = f"پوشه به‌روزرسانی شامل {res.total_files_count} فایل"
        return res

    res.total_size_bytes = archive_path.stat().st_size
    suffix = archive_path.suffix.lower()

    # ۱. حالت اسکریپت مستقیم SQL
    if suffix == ".sql":
        res.file_type = "SQL"
        res.is_valid = True
        res.sql_files = [archive_path.name]
        res.message = f"فایل پچ اسکریپت پایگاه داده: {archive_path.name}"
        return res

    # ۲. حالت ZIP
    if zipfile.is_zipfile(archive_path) or suffix == ".zip":
        res.file_type = "ZIP"
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                infolist = zf.infolist()
                res.total_files_count = len(infolist)
                for item in infolist:
                    clean_name = item.filename.replace("\\", "/")
                    parts = [p for p in clean_name.split("/") if p]
                    if not parts:
                        continue
                    root_folder = parts[0].lower()
                    if root_folder == "files":
                        res.has_files_folder = True
                    elif root_folder == "data":
                        res.has_data_folder = True

                    fname = parts[-1].lower()
                    if fname.endswith(".exe"):
                        res.exe_files.append(parts[-1])
                    elif fname.endswith(".mdf"):
                        res.mdf_files.append(parts[-1])
                    elif fname.endswith(".ldf"):
                        res.ldf_files.append(parts[-1])
                    elif fname.endswith(".sql"):
                        res.sql_files.append(parts[-1])

                res.is_valid = True
                res.message = f"آرشیو معتبر ZIP شامل {res.total_files_count} فایل"
                return res
        except Exception as ex:
            res.warnings.append(f"هشدار در خواندن ZIP: {ex}")

    # ۳. حالت RAR یا سایر فشرده‌سازها
    if suffix in [".rar", ".7z"]:
        res.file_type = "RAR" if suffix == ".rar" else "7Z"
        tool_info = find_archive_tool()
        if tool_info:
            kind, tool_path = tool_info
            # تلاش برای خواندن فهرست محتویات بدون استخراج کامل
            try:
                if kind == "7z":
                    cmd = [str(tool_path), "l", str(archive_path)]
                else:
                    cmd = [str(tool_path), "lb", str(archive_path)]

                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if proc.returncode == 0:
                    lines = proc.stdout.splitlines()
                    for line in lines:
                        clean_line = line.strip().replace("\\", "/")
                        if not clean_line:
                            continue
                        lower_line = clean_line.lower()
                        if "files/" in lower_line or lower_line.startswith("files"):
                            res.has_files_folder = True
                        if "data/" in lower_line or lower_line.startswith("data"):
                            res.has_data_folder = True

                        fname = clean_line.split("/")[-1]
                        fl = fname.lower()
                        if fl.endswith(".exe"):
                            res.exe_files.append(fname)
                        elif fl.endswith(".mdf"):
                            res.mdf_files.append(fname)
                        elif fl.endswith(".ldf"):
                            res.ldf_files.append(fname)
                        elif fl.endswith(".sql"):
                            res.sql_files.append(fname)

                    res.total_files_count = len(lines)
            except Exception as ex:
                res.warnings.append(f"امکان خواندن سریع ساختار RAR فراهم نشد: {ex}")

        res.is_valid = True
        res.message = f"آرشیو {res.file_type}: {archive_path.name}"
        return res

    # فایل ناشناخته یا فشرده دیگر
    res.file_type = suffix.upper().replace(".", "") or "UNKNOWN"
    res.is_valid = True
    res.message = f"فایل پکیج: {archive_path.name}"
    return res


def extract_archive_universal(
    archive_path: Path,
    dest_dir: Path,
    password: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> Tuple[bool, str]:
    r"""
    استخراج هوشمند و چندلایه انواع فایل‌های فشرده (ZIP, RAR, 7Z):
    - لایه ۱: ماژول درونی پایتون zipfile (کاملاً مستقل و بدون نیاز به هیچ ابزار خارجی برای فایلهای زیپ)
    - لایه ۲: ابزار درونی tar.exe در ویندوز ۱۰ و ۱۱ (C:\Windows\System32\tar.exe)
    - لایه ۳: دستور بومی پاورشل Expand-Archive
    - لایه ۴: استفاده از WinRAR یا 7-Zip در صورت وجود در سیستم برای فایلهای RAR
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = archive_path.suffix.lower()

    if progress_callback:
        progress_callback(f"در حال آماده‌سازی استخراج {archive_path.name}...", 10)

    # =========================================================================
    # استراتژی اول: فایل‌های ZIP با ماژول داخلی پایتون (Zero Dependency)
    # =========================================================================
    if zipfile.is_zipfile(archive_path) or suffix == ".zip":
        logger.log("EXTRACTOR", "ZIPFILE", "RUNNING", f"استخراج با zipfile داخلی پایتون: {archive_path.name}")
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                members = zf.infolist()
                total = len(members)
                pwd_bytes = password.encode("utf-8") if password else None

                for idx, member in enumerate(members):
                    # جلوگیری از Path Traversal / Zip Slip
                    target_path = dest_dir / member.filename
                    try:
                        target_path.resolve().relative_to(dest_dir.resolve())
                    except ValueError:
                        continue

                    zf.extract(member, path=dest_dir, pwd=pwd_bytes)
                    if progress_callback and total > 0 and idx % max(1, total // 10) == 0:
                        pct = 20 + int((idx / total) * 75)
                        progress_callback(f"استخراج: {member.filename.split('/')[-1]}", pct)

            logger.log("EXTRACTOR", "ZIPFILE", "SUCCESS", f"استخراج موفق {total} فایل در {dest_dir}")
            return True, f"تعداد {total} فایل با موفقیت استخراج شد."
        except Exception as ex_zip:
            logger.log("EXTRACTOR", "ZIPFILE", "WARN", f"استخراج با zipfile خطا داد: {ex_zip}. تلاش با متدهای جایگزین...")

    # =========================================================================
    # استراتژی دوم: ابزار درونی ویندوز 10/11 tar.exe
    # =========================================================================
    win_tar = Path(r"C:\Windows\System32\tar.exe")
    if win_tar.exists() and suffix in [".zip", ".tar", ".gz"]:
        logger.log("EXTRACTOR", "WIN_TAR", "RUNNING", f"استخراج با ابزار بومی ویندوز tar.exe: {archive_path.name}")
        try:
            tar_cmd = [str(win_tar), "-xf", str(archive_path), "-C", str(dest_dir)]
            res = subprocess.run(tar_cmd, capture_output=True, text=True, timeout=180)
            if res.returncode == 0:
                logger.log("EXTRACTOR", "WIN_TAR", "SUCCESS", f"استخراج با tar.exe با موفقیت انجام شد.")
                return True, "استخراج فایل با موفقیت انجام شد."
        except Exception as ex_tar:
            logger.log("EXTRACTOR", "WIN_TAR", "WARN", f"خطا در tar.exe: {ex_tar}")

    # =========================================================================
    # استراتژی سوم: استفاده از WinRAR یا 7-Zip
    # =========================================================================
    tool_info = find_archive_tool()
    if tool_info:
        kind, tool_path = tool_info
        logger.log("EXTRACTOR", "EXTERNAL_TOOL", "RUNNING", f"استخراج با {tool_path.name}: {archive_path.name}")
        try:
            if kind == "7z":
                cmd = [str(tool_path), "x", "-y", f"-o{dest_dir}", str(archive_path)]
                if password:
                    cmd.insert(2, f"-p{password}")
            else:
                # WinRAR / UnRAR
                cmd = [str(tool_path), "x", "-y"]
                if password:
                    cmd.append(f"-p{password}")
                cmd.extend([str(archive_path), str(dest_dir)])

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if res.returncode == 0:
                logger.log("EXTRACTOR", "EXTERNAL_TOOL", "SUCCESS", f"استخراج با {tool_path.name} انجام شد.")
                return True, "استخراج بسته با موفقیت پایان یافت."
            else:
                err_text = res.stderr or res.stdout
                logger.log("EXTRACTOR", "EXTERNAL_TOOL", "WARN", f"خروجی ابزار استخراج: {err_text}")
        except Exception as ex_tool:
            logger.log("EXTRACTOR", "EXTERNAL_TOOL", "WARN", f"خطا در اجرای {tool_path.name}: {ex_tool}")

    # =========================================================================
    # استراتژی چهارم: پاورشل Expand-Archive (فقط برای فایلهای ZIP)
    # =========================================================================
    if suffix == ".zip":
        logger.log("EXTRACTOR", "POWERSHELL", "RUNNING", "تلاش نهایی با PowerShell Expand-Archive...")
        try:
            ps_cmd = f"Expand-Archive -Path '{archive_path}' -DestinationPath '{dest_dir}' -Force"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=180)
            if res.returncode == 0:
                logger.log("EXTRACTOR", "POWERSHELL", "SUCCESS", "استخراج با PowerShell با موفقیت انجام شد.")
                return True, "استخراج فایل با موفقیت انجام شد."
        except Exception as ex_ps:
            logger.log("EXTRACTOR", "POWERSHELL", "WARN", f"خطا در PowerShell Expand-Archive: {ex_ps}")

    # در صورت عدم موفقیت و فرمت RAR، راهنمای شفاف تولید شود
    if suffix in [".rar", ".7z"]:
        err_msg = (
            f"برای استخراج فایل فشرده {suffix.upper()}، به نرم‌افزار WinRAR یا 7-Zip نیاز است "
            f"اما این ابزارها روی ویندوز فعلی یافت نشدند.\n\n"
            f"راهکار ساده: لطفاً نرم‌افزار WinRAR را نصب فرمایید یا فایل را به صورت ZIP فشرده نمایید."
        )
    else:
        err_msg = f"عدم امکان استخراج بسته فشرده {archive_path.name} با هیچ‌یک از متدهای سیستم‌عامل."

    logger.log("EXTRACTOR", "FINAL", "ERROR", err_msg)
    return False, err_msg


def close_running_sepehryar_processes() -> Tuple[int, List[str]]:
    """
    شناسایی و بستن ایمن کلیه پروسه‌های باز نرم‌افزار سپهریار جهت آزادسازی فایل‌ها و پیشگیری از خطای WinError 32
    """
    target_exe_names = {
        "hesabdari.exe",
        "sepandresturan.exe",
        "clientsepand.exe",
        "sepandyar_taxgov.exe",
        "sepehryar.exe",
        "cod.exe",
    }
    closed_names: List[str] = []

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            p_name = (proc.info.get("name") or "").lower()
            if p_name in target_exe_names:
                logger.log("PROCESS_UNLOCK", "TERMINATE", "RUNNING", f"بستن پروسه قفل‌کننده: {p_name} (PID: {proc.pid})")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()
                closed_names.append(proc.info.get("name") or p_name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if closed_names:
        logger.log("PROCESS_UNLOCK", "SUMMARY", "SUCCESS", f"تعداد {len(closed_names)} پروسه فعال سپهریار بسته شد: {closed_names}")
    return len(closed_names), closed_names
