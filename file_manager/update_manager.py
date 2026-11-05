# file_manager/update_manager.py
"""
ماژول پردازش و اعمال بسته آخرین به‌روزرسانی نرم‌افزار سپهریار:
۱. استخراج بدون وابستگی انواع فایل‌های آرشیو (.zip, .rar, .7z) با متدهای چندلایه
۲. آزادسازی خودکار فایل‌ها با بستن پروسه‌های در حال اجرا جهت جلوگیری از خطای WinError 32
۳. کپی محتویات پوشه files بر روی فایل‌های نصبی برنامه
۴. انتقال فایل‌های دیتابیس پوشه data به پوشه SEPEHRYAR.Data
۵. اتچ خودکار پایگاه داده (.mdf/.ldf) در SQL Server فعال (SEPEHRYAR2014 یا SEPEHRYAR2019)
۶. شناسایی و اجرای خودکار پچ‌های اسکریپتی SQL (.sql) بر روی پایگاه داده
۷. ایجاد و به‌روزرسانی میانبر فایل اجرایی روی دسکتاپ
"""

import os
from pathlib import Path
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple
import pyodbc

from config.settings import (
    SQL_SA_USER,
    SQL_SA_PASSWORD,
    get_sql_instance_name,
    requires_sql,
)
from app_logging.app_logger import logger
from packages.product_catalog import get_product_by_id, resolve_installed_exe_path
from utils.archive_extractor import (
    close_running_sepehryar_processes,
    extract_archive_universal,
)
from utils.shortcut_manager import create_shortcuts_for_product


@dataclass
class UpdateResult:
    success: bool
    message: str
    files_copied_count: int = 0
    data_files_copied: List[str] = field(default_factory=list)
    attached_databases: List[str] = field(default_factory=list)
    executed_sql_scripts: List[str] = field(default_factory=list)
    shortcuts_created: List[str] = field(default_factory=list)
    error_details: Optional[str] = None
    backup_dir: Optional[str] = None
    rollback_executed: bool = False
    rollback_success: bool = False


class UpdateManager:
    """
    مدیریت کامل چرخه اعمال پکیج آخرین آپدیت
    """
    def __init__(
        self,
        root_dir: Path,
        selected_product_ids: List[str],
        install_mode: str = "server",
        sql_version: str = "2019",
        server_target: str = "",
        progress_callback: Optional[Callable[[str, int], None]] = None,
        sql_instance: Optional[str] = None,
    ):
        self.root_dir = root_dir
        self.selected_product_ids = selected_product_ids
        self.install_mode = install_mode
        self.sql_version = str(sql_version)
        self.server_target = str(server_target)
        self.instance_name = (sql_instance or get_sql_instance_name(self.sql_version)).strip()
        self.progress_callback = progress_callback
        self.data_dir = self.root_dir / "SEPEHRYAR.Data"
        self.update_dir = self.root_dir / "SEPEHRYAR.Update"

    def _notify(self, msg: str, percent: int = -1):
        if self.progress_callback:
            self.progress_callback(msg, percent)

    def extract_archive(self, archive_path: Path, dest_dir: Path) -> Tuple[bool, str]:
        """استخراج فایل آرشیو با متد چندلایه Universal"""
        return extract_archive_universal(
            archive_path=archive_path,
            dest_dir=dest_dir,
            progress_callback=self.progress_callback,
        )

    def copy_update_files(self, source_extracted_dir: Path) -> Tuple[bool, str, int]:
        """
        یافتن پوشه files و کپی/جایگزینی کلیه فایل‌ها روی پوشه برنامه نصب‌شده
        همراه با آزادسازی خودکار پروسه‌های باز جهت جلوگیری از قفل شدن فایل‌ها
        """
        # ۱. آزادسازی پروسه‌های در حال اجرا
        close_running_sepehryar_processes()

        # جستجوی پوشه files (بدون حساسیت به حروف بزرگ و کوچک)
        files_dirs = [d for d in source_extracted_dir.rglob("*") if d.is_dir() and d.name.lower() == "files"]
        if not files_dirs:
            # بررسی اینکه آیا خود پوشه ریشه استخراج شده حاوی فایل‌های اجرایی است
            files_dir = source_extracted_dir
        else:
            files_dir = files_dirs[0]

        logger.log("UPDATE", "COPY_FILES", "RUNNING", f"پوشه منبع files: {files_dir}")
        copied_count = 0
        errors: List[str] = []

        # کپی بر روی پوشه محصولات نصب‌شده
        target_dirs: List[Path] = []
        for pid in self.selected_product_ids:
            cfg = get_product_by_id(pid)
            folder_name = cfg.folder_name if cfg else pid
            p_dir = self.root_dir / folder_name
            if p_dir.exists():
                target_dirs.append(p_dir)

        if not target_dirs:
            # اگر پوشه‌ای یافت نشد، ریشه یا زیرپوشه‌های موجود در root بررسی شوند
            sub_dirs = [d for d in self.root_dir.iterdir() if d.is_dir() and "sepehryar." in d.name.lower() and d.name.lower() not in ["sepehryar.setup", "sepehryar.data", "sepehryar.backup", "sepehryar.update"]]
            target_dirs = sub_dirs or [self.root_dir]

        for target_dir in target_dirs:
            logger.log("UPDATE", "COPY_FILES", "RUNNING", f"کپی فایل‌های آپدیت به مقصد: {target_dir}")
            for root, _, files in os.walk(files_dir):
                # نادیده گرفتن پوشه data اگر در داخل files قرار داشت
                if "data" in [part.lower() for part in Path(root).relative_to(files_dir).parts]:
                    continue

                rel_path = Path(root).relative_to(files_dir)
                dest_sub_dir = target_dir / rel_path
                dest_sub_dir.mkdir(parents=True, exist_ok=True)

                for f in files:
                    s_file = Path(root) / f
                    # فایل‌های دیتابیس در کپی files وارد نشوند
                    if s_file.suffix.lower() in [".mdf", ".ldf"]:
                        continue

                    d_file = dest_sub_dir / f
                    try:
                        shutil.copy2(s_file, d_file)
                        copied_count += 1
                    except PermissionError:
                        # در صورت بروز خطای قفل، مجدداً پروسه‌ها بسته شده و تلاش دوم صورت می‌گیرد
                        close_running_sepehryar_processes()
                        try:
                            shutil.copy2(s_file, d_file)
                            copied_count += 1
                        except Exception as ex2:
                            errors.append(f"{f}: {ex2}")
                            logger.log("UPDATE", "COPY_FILES", "WARN", f"عدم امکان جایگزینی فایل قفل‌شده {f}: {ex2}")
                    except Exception as ex:
                        errors.append(f"{f}: {ex}")
                        logger.log("UPDATE", "COPY_FILES", "WARN", f"خطا در کپی {f}: {ex}")

        if errors:
            return False, "خطا در کپی فایل‌های آپدیت: " + " | ".join(errors), copied_count

        # تنظیم مجدد فایل‌های CONNECT در صورت نیاز
        if getattr(self, "server_target", ""):
            try:
                from utils.connect_config import update_all_connect_files_in_folder
                for pid in self.selected_product_ids:
                    p_info = get_product_by_id(pid)
                    f_name = p_info.folder_name if p_info else pid
                    d_dir = self.root_dir / f_name
                    if d_dir.exists():
                        update_all_connect_files_in_folder(d_dir, self.server_target)
            except Exception as ex_c:
                logger.log("UPDATE", "CONNECT_CONFIG", "WARN", f"خطا در به‌روزرسانی مجدد فایل CONNECT: {ex_c}")

        msg = f"تعداد {copied_count} فایل جدید روی برنامه کپی و به‌روزرسانی شد."
        logger.log("UPDATE", "COPY_FILES", "SUCCESS", msg)
        return True, msg, copied_count

    def copy_data_files(self, source_extracted_dir: Path) -> Tuple[bool, str, List[Path]]:
        """
        یافتن پوشه data و کپی فایل‌های دیتابیس به SEPEHRYAR.Data
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)

        data_dirs = [d for d in source_extracted_dir.rglob("*") if d.is_dir() and d.name.lower() == "data"]
        copied_mdfs: List[Path] = []
        errors: List[str] = []

        if not data_dirs:
            # جستجوی مستقیم فایل‌های .mdf و .ldf در کل محتوای استخراج‌شده
            mdf_candidates = list(source_extracted_dir.rglob("*.mdf"))
            ldf_candidates = list(source_extracted_dir.rglob("*.ldf"))
            data_files = mdf_candidates + ldf_candidates
        else:
            data_dir_src = data_dirs[0]
            data_files = [f for f in data_dir_src.iterdir() if f.is_file()]

        for f in data_files:
            dst = self.data_dir / f.name
            is_mdf = dst.suffix.lower() == ".mdf"

            # حفاظت حیاتی از داده‌های موجود مشتری: اگر فایل دیتابیس از قبل موجود باشد بازنویسی نشود
            if dst.exists():
                if is_mdf:
                    copied_mdfs.append(dst)
                logger.log("UPDATE", "COPY_DATA", "INFO", f"فایل دیتابیس {dst.name} از قبل در پوشه Data موجود است و جهت حفظ اطلاعات مالی بازنویسی نشد.")
                continue

            try:
                shutil.copy2(f, dst)
                if is_mdf:
                    copied_mdfs.append(dst)
                logger.log("UPDATE", "COPY_DATA", "SUCCESS", f"فایل دیتا کپی شد: {dst.name}")
            except Exception as ex:
                errors.append(f"{f.name}: {ex}")
                logger.log("UPDATE", "COPY_DATA", "WARN", f"خطا در کپی فایل دیتا {f.name}: {ex}")

        if errors:
            return False, "خطا در انتقال فایل‌های داده: " + " | ".join(errors), copied_mdfs

        # تضمین دسترسی کامل برای سرویس SQL Server
        self._grant_folder_permissions(self.data_dir)

        msg = f"تعداد {len(data_files)} فایل دیتابیس به {self.data_dir.name} منتقل شد."
        return True, msg, copied_mdfs

    def _grant_folder_permissions(self, folder: Path):
        """اعمال دسترسی کامل ویندوز بر روی پوشه جهت جلوگیری از خطای Access Denied در SQL Server"""
        try:
            subprocess.run(
                ["icacls", str(folder), "/grant", "Everyone:(OI)(CI)F", "/T", "/Q"],
                capture_output=True,
                timeout=15
            )
            logger.log("UPDATE", "PERMISSIONS", "SUCCESS", f"دسترسی کامل بر پوشه {folder} تنظیم شد.")
        except Exception as ex:
            logger.log("UPDATE", "PERMISSIONS", "WARN", f"خطا در تنظیم دسترسی icacls: {ex}")

    def attach_databases(self, mdf_files: List[Path]) -> Tuple[bool, str, List[str]]:
        """
        اتچ کردن خودکار فایل‌های .mdf شناسایی‌شده در اینستنس SQL Server فعال
        با پشتیبانی از Windows Auth و SA Auth بدون توقف برنامه
        """
        if not mdf_files:
            mdf_files = list(self.data_dir.glob("*.mdf"))

        if not mdf_files:
            return True, "هیچ فایل پایگاه داده‌ای (.mdf) برای اتچ یافت نشد.", []

        target_server = f".\\{self.instance_name}"
        logger.log("UPDATE", "ATTACH_DB", "RUNNING", f"اتصال به {target_server} جهت اتچ پایگاه داده")

        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        driver = drivers[0] if drivers else "SQL Server"

        # اتصال: ابتدا با Windows Auth سپس با sa
        conn = None
        for conn_str in [
            f"Driver={{{driver}}};Server={target_server};Trusted_Connection=yes;",
            f"Driver={{{driver}}};Server={target_server};UID={SQL_SA_USER};PWD={SQL_SA_PASSWORD};",
        ]:
            try:
                conn = pyodbc.connect(conn_str, timeout=10, autocommit=True)
                break
            except Exception:
                pass

        if not conn:
            err = f"عدم امکان اتصال به SQL Server ({target_server}) جهت اتچ دیتابیس."
            logger.log("UPDATE", "ATTACH_DB", "WARN", err)
            return False, err, []

        attached_dbs: List[str] = []
        errors: List[str] = []
        try:
            cursor = conn.cursor()
            for mdf in mdf_files:
                db_name = mdf.stem
                mdf_path_str = str(mdf.resolve()).replace("'", "''")
                sql_db_name = db_name.replace("]", "]]")
                ldf_candidate = mdf.with_suffix(".ldf")
                if not ldf_candidate.exists():
                    ldf_candidate = mdf.parent / f"{mdf.stem}_log.ldf"

                # بررسی عدم وجود قبلی دیتابیس
                cursor.execute("SELECT name FROM sys.databases WHERE name = ?", (db_name,))
                if cursor.fetchone():
                    logger.log("UPDATE", "ATTACH_DB", "INFO", f"دیتابیس {db_name} از قبل در SQL Server موجود است.")
                    attached_dbs.append(db_name)
                    continue

                # اجرای دستور ATTACH
                if ldf_candidate.exists():
                    ldf_path_str = str(ldf_candidate.resolve()).replace("'", "''")
                    sql_attach = f"CREATE DATABASE [{sql_db_name}] ON (FILENAME = N'{mdf_path_str}'), (FILENAME = N'{ldf_path_str}') FOR ATTACH;"
                else:
                    sql_attach = f"CREATE DATABASE [{sql_db_name}] ON (FILENAME = N'{mdf_path_str}') FOR ATTACH_REBUILD_LOG;"

                try:
                    cursor.execute(sql_attach)
                    attached_dbs.append(db_name)
                    logger.log("UPDATE", "ATTACH_DB", "SUCCESS", f"پایگاه داده {db_name} با موفقیت اتچ شد.")
                except Exception as ex_db:
                    errors.append(f"{db_name}: {ex_db}")
                    logger.log("UPDATE", "ATTACH_DB", "WARN", f"هشدار در اتچ {db_name}: {ex_db}")

            if errors:
                return False, "اتصال پایگاه داده ناموفق بود: " + " | ".join(errors), attached_dbs
            return True, f"تعداد {len(attached_dbs)} پایگاه داده در SQL Server آماده‌سازی شد.", attached_dbs
        except Exception as ex:
            return False, f"عملیات اتچ ناموفق بود: {ex}", attached_dbs
        finally:
            conn.close()

    def execute_sql_patch_scripts(self, search_dir: Path) -> Tuple[bool, str, List[str]]:
        """
        یافتن و اجرای کلیه اسکریپت‌های پچ SQL (.sql) موجود در پکیج آپدیت بر روی SQL Server
        """
        sql_scripts = sorted(search_dir.rglob("*.sql"))
        executed: List[str] = []
        if not sql_scripts:
            return True, "پچ SQL در بسته وجود ندارد.", executed

        from sql.sql_auditor import SQLInstanceAuditor
        auditor = SQLInstanceAuditor()

        for s_file in sql_scripts:
            self._notify(f"در حال اعمال پچ پایگاه داده: {s_file.name}...", 88)
            ok, msg = auditor.execute_sql_script(self.instance_name, s_file)
            if ok:
                executed.append(s_file.name)
                logger.log("UPDATE", "SQL_PATCH", "SUCCESS", f"پچ SQL با موفقیت اعمال شد: {s_file.name}")
            else:
                logger.log("UPDATE", "SQL_PATCH", "WARN", f"خطا در اجرای پچ SQL {s_file.name}: {msg}")
                return False, f"اجرای پچ {s_file.name} ناموفق بود: {msg}", executed

        return True, "پچ‌های SQL با موفقیت اجرا شدند.", executed

    def refresh_desktop_shortcuts(self) -> List[Path]:
        """
        ساخت / به‌روزرسانی میانبر فایل اجرایی برنامه در دسکتاپ
        """
        created_shortcuts: List[Path] = []
        for pid in self.selected_product_ids:
            p_info = get_product_by_id(pid)
            exe_path = resolve_installed_exe_path(self.root_dir, pid)
            if p_info and exe_path and exe_path.exists():
                created = create_shortcuts_for_product(
                    p_info.title,
                    p_info.shortcut_name,
                    exe_path,
                )
                created_shortcuts.extend(created)
                logger.log("UPDATE", "SHORTCUT", "SUCCESS", f"میانبر دسکتاپ برای {p_info.title} ایجاد شد.")

        return created_shortcuts

    def execute_update_pipeline(self, archive_path: Path, lock_held: bool = False) -> UpdateResult:
        """Installer adapter for the same transaction engine used by the updater."""
        from file_manager.transactional_update import TransactionalUpdate
        from file_manager.update_package import UpdatePackage

        def progress(stage, percent, message):
            self._notify(message, percent)

        try:
            with UpdatePackage(archive_path) as package:
                package_products = package.manifest["products"]
        except Exception as exc:
            return UpdateResult(False, str(exc))
        targets = {}
        for product in self.selected_product_ids:
            if product not in package_products:
                continue
            info = get_product_by_id(product)
            if info is None:
                return UpdateResult(False, f"????? ????????: {product}")
            targets[product] = self.root_dir / info.folder_name
        if not targets:
            return UpdateResult(False, "محصول بسته در میان محصولات انتخاب‌شده نیست.")
        engine = TransactionalUpdate(
            self.root_dir, targets, sql_instance=self.instance_name, sql_version=self.sql_version,
            data_dir=self.data_dir, allow_database=requires_sql(self.selected_product_ids, self.install_mode),
            allow_equal_version=True, progress_callback=progress,
        )
        result = engine.execute(archive_path, lock_held=lock_held)
        return UpdateResult(
            success=result.success, message=result.message,
            files_copied_count=result.files_updated_count,
            data_files_copied=result.data_files_transferred,
            attached_databases=result.attached_databases,
            executed_sql_scripts=result.executed_sql_scripts,
            error_details=None if result.success else result.message,
            backup_dir=str(result.backup_dir) if result.backup_dir else None,
            rollback_executed=result.rollback_executed,
            rollback_success=result.rollback_success,
        )
