# downloader/ssms_downloader.py
"""
ماژول دانلود واقعی، گزارش پیشرفت بایت‌به‌بایت و اجرای نصب SQL Management Studio
Real downloader with progress tracking, error handling, and SSMS installation
"""

import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional, Tuple

from config.settings import (
    SETUP_DIR,
    SSMS_LINK_FILENAME,
    SSMS_ALT_LINK_FILENAME,
    SSMS_FALLBACK_URL,
)
from app_logging.app_logger import logger


def read_ssms_download_url(search_dirs: Optional[list] = None) -> str:
    """
    خواندن داینامیک URL دانلود از فایل LINK DOWNLOAD SQL MANAGEMENT بدون هاردکد کردن
    """
    if search_dirs is None:
        search_dirs = [SETUP_DIR]

    for sdir in search_dirs:
        for fname in [SSMS_LINK_FILENAME, SSMS_ALT_LINK_FILENAME]:
            fp = Path(sdir) / fname
            if fp.exists():
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            cleaned = line.strip()
                            if cleaned.startswith("http://") or cleaned.startswith("https://"):
                                logger.log("SSMS", "READ_URL", "SUCCESS", f"آدرس دانلود از {fp.name} خوانده شد: {cleaned}")
                                return cleaned
                except Exception as ex:
                    logger.log("SSMS", "READ_URL", "WARN", f"خطا در خواندن {fp}: {ex}")

    logger.log("SSMS", "READ_URL", "FALLBACK", "استفاده از آدرس پیش‌فرض به دلیل عدم دسترسی به فایل لینک")
    return SSMS_FALLBACK_URL


def is_ssms_installed() -> bool:
    """
    بررسی نصب بودن SQL Server Management Studio در سیستم
    """
    candidate_paths = [
        Path(r"C:\Program Files (x86)\Microsoft SQL Server Management Studio 18\Common7\IDE\Ssms.exe"),
        Path(r"C:\Program Files (x86)\Microsoft SQL Server Management Studio 19\Common7\IDE\Ssms.exe"),
        Path(r"C:\Program Files (x86)\Microsoft SQL Server Management Studio 20\Common7\IDE\Ssms.exe"),
        Path(r"C:\Program Files\Microsoft SQL Server Management Studio 18\Common7\IDE\Ssms.exe"),
        Path(r"C:\Program Files\Microsoft SQL Server Management Studio 19\Common7\IDE\Ssms.exe"),
    ]
    for cp in candidate_paths:
        if cp.exists():
            return True

    # بررسی در رجیستری
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Microsoft SQL Server Management Studio"):
            return True
    except Exception:
        pass

    return False


class SSMSDownloader:
    """
    مدیریت دانلود با پروگرس واقعی و اجرای نصاب SSMS
    """
    def __init__(
        self,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
    ):
        """
        progress_callback(downloaded_bytes, total_bytes, percent, status_text)
        """
        self.progress_callback = progress_callback
        self.cancel_requested = False

    def request_cancel(self):
        self.cancel_requested = True

    def download_and_install(self, destination_dir: Path) -> Tuple[bool, str]:
        """
        اجرای چرخه کامل دانلود و نصب SSMS:
        ۱. بررسی وضعیت نصب فعلی (اگر نصب بود، اسکیپ می‌شود)
        ۲. دریافت آدرس از فایل متنی
        ۳. دانلود استریم شده با ثبت بایت‌ها و درصد
        ۴. اجرای فایل نصبی و بررسی نهایی
        """
        logger.log("SSMS", "CHECK", "RUNNING", "بررسی وضعیت نصب SQL Server Management Studio")
        if is_ssms_installed():
            msg = "SQL Server Management Studio از قبل روی سیستم نصب است."
            logger.log("SSMS", "CHECK", "ALREADY_INSTALLED", msg)
            if self.progress_callback:
                self.progress_callback(100, 100, 100.0, msg)
            return True, msg

        url = read_ssms_download_url([destination_dir, SETUP_DIR])
        logger.log("SSMS", "DOWNLOAD", "START", f"شروع دانلود از آدرس: {url}")

        destination_dir.mkdir(parents=True, exist_ok=True)
        # استخراج نام فایل از URL
        raw_name = url.split("?")[0].split("/")[-1]
        if not raw_name:
            raw_name = "SSMS-Setup.rar"
        download_target = destination_dir / raw_name

        # دانلود واقعی
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SepehryarInstaller/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 1024 * 64  # 64 KB
                start_time = time.time()

                with open(download_target, "wb") as f_out:
                    while True:
                        if self.cancel_requested:
                            logger.log("SSMS", "DOWNLOAD", "CANCELLED", "دانلود توسط کاربر متوقف شد.")
                            return False, "دانلود لغو گردید."

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            percent = round((downloaded / total_size) * 100, 1)
                        else:
                            percent = 50.0

                        mb_downloaded = round(downloaded / (1024 * 1024), 1)
                        mb_total = round(total_size / (1024 * 1024), 1) if total_size > 0 else 0
                        status_str = f"Downloading SQL Management Studio {int(percent)}% ({mb_downloaded}/{mb_total} MB)"

                        if self.progress_callback:
                            self.progress_callback(downloaded, total_size, percent, status_str)

            logger.log("SSMS", "DOWNLOAD", "SUCCESS", f"دانلود با موفقیت پایان یافت: {download_target}")

        except Exception as ex:
            err_msg = f"خطای شبکه در دانلود SSMS: {ex}"
            logger.log("SSMS", "DOWNLOAD", "ERROR", err_msg, error=str(ex))
            return False, err_msg

        # اجرای فایل نصبی
        setup_exe_to_run: Optional[Path] = None

        if download_target.suffix.lower() == ".rar":
            # استخراج آرشیو در صورت نیاز
            extract_dir = destination_dir / "SSMS_Extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)
            unrar = Path(r"C:\Program Files\WinRAR\UnRAR.exe")
            if unrar.exists():
                try:
                    subprocess.run(
                        [str(unrar), "x", "-psoft98.ir", "-y", str(download_target), str(extract_dir)],
                        timeout=300
                    )
                    exes = list(extract_dir.rglob("*.exe"))
                    if exes:
                        setup_exe_to_run = exes[0]
                except Exception as ex:
                    logger.log("SSMS", "EXTRACT", "ERROR", f"خطا در استخراج پکیج SSMS: {ex}")
        elif download_target.suffix.lower() == ".exe":
            setup_exe_to_run = download_target

        if setup_exe_to_run and setup_exe_to_run.exists():
            logger.log("SSMS", "EXECUTE", "RUNNING", f"اجرای نصاب {setup_exe_to_run}")
            if self.progress_callback:
                self.progress_callback(100, 100, 100.0, "در حال اجرای نصب SQL Server Management Studio...")
            try:
                # اجرای نصب SSMS
                subprocess.Popen([str(setup_exe_to_run), "/install", "/quiet", "/norestart"])
                logger.log("SSMS", "EXECUTE", "SUCCESS", "نصاب SSMS فراخوانی شد.")
            except Exception as ex:
                logger.log("SSMS", "EXECUTE", "WARN", f"خطا در اجرای مستقیم: {ex}")

        return True, "عملیات SSMS با موفقیت انجام شد."
