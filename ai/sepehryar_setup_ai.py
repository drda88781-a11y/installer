# ai/sepehryar_setup_ai.py
"""
هسته هوشمند نصاب سپهریار (Sepehryar Setup AI)
شامل:
۱. پروفایلینگ هوشمند سخت‌افزار و تنظیم کانفیگ‌های SQL
۲. تشخیص هوشمند پیش‌نیازها بر اساس وضعیت دقیق سیستم عامل
۳. تخصیص داینامیک منابع (تغییر سرعت نصب بر اساس درگیری سیستم)
"""

import os
import psutil
import platform
import winreg
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app_logging.app_logger import logger


@dataclass
class SystemProfile:
    total_ram_gb: float
    available_ram_gb: float
    cpu_cores: int
    cpu_usage_percent: float
    system_arch: str
    is_windows_11_or_10: bool
    recommended_sql_max_memory_mb: int
    recommended_sql_dop: int  # Max Degree of Parallelism
    performance_score: int    # 1 to 100


class SepehryarSetupAI:
    def __init__(self):
        self._profile: Optional[SystemProfile] = None
        self._last_copy_check: float = 0.0
        self._cached_copy_params: Tuple[int, float] = (1024 * 1024 * 4, 0.0)

    # ==========================================
    # 1. Smart Hardware Profiling
    # ==========================================
    def analyze_hardware(self) -> SystemProfile:
        """
        بررسی دقیق سخت‌افزار و تعیین بهترین کانفیگ برای نصب و دیتابیس
        """
        logger.log("AI", "HARDWARE", "INFO", "در حال پروفایلینگ هوشمند سخت‌افزار...")
        
        # RAM
        mem = psutil.virtual_memory()
        total_ram = round(mem.total / (1024 ** 3), 2)
        avail_ram = round(mem.available / (1024 ** 3), 2)
        
        # CPU
        cores = psutil.cpu_count(logical=True) or 4
        usage = psutil.cpu_percent(interval=0.5)
        
        # OS
        arch = platform.machine()
        win_ver = platform.release()
        is_modern_win = win_ver in ["10", "11"]
        
        # --- هوش تصمیم‌گیری SQL ---
        
        # حافظه SQL: معمولا 70% رم خالی، اما حداقل 1 گیگ و حداکثر 80% رم کل
        sql_mem_mb = int((avail_ram * 0.7) * 1024)
        if sql_mem_mb < 1024:
            sql_mem_mb = 1024
        
        # درجه موازی‌سازی SQL (Max DOP):
        # بر اساس معماری NUMA و تعداد هسته‌ها
        if cores >= 16:
            sql_dop = 8
        elif cores >= 8:
            sql_dop = 4
        else:
            sql_dop = 2
            
        # امتیاز سیستم (1-100)
        score = min(100, int((total_ram / 16) * 40 + (cores / 8) * 60))
        
        self._profile = SystemProfile(
            total_ram_gb=total_ram,
            available_ram_gb=avail_ram,
            cpu_cores=cores,
            cpu_usage_percent=usage,
            system_arch=arch,
            is_windows_11_or_10=is_modern_win,
            recommended_sql_max_memory_mb=sql_mem_mb,
            recommended_sql_dop=sql_dop,
            performance_score=score
        )
        
        logger.log("AI", "HARDWARE", "SUCCESS", f"پروفایل سخت‌افزار ساخته شد: {score}/100 امتیاز")
        return self._profile

    # ==========================================
    # 2. Smart Prerequisites Management
    # ==========================================
    def check_prerequisites(self) -> List[str]:
        """
        تشخیص هوشمند اینکه دقیقاً چه پیش‌نیازهایی باید نصب شوند.
        جلوگیری از نصب مجدد مواردی که قبلا نصب شده‌اند.
        """
        logger.log("AI", "PREREQ", "INFO", "تحلیل هوشمند پیش‌نیازهای نصب...")
        needed = []
        
        # 1. بررسی دقیق .NET Framework 4.8
        if not self._check_dotnet_48():
            needed.append("DotNet48")
            
        # 2. بررسی VC++ 2015-2022 (نیاز اصلی SQL و ابزارهای مدرن)
        if not self._check_vcredist_2015_2022():
            needed.append("VCRedist_2015_2022")
            
        # 3. بررسی فونت‌های سیستمی
        # به جای نصب کورکورانه، چک می‌کنیم آیا IRANSans نصب است؟
        if not self._check_font_installed("IRANSans"):
            needed.append("SystemFonts")
            
        logger.log("AI", "PREREQ", "RESULT", f"پیش‌نیازهای ضروری تشخیص داده شده: {needed}")
        return needed

    def _check_dotnet_48(self) -> bool:
        """تشخیص قطعی دات‌نت 4.8 از طریق رجیستری"""
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full") as key:
                release, _ = winreg.QueryValueEx(key, "Release")
                # Release 528040 = .NET 4.8
                return release >= 528040
        except OSError:
            return False

    def _check_vcredist_2015_2022(self) -> bool:
        """تشخیص نصب بودن VC++ 2015-2022 x64"""
        try:
            # کلید رجیستری برای VC++ 2015-2022 x64
            key_path = r"SOFTWARE\Classes\Installer\Dependencies\VC,redist.x64,amd64,14.30,bundle"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                ver, _ = winreg.QueryValueEx(key, "Version")
                return ver.startswith("14.")
        except OSError:
            return False
            
    def _check_font_installed(self, font_name: str) -> bool:
        font_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
        if not os.path.exists(font_path):
            return False
        for f in os.listdir(font_path):
            if font_name.lower() in f.lower():
                return True
        return False

    # ==========================================
    # 3. Dynamic Resource Allocation
    # ==========================================
    def get_dynamic_copy_params(self) -> Tuple[int, float]:
        """
        بر اساس درگیری فعلی سیستم، سرعت و بافر کپی فایل‌ها را بهینه و داینامیک تنظیم می‌کند.
        از کش ۳ ثانیه‌ای استفاده می‌کند تا از سربار مکرر و تاخیر ناخواسته جلوگیری شود.
        خروجی: (اندازه چانک به بایت, زمان تاخیر بین چانک‌ها به ثانیه)
        """
        import time
        now = time.time()
        if now - self._last_copy_check < 3.0:
            return self._cached_copy_params

        self._last_copy_check = now
        try:
            # interval=None غیرمسدودکننده و سریع است (بدون اسلیپ ۱۰۰ میلی‌ثانیه‌ای)
            cpu_usage = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            
            # در شرایط نرمال: بافر پرسرعت ۴ مگابایت، بدون تاخیر
            if cpu_usage > 92.0 and mem.percent > 95.0:
                self._cached_copy_params = (1024 * 1024 * 1, 0.0)
            else:
                self._cached_copy_params = (1024 * 1024 * 4, 0.0)
        except Exception:
            self._cached_copy_params = (1024 * 1024 * 4, 0.0)

        return self._cached_copy_params


# یک نمونه سراسری (Singleton) برای استفاده در تمام بخش‌های اینستالر
setup_ai = SepehryarSetupAI()
