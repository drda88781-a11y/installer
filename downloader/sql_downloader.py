# downloader/sql_downloader.py
"""
ماژول دانلود آنلاین، استخراج و نصب خودکار SQL Server 2019 Enterprise
Online download, extraction, and automated installation of SQL Server 2019 Enterprise
- دانلود استریم با گزارش پیشرفت بایت‌به‌بایت
- استخراج آرشیو RAR رمزدار
- مانت ISO و نصب سایلنت
"""

import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional, Tuple

from app_logging.app_logger import logger


# آدرس‌های پیش‌فرض دانلود SQL Server
SQL_DOWNLOAD_URLS = {
    "2019": {
        "enterprise": "https://dl2.soft98.ir/programing/Microsoft.SQL.Server.2019.Enterprise.x64.rar?1790685163",
        "archive_name": "Microsoft.SQL.Server.2019.Enterprise.x64.rar",
        "archive_pass": "soft98.ir",
    },
}


def get_sql_download_config(sql_version: str = "2019") -> dict:
    """دریافت پیکربندی دانلود برای نسخه مشخص SQL Server"""
    return SQL_DOWNLOAD_URLS.get(sql_version, SQL_DOWNLOAD_URLS["2019"])


class SQLOnlineDownloader:
    """
    مدیریت دانلود آنلاین SQL Server با پروگرس واقعی، استخراج و آماده‌سازی
    """
    def __init__(
        self,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
        sql_version: str = "2019",
    ):
        """
        progress_callback(downloaded_bytes, total_bytes, percent, status_text)
        """
        self.progress_callback = progress_callback
        self.sql_version = sql_version
        self.cancel_requested = False
        self.config = get_sql_download_config(sql_version)

    def request_cancel(self):
        self.cancel_requested = True

    def _notify(self, downloaded: int, total: int, percent: float, status: str):
        if self.progress_callback:
            self.progress_callback(downloaded, total, percent, status)

    def _find_unrar(self) -> Optional[Path]:
        """یافتن ابزار اکسترکت UnRAR، WinRAR یا 7-Zip"""
        candidates = [
            Path(r"C:\Program Files\WinRAR\UnRAR.exe"),
            Path(r"C:\Program Files\WinRAR\WinRAR.exe"),
            Path(r"C:\Program Files (x86)\WinRAR\UnRAR.exe"),
            Path(r"C:\Program Files\7-Zip\7z.exe"),
        ]
        for c in candidates:
            if c.exists():
                return c
        which_unrar = shutil.which("unrar")
        if which_unrar:
            return Path(which_unrar)
        return None

    def is_archive_available_locally(self, search_dirs: list) -> Optional[Path]:
        """
        بررسی وجود آرشیو SQL Server در مسیرهای محلی
        اگر قبلاً دانلود شده یا در SETUP موجود باشد برگردانده می‌شود
        """
        archive_name = self.config["archive_name"]
        for sdir in search_dirs:
            candidate = Path(sdir) / archive_name
            if candidate.exists():
                logger.log("SQL_DL", "LOCAL_CHECK", "FOUND",
                           f"آرشیو SQL Server در مسیر محلی یافت شد: {candidate}")
                return candidate
        return None

    def download_archive(self, destination_dir: Path) -> Tuple[bool, Path, str]:
        """
        دانلود فایل آرشیو SQL Server با پروگرس واقعی
        Returns: (success, file_path, message)
        """
        url = self.config["enterprise"]
        archive_name = self.config["archive_name"]
        destination_dir.mkdir(parents=True, exist_ok=True)
        download_target = destination_dir / archive_name

        # اگر قبلاً دانلود شده
        if download_target.exists():
            existing_size_mb = round(download_target.stat().st_size / (1024 * 1024), 1)
            if existing_size_mb > 100:  # حداقل باید 100 مگ باشد
                logger.log("SQL_DL", "DOWNLOAD", "SKIP",
                           f"آرشیو موجود: {download_target} ({existing_size_mb} MB)")
                self._notify(100, 100, 100.0,
                             f"فایل SQL Server قبلاً دانلود شده ({existing_size_mb} MB)")
                return True, download_target, "فایل SQL Server از قبل موجود است."

        logger.log("SQL_DL", "DOWNLOAD", "START",
                   f"شروع دانلود SQL Server {self.sql_version} از: {url}")
        self._notify(0, 0, 0.0, "در حال اتصال به سرور دانلود...")

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "SepehryarInstaller/2026.1"
                },
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 1024 * 128  # 128 KB chunks
                start_time = time.time()

                total_mb = round(total_size / (1024 * 1024), 1) if total_size > 0 else 0
                self._notify(0, total_size, 0.0,
                             f"دانلود SQL Server {self.sql_version} — 0/{total_mb} MB")

                # ذخیره به فایل موقت و بعد rename (جلوگیری از فایل ناقص)
                temp_target = download_target.with_suffix(".downloading")

                with open(temp_target, "wb") as f_out:
                    while True:
                        if self.cancel_requested:
                            logger.log("SQL_DL", "DOWNLOAD", "CANCELLED",
                                       "دانلود SQL Server توسط کاربر متوقف شد.")
                            try:
                                temp_target.unlink()
                            except Exception:
                                pass
                            return False, download_target, "دانلود لغو گردید."

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            percent = round((downloaded / total_size) * 100, 1)
                        else:
                            percent = 50.0

                        mb_dl = round(downloaded / (1024 * 1024), 1)
                        elapsed = time.time() - start_time
                        speed_mbps = round(mb_dl / elapsed, 1) if elapsed > 0.5 else 0

                        status = (
                            f"دانلود SQL Server {int(percent)}%  "
                            f"({mb_dl}/{total_mb} MB)  "
                            f"سرعت: {speed_mbps} MB/s"
                        )
                        self._notify(downloaded, total_size, percent, status)

                # تبدیل فایل موقت به نهایی
                if download_target.exists():
                    download_target.unlink()
                temp_target.rename(download_target)

            final_mb = round(download_target.stat().st_size / (1024 * 1024), 1)
            logger.log("SQL_DL", "DOWNLOAD", "SUCCESS",
                       f"دانلود SQL Server با موفقیت انجام شد: {final_mb} MB")
            self._notify(total_size, total_size, 100.0,
                         f"دانلود SQL Server {self.sql_version} تکمیل شد ({final_mb} MB)")
            return True, download_target, f"دانلود موفق — {final_mb} MB"

        except Exception as ex:
            err_msg = f"خطای شبکه در دانلود SQL Server: {ex}"
            logger.log("SQL_DL", "DOWNLOAD", "ERROR", err_msg, error=str(ex))
            # پاکسازی فایل ناقص
            temp_target = download_target.with_suffix(".downloading")
            for f in [temp_target, download_target]:
                try:
                    if f.exists() and f.stat().st_size < 1024 * 1024:
                        f.unlink()
                except Exception:
                    pass
            return False, download_target, err_msg

    def extract_and_prepare(
        self,
        archive_path: Path,
        extract_dir: Path,
    ) -> Tuple[bool, str]:
        """
        استخراج آرشیو RAR رمزدار و آماده‌سازی فایل‌های نصب
        Returns: (success, message)
        """
        archive_pass = self.config["archive_pass"]

        unrar_exe = self._find_unrar()
        if not unrar_exe:
            err = "ابزار UnRAR/WinRAR/7-Zip جهت استخراج پکیج SQL Server یافت نشد."
            logger.log("SQL_DL", "EXTRACT", "ERROR", err)
            return False, err

        extract_dir.mkdir(parents=True, exist_ok=True)

        self._notify(0, 100, 30.0, "در حال استخراج بسته نصبی SQL Server...")
        logger.log("SQL_DL", "EXTRACT", "RUNNING",
                   f"استخراج {archive_path.name} با {unrar_exe.name}")

        try:
            if "7z" in unrar_exe.name.lower():
                cmd = [
                    str(unrar_exe), "x",
                    f"-p{archive_pass}", "-y",
                    f"-o{extract_dir}",
                    str(archive_path),
                ]
            else:
                cmd = [
                    str(unrar_exe), "x",
                    f"-p{archive_pass}", "-y",
                    str(archive_path),
                    str(extract_dir) + "\\",
                ]

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if proc.returncode != 0:
                err = f"خطای استخراج آرشیو SQL Server (کد: {proc.returncode})"
                logger.log("SQL_DL", "EXTRACT", "ERROR", err)
                return False, err

        except subprocess.TimeoutExpired:
            err = "عملیات استخراج بیش از ۱۰ دقیقه طول کشید و متوقف شد."
            logger.log("SQL_DL", "EXTRACT", "TIMEOUT", err)
            return False, err
        except Exception as ex:
            err = f"خطا در استخراج آرشیو: {ex}"
            logger.log("SQL_DL", "EXTRACT", "ERROR", err, error=str(ex))
            return False, err

        self._notify(0, 100, 60.0, "استخراج SQL Server با موفقیت انجام شد.")
        logger.log("SQL_DL", "EXTRACT", "SUCCESS", "بسته نصبی SQL Server با موفقیت استخراج گردید.")
        return True, "استخراج موفق."

    def download_extract_flow(
        self,
        destination_dir: Path,
        local_search_dirs: Optional[list] = None,
    ) -> Tuple[bool, Optional[Path], str]:
        """
        فلوی کامل: بررسی محلی → دانلود → استخراج
        Returns: (success, archive_path, message)
        """
        # ابتدا بررسی آیا آرشیو از قبل موجود هست
        search = local_search_dirs or [destination_dir]
        existing = self.is_archive_available_locally(search)

        if existing:
            archive_path = existing
            self._notify(100, 100, 100.0, "آرشیو SQL Server از مسیر محلی بارگذاری شد.")
        else:
            # دانلود آنلاین
            ok, archive_path, msg = self.download_archive(destination_dir)
            if not ok:
                return False, None, msg

        # استخراج
        extract_dir = destination_dir / "SQL_Extracted"
        ok, msg = self.extract_and_prepare(archive_path, extract_dir)
        if not ok:
            return False, None, msg

        return True, archive_path, "دانلود و استخراج SQL Server با موفقیت انجام شد."
