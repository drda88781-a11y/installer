# file_manager/update_engine.py
"""
موتور جامع و تراکنش‌محور به‌روزرسانی دستی نرم‌افزار سپهریار (SEPEHRYAR Manual Update Engine):
۱. اعتبارسنجی دقیق و امن فایل آرشیو ZIP بر اساس ساختار استاندارد (Files و Data) و پیشگیری از Zip Slip
۲. تشخیص هوشمند و داینامیک مسیرهای نصب، پوشه SEPEHRYAR.Data، اینستنس SQL Server و دیتابیس بدون هاردکد
۳. استخراج و مقایسه دقیق نسخه‌ها از هدر باینری PE فایل‌های EXE
۴. پشتیبان‌گیری کامل از فایل‌های برنامه و دیتابیس (SQL Server .bak) قبل از هرگونه تغییر
۵. تفکیک کامل و مستقل چرخه به‌روزرسانی Files از Data
۶. مدیریت هوشمند ۳ حالت پایگاه داده (عدم وجود، وجود قبلی بدون نیاز به تغییر، دیتابیس نسخه جدید)
۷. حفظ کامل فایل‌های پیکربندی و تنظیمات حساس (conect.xml، کانفیگ‌ها، لایسنس و ...)
۸. اعتبارسنجی زنده و ۱۲ گانه سلامت پایگاه داده و برنامه پس از به‌روزرسانی
۹. قابلیت بازگشت کامل به نسخه قبلی (Rollback) در صورت بروز هرگونه خطا در هر مرحله
۱۰. ثبت لاگ فوق‌العاده تفصیلی برای هر عملیات در UpdateLogs/Update_YYYY-MM-DD_HHMMSS.log
"""

import ctypes
from ctypes import wintypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Callable, Dict, List, Optional, Tuple, Any
import zipfile

import psutil
import pyodbc

from config.settings import (
    SQL_SA_USER,
    SQL_SA_PASSWORD,
    get_sql_instance_name,
)
from app_logging.app_logger import logger


# ============================================================================
# ۱. ساختارهای داده‌ای و کلاس‌های نتیجه (Data Structures)
# ============================================================================

class UpdateStageStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class UpdateStageItem:
    def __init__(self, stage_id: str, title: str):
        self.stage_id = stage_id
        self.title = title
        self.status = UpdateStageStatus.PENDING
        self.message = ""
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.duration_seconds: float = 0.0

    def start(self):
        self.status = UpdateStageStatus.RUNNING
        self.start_time = time.time()

    def complete(self, message: str = ""):
        self.status = UpdateStageStatus.SUCCESS
        self.message = message
        self.end_time = time.time()
        if self.start_time:
            self.duration_seconds = round(self.end_time - self.start_time, 2)

    def fail(self, message: str = ""):
        self.status = UpdateStageStatus.FAILED
        self.message = message
        self.end_time = time.time()
        if self.start_time:
            self.duration_seconds = round(self.end_time - self.start_time, 2)

    def skip(self, message: str = ""):
        self.status = UpdateStageStatus.SKIPPED
        self.message = message


class UpdateValidationReport:
    """گزارش کامل اعتبارسنجی پکیج آپدیت ZIP قبل از هرگونه تغییر"""
    def __init__(self):
        self.is_valid: bool = False
        self.archive_path: Optional[Path] = None
        self.zip_file_size_bytes: int = 0
        self.has_files_folder: bool = False
        self.files_count: int = 0
        self.files_total_size: int = 0
        self.detected_exes: List[str] = []
        self.main_exe_name: Optional[str] = None
        self.package_version: str = "نامشخص"
        self.has_data_folder: bool = False
        self.mdf_files: List[str] = []
        self.ldf_files: List[str] = []
        self.has_sql_server_forbidden_files: bool = False
        self.forbidden_files_found: List[str] = []
        self.is_path_traversal_safe: bool = True
        self.error_message: Optional[str] = None
        self.warnings: List[str] = []


class InstalledAppInfo:
    """مشخصات برنامه نصب‌شده روی سیستم"""
    def __init__(
        self,
        product_id: str,
        title: str,
        install_dir: Path,
        main_exe_path: Path,
        version: str,
        data_dir: Optional[Path] = None,
        config_files: Optional[List[Path]] = None,
    ):
        self.product_id = product_id
        self.title = title
        self.install_dir = install_dir
        self.main_exe_path = main_exe_path
        self.version = version
        self.data_dir = data_dir
        self.config_files = config_files or []


class UpdatePipelineResult:
    """نتیجه نهایی اجرای پایپ‌لاین آپدیت"""
    def __init__(self):
        self.success: bool = False
        self.message: str = ""
        self.previous_version: str = ""
        self.new_version: str = ""
        self.app_dir: Optional[Path] = None
        self.data_dir: Optional[Path] = None
        self.sql_instance: str = ""
        self.database_name: str = ""
        self.files_updated_count: int = 0
        self.data_files_transferred: List[str] = []
        self.database_updated: bool = False
        self.database_action: str = "هیچ"
        self.backup_app_dir: Optional[Path] = None
        self.backup_db_file: Optional[Path] = None
        self.log_file_path: Optional[Path] = None
        self.rollback_executed: bool = False
        self.rollback_success: bool = False
        self.failed_stage_id: Optional[str] = None
        self.error_details: Optional[str] = None
        self.stages: List[UpdateStageItem] = []


# ============================================================================
# ۲. توابع کمکی استخراج نسخه PE و مقایسه Semantic (Version Utils)
# ============================================================================

def get_pe_file_version(filepath: Path) -> str:
    """
    استخراج نسخه فایل ویندوز (FileVersion / ProductVersion) از هدر PE
    از طریق Win32 API رسمی بدون وابستگی خارجی
    """
    path_str = str(filepath.resolve())
    if not filepath.exists() or not filepath.is_file():
        return "0.0.0.0"

    try:
        size = ctypes.windll.version.GetFileVersionInfoSizeW(path_str, None)
        if size == 0:
            return "1.0.0.0"

        res = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(path_str, 0, size, res):
            return "1.0.0.0"

        u_len = wintypes.UINT()
        p_buffer = ctypes.c_void_p()

        # بررسی VS_FIXEDFILEINFO در ریشه منابع
        if ctypes.windll.version.VerQueryValueW(res, "\\", ctypes.byref(p_buffer), ctypes.byref(u_len)):
            class VS_FIXEDFILEINFO(ctypes.Structure):
                _fields_ = [
                    ("dwSignature", wintypes.DWORD),
                    ("dwStrucVersion", wintypes.DWORD),
                    ("dwFileVersionMS", wintypes.DWORD),
                    ("dwFileVersionLS", wintypes.DWORD),
                    ("dwProductVersionMS", wintypes.DWORD),
                    ("dwProductVersionLS", wintypes.DWORD),
                    ("dwFileFlagsMask", wintypes.DWORD),
                    ("dwFileFlags", wintypes.DWORD),
                    ("dwFileOS", wintypes.DWORD),
                    ("dwFileType", wintypes.DWORD),
                    ("dwFileSubtype", wintypes.DWORD),
                    ("dwFileDateMS", wintypes.DWORD),
                    ("dwFileDateLS", wintypes.DWORD),
                ]

            vs = VS_FIXEDFILEINFO.from_address(p_buffer.value)
            # خواندن ProductVersion اولویت دارد زیرا نسخه محصول را بازتاب می‌دهد
            p_major = vs.dwProductVersionMS >> 16
            p_minor = vs.dwProductVersionMS & 0xFFFF
            p_build = vs.dwProductVersionLS >> 16
            p_rev = vs.dwProductVersionLS & 0xFFFF

            f_major = vs.dwFileVersionMS >> 16
            f_minor = vs.dwFileVersionMS & 0xFFFF
            f_build = vs.dwFileVersionLS >> 16
            f_rev = vs.dwFileVersionLS & 0xFFFF

            # اگر ProductVersion مقدار معنادار داشت
            if (p_major, p_minor, p_build, p_rev) != (0, 0, 0, 0):
                return f"{p_major}.{p_minor}.{p_build}.{p_rev}"
            if (f_major, f_minor, f_build, f_rev) != (0, 0, 0, 0):
                return f"{f_major}.{f_minor}.{f_build}.{f_rev}"

        return "1.0.0.0"
    except Exception as ex:
        logger.log("VERSION", "READ_ERROR", "WARN", f"عدم امکان خواندن نسخه PE از {filepath.name}: {ex}")
        return "1.0.0.0"


def normalize_version(ver_str: str) -> Tuple[int, ...]:
    """تبدیل رشته نسخه به تاپل عددی جهت مقایسه ریاضی دقیق"""
    if not ver_str:
        return (0, 0, 0, 0)
    # پاک‌سازی از هرگونه حرف یا کاراکتر متنی
    clean = re.sub(r"[^\d.]", "", ver_str.strip())
    parts = clean.split(".")
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


def compare_versions(current_ver: str, update_ver: str) -> int:
    """
    مقایسه نسخه فعلی با نسخه آپدیت:
    بازگرداندن:
      > 0  اگر نسخه آپدیت جدیدتر باشد (Update > Current)
      = 0  اگر دو نسخه برابر باشند (Update == Current)
      < 0  اگر نسخه آپدیت قدیمی‌تر باشد (Update < Current)
    """
    cur_tuple = normalize_version(current_ver)
    upd_tuple = normalize_version(update_ver)

    if upd_tuple > cur_tuple:
        return 1
    elif upd_tuple < cur_tuple:
        return -1
    else:
        return 0


# ============================================================================
# ۳. تشخیص هوشمند سیستم و مسیرها (Dynamic Path & SQL Detection)
# ============================================================================

def detect_installed_applications() -> List[InstalledAppInfo]:
    """
    تشخیص خودکار و بدون هاردکد تمام برنامه‌های نصب‌شده سپهریار بر روی تمام درایوهای فعال سیستم
    """
    results: List[InstalledAppInfo] = []
    searched_dirs: List[Path] = []

    # اسکن تمام درایوهای ویندوز
    for part in psutil.disk_partitions(all=False):
        mount = part.mountpoint
        if not mount or "cdrom" in part.opts:
            continue
        p_mount = Path(mount)

        candidates = [
            p_mount / "SEPEHRYAR",
            p_mount / "Program Files" / "Sepehryar",
            p_mount / "Program Files (x86)" / "Sepehryar",
            p_mount / "Sepehryar",
        ]
        for c in candidates:
            if c.exists() and c.is_dir():
                searched_dirs.append(c)

    # افزودن مسیر جاری و پوشه پدر
    searched_dirs.append(Path.cwd())
    searched_dirs.append(Path.cwd().parent)

    # اسکن پوشه‌ها برای یافتن فایل‌های اجرایی سپهریار
    known_products = [
        {"id": "SEPEHRYAR.Hesabdari", "title": "سپهریار - حسابداری", "exes": ["Hesabdari.exe"]},
        {"id": "SEPEHRYAR.Resturan", "title": "سپهریار - رستوران", "exes": ["SepandResturan.exe"]},
        {"id": "SEPEHRYAR.Sanati", "title": "سپهریار - صنعتی", "exes": ["Hesabdari.exe"]},
        {"id": "SEPEHRYAR.Client", "title": "سپهریار - فروش (کلاینت)", "exes": ["ClientSepand.exe"]},
        {"id": "SEPEHRYAR.TaxGov", "title": "سپهریار - سامانه مودیان", "exes": ["SepandYar_TaxGov.exe"]},
    ]

    seen_exe_paths = set()

    for base_dir in searched_dirs:
        # بررسی زیرپوشه‌های موجود در base_dir
        sub_dirs = [base_dir]
        try:
            sub_dirs.extend([d for d in base_dir.iterdir() if d.is_dir()])
        except Exception:
            pass

        for s_dir in sub_dirs:
            for p_info in known_products:
                for exe_name in p_info["exes"]:
                    candidate_exe = s_dir / exe_name
                    if not candidate_exe.exists() or not candidate_exe.is_file():
                        # بررسی در صورت وجود ساب‌فولدر تو در تو
                        candidate_exe = s_dir / s_dir.name / exe_name

                    if candidate_exe.exists() and candidate_exe.is_file():
                        norm_exe = str(candidate_exe.resolve()).lower()
                        if norm_exe in seen_exe_paths:
                            continue
                        seen_exe_paths.add(norm_exe)

                        install_folder = candidate_exe.parent
                        ver = get_pe_file_version(candidate_exe)

                        # تشخیص پوشه داده متناظر
                        data_dir = detect_sepehryar_data_dir(install_folder)

                        # تشخیص فایل‌های کانفیگ
                        configs = []
                        for cfg_name in ["conect.xml", "connect.xml", "Conect.xml", f"{exe_name}.config", "Setting.Stg"]:
                            cfg_path = install_folder / cfg_name
                            if cfg_path.exists():
                                configs.append(cfg_path)

                        app_item = InstalledAppInfo(
                            product_id=p_info["id"],
                            title=p_info["title"],
                            install_dir=install_folder,
                            main_exe_path=candidate_exe,
                            version=ver,
                            data_dir=data_dir,
                            config_files=configs,
                        )
                        results.append(app_item)

    return results


def detect_sepehryar_data_dir(app_dir: Optional[Path] = None) -> Path:
    r"""
    تشخیص داینامیک و خودکار مسیر SEPEHRYAR.Data بدون هیچ‌گونه هاردکد:
    ۱. در کنار پوشه محصول در ریشه نصب (مثلاً D:\SEPEHRYAR\SEPEHRYAR.Data)
    ۲. در ریشه درایو نصب (مثلاً D:\SEPEHRYAR.Data)
    ۳. در سایر درایوهای موجود در سیستم
    ۴. فال‌بک امن بر روی درایو انتخابی
    """
    if app_dir:
        # ۱. بررسی پدر مسیر برنامه (مثلاً D:\SEPEHRYAR)
        p1 = app_dir.parent / "SEPEHRYAR.Data"
        if p1.exists() and p1.is_dir():
            return p1

        # در صورتی که ساختار تو در تو باشد
        p1_sub = app_dir.parent.parent / "SEPEHRYAR.Data"
        if p1_sub.exists() and p1_sub.is_dir():
            return p1_sub

        # ۲. بررسی ریشه درایو برنامه
        drive_letter = app_dir.drive
        if drive_letter:
            p2 = Path(f"{drive_letter}\\SEPEHRYAR.Data")
            if p2.exists() and p2.is_dir():
                return p2

    # ۳. بررسی سایر درایوهای فعال سیستم
    for part in psutil.disk_partitions(all=False):
        mount = part.mountpoint
        if not mount or "cdrom" in part.opts:
            continue
        p = Path(mount) / "SEPEHRYAR" / "SEPEHRYAR.Data"
        if p.exists() and p.is_dir():
            return p
        p_root = Path(mount) / "SEPEHRYAR.Data"
        if p_root.exists() and p_root.is_dir():
            return p_root

    # فال‌بک: ایجاد در پوشه پدر برنامه یا درایو مناسب
    if app_dir:
        return app_dir.parent / "SEPEHRYAR.Data"
    return Path(r"D:\SEPEHRYAR\SEPEHRYAR.Data")


def detect_sql_server_instances() -> List[Dict[str, Any]]:
    """
    تشخیص کلیه اینستنس‌های فعال SQL Server روی سیستم از طریق رجیستری و سرویس‌های فعال ویندوز
    """
    instances: List[Dict[str, Any]] = []
    found_names = set()

    # ۱. جستجو در رجیستری ویندوز
    reg_keys = [
        r"SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL",
        r"SOFTWARE\WOW6432Node\Microsoft\Microsoft SQL Server\Instance Names\SQL",
    ]
    import winreg
    for rpath in reg_keys:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rpath) as key:
                i = 0
                while True:
                    name, val, _ = winreg.EnumValue(key, i)
                    if name and name not in found_names:
                        found_names.add(name)
                        instances.append({
                            "name": name,
                            "registry_id": val,
                            "service_name": f"MSSQL${name}" if name != "MSSQLSERVER" else "MSSQLSERVER",
                            "source": "registry",
                        })
                    i += 1
        except OSError:
            pass

    # ۲. جستجو در سرویس‌های فعال ویندوز
    for s in psutil.win_service_iter():
        try:
            s_name = s.name()
            if s_name.upper().startswith("MSSQL$"):
                inst_name = s_name[6:]
                if inst_name not in found_names:
                    found_names.add(inst_name)
                    instances.append({
                        "name": inst_name,
                        "registry_id": s_name,
                        "service_name": s_name,
                        "source": "service",
                    })
            elif s_name.upper() == "MSSQLSERVER" and "MSSQLSERVER" not in found_names:
                found_names.add("MSSQLSERVER")
                instances.append({
                    "name": "MSSQLSERVER",
                    "registry_id": "MSSQLSERVER",
                    "service_name": s_name,
                    "source": "service",
                })
        except Exception:
            pass

    return instances


def find_best_sql_instance(preferred_instance: Optional[str] = None) -> Optional[str]:
    """
    یافتن بهترین اینستنس SQL Server قابل اتصال:
    اولویت با اینستنس انتخابی یا SEPEHRYAR2019 و سپس SEPEHRYAR2014 و در نهایت سایر اینستنس‌ها
    """
    available = detect_sql_server_instances()
    names = [a["name"] for a in available]

    if preferred_instance and preferred_instance in names:
        return preferred_instance

    for priority_cand in ["SEPEHRYAR2019", "SEPEHRYAR2014", "SQLEXPRESS", "MSSQLSERVER"]:
        if priority_cand in names:
            return priority_cand

    if names:
        return names[0]
    return None


def ensure_sql_service_running(instance_name: str) -> bool:
    """اطمینان از فعال و در حال اجرا بودن سرویس SQL Server"""
    svc_name = f"MSSQL${instance_name}" if instance_name != "MSSQLSERVER" else "MSSQLSERVER"
    try:
        service = psutil.win_service_get(svc_name)
        if service.status() == "running":
            return True
        # تلاش برای استارت
        res = subprocess.run(["net", "start", svc_name], capture_output=True, text=True, timeout=30)
        return res.returncode == 0 or "already started" in res.stdout.lower()
    except Exception as ex:
        logger.log("SQL", "SERVICE_START", "WARN", f"خطا در بررسی/استارت سرویس {svc_name}: {ex}")
        return False


def get_sql_connection(instance_name: str, timeout: int = 10) -> Optional[pyodbc.Connection]:
    """برقراری اتصال امن با ODBC به SQL Server"""
    drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
    if not drivers:
        return None

    preferred_driver = "SQL Server"
    for d in ["ODBC Driver 17 for SQL Server", "SQL Server Native Client 11.0", "SQL Server"]:
        if d in drivers:
            preferred_driver = d
            break

    target_server = f".\\{instance_name}" if instance_name != "MSSQLSERVER" else "."

    # ۱. ابتدا تلاش با Windows Authentication
    conn_str_trusted = f"Driver={{{preferred_driver}}};Server={target_server};Trusted_Connection=yes;"
    try:
        conn = pyodbc.connect(conn_str_trusted, timeout=timeout, autocommit=True)
        return conn
    except Exception:
        pass

    # ۲. تلاش با SQL Authentication (sa)
    conn_str_sa = f"Driver={{{preferred_driver}}};Server={target_server};UID={SQL_SA_USER};PWD={SQL_SA_PASSWORD};"
    try:
        conn = pyodbc.connect(conn_str_sa, timeout=timeout, autocommit=True)
        return conn
    except Exception:
        return None


# ============================================================================
# ۴. اعتبارسنجی امن بسته ZIP و جلوگیری از Zip Slip (Validation)
# ============================================================================

def is_safe_path(base_dir: Path, target_path: Path) -> bool:
    """بررسی عدم خروج مسیر از پوشه مقصد (جلوگیری قطعی از Path Traversal / Zip Slip)"""
    try:
        target_path.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def validate_update_archive(archive_path: Path) -> UpdateValidationReport:
    from file_manager.update_package import UpdatePackage
    report = UpdateValidationReport()
    report.archive_path = archive_path
    try:
        with UpdatePackage(archive_path) as package:
            report.is_valid = True
            report.zip_file_size_bytes = archive_path.stat().st_size
            report.package_version = package.manifest["version"]
            report.products = package.manifest["products"]
            report.database_names = [db["name"] for db in package.manifest.get("databases", [])]
            report.has_files_folder = any(entry.kind == "application" for entry in package.files)
            report.has_data_folder = bool(package.manifest.get("databases"))
            report.files_count = len(package.files)
            report.files_total_size = sum(entry.size for entry in package.files)
            report.detected_exes = [Path(entry.target).name for entry in package.files if entry.kind == "application" and entry.target.lower().endswith(".exe")]
            report.main_exe_name = report.detected_exes[0] if report.detected_exes else None
            report.mdf_files = [entry.path for entry in package.files if entry.kind == "data" and entry.path.lower().endswith(".mdf")]
            report.ldf_files = [entry.path for entry in package.files if entry.kind == "data" and entry.path.lower().endswith(".ldf")]
    except Exception as exc:
        report.error_message = str(exc)
    return report


class ManualUpdatePipeline:
    """UI adapter; all backup, mutation and recovery live in TransactionalUpdate."""
    from file_manager.transactional_update import STAGES as STAGES_DEF

    def __init__(self, archive_path, target_app_dir=None, target_data_dir=None,
                 sql_instance=None, progress_callback=None, stage_callback=None):
        self.archive_path = Path(archive_path)
        self.target_app_dir = target_app_dir
        self.target_data_dir = target_data_dir
        self.sql_instance = sql_instance
        self.progress_callback = progress_callback
        self.stage_callback = stage_callback
        self.stages = [UpdateStageItem(stage, title) for stage, title in self.STAGES_DEF]
        self._active_stage = None

    def _stage(self, index, message):
        if self._active_stage is not None:
            previous = self.stages[self._active_stage]
            previous.complete(previous.message)
            if self.stage_callback:
                self.stage_callback(self._active_stage, previous)
        self._active_stage = index
        current = self.stages[index]
        current.start()
        current.message = message
        if self.stage_callback:
            self.stage_callback(index, current)

    def execute(self):
        from config.settings import PRODUCTS_CONFIG, requires_sql
        from file_manager.update_package import UpdatePackage
        from file_manager.transactional_update import TransactionalUpdate
        result = UpdatePipelineResult()
        result.stages = self.stages
        try:
            if self.target_app_dir is None:
                raise ValueError("???? ????? ??? ?? ?????? ????.")
            directory = Path(self.target_app_dir).resolve()
            with UpdatePackage(self.archive_path) as package:
                products = package.manifest["products"]
                matches = [p for p in products if directory.name == PRODUCTS_CONFIG[p]["folder_name"]]
                if not matches and len(products) == 1 and (directory / PRODUCTS_CONFIG[products[0]]["main_exe"]).is_file():
                    matches = products
                if len(matches) != 1:
                    raise ValueError("????? ???? ?? ???? ??????? ?????? ????? ?? ???? ????? ????.")
            product = matches[0]
            engine = TransactionalUpdate(
                root_dir=directory.parent, targets={product: directory},
                sql_instance=self.sql_instance, data_dir=self.target_data_dir,
                allow_database=requires_sql([product]), progress_callback=self.progress_callback,
                stage_callback=self._stage,
            )
            outcome = engine.execute(self.archive_path)
            result.success = outcome.success
            result.message = outcome.message
            result.previous_version = outcome.previous_version
            result.new_version = outcome.new_version
            result.app_dir = directory
            result.data_dir = engine.data_dir
            result.sql_instance = self.sql_instance or ""
            result.files_updated_count = outcome.files_updated_count
            result.data_files_transferred = outcome.data_files_transferred
            result.database_updated = bool(outcome.attached_databases or outcome.executed_sql_scripts)
            result.backup_app_dir = outcome.backup_dir
            result.log_file_path = outcome.log_file_path
            result.rollback_executed = outcome.rollback_executed
            result.rollback_success = outcome.rollback_success
            result.failed_stage_id = outcome.failed_stage_id
            result.error_details = None if outcome.success else outcome.message
        except Exception as exc:
            result.message = result.error_details = str(exc)
        if self._active_stage is not None:
            stage = self.stages[self._active_stage]
            stage.complete(result.message) if result.success else stage.fail(result.message)
            if self.stage_callback:
                self.stage_callback(self._active_stage, stage)
        return result
