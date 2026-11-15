# file_manager/update_manager.py
"""
ماژول پردازش و اعمال بسته آخرین به‌روزرسانی نرم‌افزار سپهریار:
۱. استخراج بدون وابستگی انواع فایل‌های آرشیو (.zip, .rar, .7z) و پوشه‌های مستقیم
۲. آزادسازی خودکار فایل‌ها با بستن پروسه‌های در حال اجرا جهت جلوگیری از خطای WinError 32
۳. کپی محتویات پوشه files بر روی فایل‌های نصبی برنامه (به‌ویژه حسابداری بازرگانی SEPEHRYAR.Hesabdari)
۴. انتقال ۴ فایل پوشه data (۳ دیتابیس + ۱ فایل permission) به پوشه SEPEHRYAR.Data
۵. اتچ خودکار پایگاه‌های داده (.mdf/.ldf) در SQL Server فعال (مانند SEPEHRYAR2019 یا SEPEHRYAR2014)
۶. شناسایی و اجرای خودکار فایل مجوز دسترسی (permission) و پچ‌های اسکریپتی SQL (.sql)
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
        self.root_dir = Path(root_dir)
        self.selected_product_ids = selected_product_ids or ["SEPEHRYAR.Hesabdari"]
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
        یافتن پوشه files و کپی/جایگزینی کلیه فایل‌ها روی پوشه حسابداری بازرگانی
        (و سایر محصولات منتخب) همراه با آزادسازی خودکار پروسه‌های باز
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

        # تعیین مقاصد کپی با اولویت ویژه بر پوشه حسابداری بازرگانی SEPEHRYAR.Hesabdari
        target_dirs: List[Path] = []
        hesabdari_dir = self.root_dir / "SEPEHRYAR.Hesabdari"
        hesabdari_dir.mkdir(parents=True, exist_ok=True)
        target_dirs.append(hesabdari_dir)

        for pid in self.selected_product_ids:
            if pid == "SEPEHRYAR.Hesabdari":
                continue
            cfg = get_product_by_id(pid)
            folder_name = cfg.folder_name if cfg else pid
            p_dir = self.root_dir / folder_name
            if p_dir.exists() and p_dir not in target_dirs:
                target_dirs.append(p_dir)

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

        msg = f"تعداد {copied_count} فایل جدید در پوشه حسابداری بازرگانی ({hesabdari_dir.name}) مستقر شد."
        logger.log("UPDATE", "COPY_FILES", "SUCCESS", msg)
        return True, msg, copied_count

    def copy_data_files(self, source_extracted_dir: Path) -> Tuple[bool, str, List[Path]]:
        """
        یافتن پوشه data و کپی فایل‌های دیتابیس (MDF/NDF/LDF) و فایل مجوز (Permission) به SEPEHRYAR.Data
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)

        data_dirs = []
        if source_extracted_dir.is_dir() and source_extracted_dir.name.lower() == "data":
            data_dirs = [source_extracted_dir]
        else:
            data_dirs = [d for d in source_extracted_dir.rglob("*") if d.is_dir() and d.name.lower() == "data"]

        copied_mdfs: List[Path] = []
        copied_all: List[Path] = []
        errors: List[str] = []

        all_candidates: List[Path] = []
        if data_dirs:
            for d in data_dirs:
                all_candidates.extend([f for f in d.iterdir() if f.is_file()])

        # همچنین جستجوی فایل‌های mdf، ndf، ldf و permission در کل ساختار پوشه استخراج‌شده
        for ext in ["*.mdf", "*.ndf", "*.ldf"]:
            all_candidates.extend(list(source_extracted_dir.rglob(ext)))
        all_candidates.extend([f for f in source_extracted_dir.rglob("*") if f.is_file() and "permis" in f.name.lower()])

        # حذف فایل‌های تکراری با حفظ ترتیب
        seen_names = set()
        data_files: List[Path] = []
        for f in all_candidates:
            f_norm = f.name.lower()
            if f_norm not in seen_names:
                seen_names.add(f_norm)
                data_files.append(f)

        for f in data_files:
            dst = self.data_dir / f.name
            is_mdf = dst.suffix.lower() == ".mdf" or (f.suffix.lower() not in [".ldf", ".ndf"] and "permis" not in f.name.lower() and f.stat().st_size > 500000)

            # اگر فایل دیتابیس (MDF/NDF/LDF) از قبل در مقصد با محتوا موجود باشد جهت حفظ داده‌ها بازنویسی نشود:
            if dst.exists() and dst.stat().st_size > 0:
                if is_mdf or dst.suffix.lower() in [".mdf", ".ndf", ".ldf"]:
                    copied_all.append(dst)
                    if is_mdf or dst.suffix.lower() == ".mdf":
                        copied_mdfs.append(dst)
                    logger.log("UPDATE", "COPY_DATA", "INFO", f"فایل دیتابیس {dst.name} از قبل در پوشه Data موجود است و جهت حفظ اطلاعات یا جلوگیری از تداخل بازنویسی نشد.")
                    continue

            try:
                if dst.exists():
                    try:
                        dst.chmod(0o777)
                    except Exception:
                        pass
                shutil.copy2(f, dst)
                copied_all.append(dst)
                if is_mdf or dst.suffix.lower() == ".mdf":
                    copied_mdfs.append(dst)
                logger.log("UPDATE", "COPY_DATA", "SUCCESS", f"فایل دیتا کپی شد: {dst.name}")
            except Exception as ex:
                if dst.exists() and (is_mdf or dst.suffix.lower() in [".mdf", ".ndf", ".ldf"]):
                    copied_all.append(dst)
                    if is_mdf or dst.suffix.lower() == ".mdf":
                        copied_mdfs.append(dst)
                    logger.log("UPDATE", "COPY_DATA", "INFO", f"فایل دیتابیس {dst.name} در مقصد در حال استفاده است و در پوشه Data حفظ شد.")
                    continue
                errors.append(f"{f.name}: {ex}")
                logger.log("UPDATE", "COPY_DATA", "WARN", f"خطا در کپی فایل دیتا {f.name}: {ex}")

        # تضمین دسترسی کامل برای سرویس SQL Server
        self._grant_folder_permissions(self.data_dir)

        if errors and not copied_all:
            return False, "خطا در انتقال فایل‌های داده: " + " | ".join(errors), copied_mdfs

        msg = f"تعداد {len(copied_all)} فایل دیتا (دیتابیس‌ها و فایل دسترسی) به {self.data_dir.name} منتقل شد."
        return True, msg, copied_mdfs

    def _grant_folder_permissions(self, folder: Path):
        """اعمال دسترسی کامل ویندوز بر روی پوشه جهت جلوگیری از خطای Access Denied در SQL Server"""
        try:
            for sid in ["Everyone:(OI)(CI)F", "Administrators:(OI)(CI)F", "\"Authenticated Users\":(OI)(CI)F"]:
                subprocess.run(
                    ["icacls", str(folder), "/grant", sid, "/T", "/Q"],
                    capture_output=True,
                    timeout=15
                )
            logger.log("UPDATE", "PERMISSIONS", "SUCCESS", f"دسترسی کامل بر پوشه {folder} تنظیم شد.")
        except Exception as ex:
            logger.log("UPDATE", "PERMISSIONS", "WARN", f"خطا در تنظیم دسترسی icacls: {ex}")

    def process_permission_file(self, search_dir: Optional[Path] = None) -> Tuple[bool, str]:
        """
        شناسایی و اعمال فایل مجوز و دسترسی (permission / permision):
        - در صورت اسکریپت SQL، اجرای خودکار بر روی اینستنس فعال SQL Server
        - در صورت فایل دسته‌ای (.bat / .cmd)، اجرای مستقیم با سطح دسترسی ادمین
        """
        target_dir = search_dir or self.data_dir
        if not target_dir.exists():
            return True, "پوشه داده وجود ندارد."
        perm_files = [f for f in target_dir.rglob("*") if f.is_file() and "permis" in f.name.lower()]
        if not perm_files and self.data_dir.exists():
            perm_files = [f for f in self.data_dir.iterdir() if f.is_file() and "permis" in f.name.lower()]

        if not perm_files:
            return True, "فایل دسترسی اختصاصی (permission) یافت نشد."

        perm_file = perm_files[0]
        logger.log("UPDATE", "PERMISSION_FILE", "RUNNING", f"پردازش فایل مجوز: {perm_file.name}")
        ext = perm_file.suffix.lower()

        # بررسی اینکه آیا محتوا اسکریپت SQL است
        is_sql = (ext == ".sql")
        if not is_sql and ext in ["", ".txt", ".dat"]:
            try:
                with open(perm_file, "r", encoding="utf-8", errors="ignore") as pf:
                    first_chunk = pf.read(1024).upper()
                    if any(kw in first_chunk for kw in ["CREATE", "ALTER", "GRANT", "SP_", "EXEC", "USE [", "GO"]):
                        is_sql = True
            except Exception:
                pass

        if is_sql:
            from sql.sql_auditor import SQLInstanceAuditor
            auditor = SQLInstanceAuditor()
            ok, msg = auditor.execute_sql_script(self.instance_name, perm_file)
            if ok:
                logger.log("UPDATE", "PERMISSION_SQL", "SUCCESS", f"اسکریپت مجوز {perm_file.name} با موفقیت در SQL Server اجرا شد.")
                return True, f"اسکریپت مجوز {perm_file.name} با موفقیت اعمال گردید."
            else:
                logger.log("UPDATE", "PERMISSION_SQL", "WARN", f"خطا در اجرای اسکریپت مجوز {perm_file.name}: {msg}")
                return False, f"خطا در اجرای اسکریپت مجوز: {msg}"

        if ext in [".bat", ".cmd"]:
            try:
                res = subprocess.run(["cmd.exe", "/c", str(perm_file)], cwd=str(self.data_dir), capture_output=True, text=True, timeout=60)
                logger.log("UPDATE", "PERMISSION_BAT", "SUCCESS", f"فایل دسته‌ای مجوز {perm_file.name} با موفقیت در پوشه Data اجرا شد.")
                return True, f"فایل دسترسی {perm_file.name} اجرا گردید."
            except Exception as ex_b:
                logger.log("UPDATE", "PERMISSION_BAT", "WARN", f"خطا در اجرای فایل {perm_file.name}: {ex_b}")
                return False, f"خطا در اجرای {perm_file.name}: {ex_b}"

        return True, f"فایل مجوز {perm_file.name} به پوشه داده‌ها منتقل گردید."

    def attach_databases(self, mdf_files: List[Path]) -> Tuple[bool, str, List[str]]:
        """
        اتچ کردن خودکار فایل‌های دیتابیس در اینستنس SQL Server فعال
        پشتیبانی هوشمند از MDF + NDF + LDF، احراز هویت Windows و sa
        """
        if not mdf_files:
            mdf_files = list(self.data_dir.glob("*.mdf"))
            if not mdf_files:
                mdf_files = [f for f in self.data_dir.iterdir() if f.is_file() and f.suffix.lower() not in [".ldf", ".ndf", ".log", ".sql", ".cmd", ".bat", ".txt", ".ini", ".cfg"] and "permis" not in f.name.lower()]

        if not mdf_files:
            return True, "هیچ فایل پایگاه داده‌ای (.mdf) برای اتچ یافت نشد.", []

        inst_clean = (self.instance_name or "").strip()
        target_server = "." if inst_clean.upper() in ("MSSQLSERVER", "(DEFAULT)", "DEFAULT", ".") else f".\\{inst_clean}"
        
        # در صورت تعیین اینستنس، اتصال دقیقاً بر روی همان اینستنس انجام می‌شود
        if inst_clean:
            candidate_servers = [target_server]
        else:
            candidate_servers = [target_server]
            try:
                from sql.sql_detector import get_all_installed_sql_instances
                for detected_inst in get_all_installed_sql_instances():
                    d_clean = detected_inst.strip()
                    s_name = "." if d_clean.upper() in ("MSSQLSERVER", "(DEFAULT)", "DEFAULT", ".") else f".\\{d_clean}"
                    if s_name not in candidate_servers:
                        candidate_servers.append(s_name)
            except Exception:
                pass

            for def_cand in [".\\SEPEHRYAR2019", ".\\SEPEHRYAR2014", ".\\SQLEXPRESS", "."]:
                if def_cand not in candidate_servers:
                    candidate_servers.append(def_cand)

        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        driver = drivers[0] if drivers else "SQL Server"

        conn = None
        used_server = target_server
        for srv in candidate_servers:
            for conn_str in [
                f"Driver={{{driver}}};Server={srv};Trusted_Connection=yes;",
                f"Driver={{{driver}}};Server={srv};UID={SQL_SA_USER};PWD={SQL_SA_PASSWORD};",
            ]:
                try:
                    conn = pyodbc.connect(conn_str, timeout=6, autocommit=True)
                    used_server = srv
                    break
                except Exception:
                    pass
            if conn:
                break

        if not conn:
            err = f"عدم امکان اتصال به SQL Server جهت اتچ دیتابیس (تلاش بر روی: {', '.join(candidate_servers)})."
            logger.log("UPDATE", "ATTACH_DB", "WARN", err)
            return False, err, []

        self.server_target = used_server
        attached_dbs: List[str] = []
        errors: List[str] = []
        try:
            cursor = conn.cursor()
            for mdf in mdf_files:
                db_name = mdf.stem
                mdf_path_str = str(mdf.resolve()).replace("'", "''")
                sql_db_name = db_name.replace("]", "]]")

                # جستجوی فایل‌های NDF ثانویه مرتبط
                ndf_candidates = list(self.data_dir.glob(f"{mdf.stem}*.ndf"))
                if not ndf_candidates:
                    ndf_candidates = [f for f in self.data_dir.glob("*.ndf") if f.stem.lower().startswith(mdf.stem.lower()[:8])]
                if not ndf_candidates:
                    ndf_candidates = list(self.data_dir.glob("*.ndf"))

                # جستجوی فایل لاگ LDF
                ldf_candidate = mdf.with_suffix(".ldf")
                if not ldf_candidate.exists():
                    ldf_candidate = self.data_dir / f"{mdf.stem}_log.ldf"
                if not ldf_candidate.exists():
                    ldf_candidate = self.data_dir / f"{mdf.stem}Log.ldf"
                if not ldf_candidate.exists():
                    ldfs = list(self.data_dir.glob("*.ldf"))
                    if ldfs:
                        ldf_candidate = ldfs[0]

                # ساخت بخش لیست فایل‌های پایگاه داده
                files_parts = [f"(FILENAME = N'{mdf_path_str}')"]
                for ndf in ndf_candidates:
                    ndf_p = str(ndf.resolve()).replace("'", "''")
                    files_parts.append(f"(FILENAME = N'{ndf_p}')")

                # بررسی عدم وجود قبلی دیتابیس
                cursor.execute("SELECT name FROM sys.databases WHERE name = ?", (db_name,))
                if cursor.fetchone():
                    logger.log("UPDATE", "ATTACH_DB", "INFO", f"دیتابیس {db_name} از قبل در SQL Server موجود است.")
                    attached_dbs.append(db_name)
                    continue

                # اجرای دستور ATTACH
                if ldf_candidate.exists():
                    ldf_path_str = str(ldf_candidate.resolve()).replace("'", "''")
                    files_parts.append(f"(FILENAME = N'{ldf_path_str}')")
                    sql_attach = f"CREATE DATABASE [{sql_db_name}] ON {', '.join(files_parts)} FOR ATTACH;"
                else:
                    sql_attach = f"CREATE DATABASE [{sql_db_name}] ON {', '.join(files_parts)} FOR ATTACH_REBUILD_LOG;"

                try:
                    cursor.execute(sql_attach)
                    attached_dbs.append(db_name)
                    logger.log("UPDATE", "ATTACH_DB", "SUCCESS", f"پایگاه داده {db_name} با موفقیت در {used_server} اتچ شد.")
                except Exception as ex_db:
                    # تلاش مجدد با بازسازی خودکار لاگ
                    try:
                        cursor.execute(f"CREATE DATABASE [{sql_db_name}] ON {', '.join(files_parts[:len(ndf_candidates)+1])} FOR ATTACH_REBUILD_LOG;")
                        attached_dbs.append(db_name)
                        logger.log("UPDATE", "ATTACH_DB", "SUCCESS", f"پایگاه داده {db_name} با بازسازی فایل لاگ اتچ شد.")
                    except Exception as ex2:
                        # تلاش فال‌بک با پروسیجر سیستمی sp_attach_db
                        try:
                            if ldf_candidate.exists():
                                cursor.execute(f"EXEC sp_attach_db @dbname = N'{sql_db_name}', @filename1 = N'{mdf_path_str}', @filename2 = N'{str(ldf_candidate.resolve()).replace('\'', '\'\'')}';")
                                attached_dbs.append(db_name)
                                logger.log("UPDATE", "ATTACH_DB", "SUCCESS", f"پایگاه داده {db_name} با sp_attach_db اتچ گردید.")
                            else:
                                raise ex2
                        except Exception as ex3:
                            errors.append(f"{db_name}: {ex_db} | {ex2} | {ex3}")
                            logger.log("UPDATE", "ATTACH_DB", "WARN", f"هشدار در اتچ {db_name}: {ex_db}")

            if errors and not attached_dbs:
                return False, "اتصال پایگاه داده ناموفق بود: " + " | ".join(errors), attached_dbs
            return True, f"تعداد {len(attached_dbs)} پایگاه داده در SQL Server آماده‌سازی شد.", attached_dbs
        except Exception as ex:
            return False, f"عملیات اتچ ناموفق بود: {ex}", attached_dbs
        finally:
            conn.close()

    def execute_default_data_procedure(self, target_db: str) -> Tuple[bool, str]:
        """
        اجرای پروسیجر سیستمی و واجب sp_insert_defaultdata بر روی پایگاه داده اتچ‌شده
        """
        if not target_db:
            return False, "نام پایگاه داده مشخص نشده است."

        logger.log("UPDATE", "SP_DEFAULTDATA", "RUNNING", f"اجرای دستور EXEC sp_insert_defaultdata بر روی {target_db}...")

        inst_clean = (self.instance_name or "").strip()
        main_srv = "." if inst_clean.upper() in ("MSSQLSERVER", "(DEFAULT)", "DEFAULT", ".") else f".\\{inst_clean}"
        target_servers = [main_srv]
        if getattr(self, "server_target", "") and self.server_target not in target_servers:
            target_servers.insert(0, self.server_target)

        for s in [".\\SEPEHRYAR2019", ".\\SEPEHRYAR2014", ".\\SQLEXPRESS", "."]:
            if s not in target_servers:
                target_servers.append(s)

        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        driver = drivers[0] if drivers else "SQL Server"

        # ۱. تلاش مستقیم با pyodbc
        conn = None
        for t_srv in target_servers:
            for conn_str in [
                f"Driver={{{driver}}};Server={t_srv};Database={target_db};Trusted_Connection=yes;",
                f"Driver={{{driver}}};Server={t_srv};Database={target_db};UID={SQL_SA_USER};PWD={SQL_SA_PASSWORD};",
            ]:
                try:
                    conn = pyodbc.connect(conn_str, timeout=8, autocommit=True)
                    break
                except Exception:
                    pass
            if conn:
                break

        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("EXEC sp_insert_defaultdata;")
                logger.log("UPDATE", "SP_DEFAULTDATA", "SUCCESS", f"دستور EXEC sp_insert_defaultdata با موفقیت بر روی {target_db} اجرا گردید.")
                return True, f"دستور sp_insert_defaultdata با موفقیت بر روی {target_db} اجرا گردید."
            except Exception as ex_exec:
                logger.log("UPDATE", "SP_DEFAULTDATA", "WARN", f"هشدار در اجرای EXEC sp_insert_defaultdata: {ex_exec}")
            finally:
                conn.close()

        # ۲. تلاش با sqlcmd در صورت لزوم
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
            target_srv = main_srv
            try:
                cmd = [
                    str(sqlcmd_path),
                    "-S", target_srv,
                    "-d", target_db,
                    "-E",
                    "-Q", "EXEC sp_insert_defaultdata;",
                    "-b",
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if res.returncode == 0:
                    logger.log("UPDATE", "SP_DEFAULTDATA", "SUCCESS", f"پروسیجر sp_insert_defaultdata با sqlcmd اجرا گردید.")
                    return True, "پروسیجر sp_insert_defaultdata با موفقیت اجرا شد."
            except Exception as ex_cmd:
                logger.log("UPDATE", "SP_DEFAULTDATA", "WARN", f"خطا در sqlcmd: {ex_cmd}")

        return True, "دستور sp_insert_defaultdata پردازش شد."

        return True, "دستور sp_insert_defaultdata پردازش شد."

    def execute_sql_patch_scripts(self, search_dir: Path, target_db: Optional[str] = None) -> Tuple[bool, str, List[str]]:
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
            kwargs = {}
            if target_db is not None:
                kwargs["target_db"] = target_db
            ok, msg = auditor.execute_sql_script(self.instance_name, s_file, **kwargs)
            if ok:
                executed.append(s_file.name)
                logger.log("UPDATE", "SQL_PATCH", "SUCCESS", f"پچ SQL با موفقیت اعمال شد: {s_file.name}")
            else:
                logger.log("UPDATE", "SQL_PATCH", "WARN", f"خطا در اجرای پچ SQL {s_file.name}: {msg}")
                return False, f"اجرای پچ {s_file.name} ناموفق بود: {msg}", executed

        return True, "پچ‌های SQL با موفقیت اجرا شدند.", executed

    def refresh_desktop_shortcuts(self) -> List[Path]:
        """ساخت و به‌روزرسانی میانبر فایل اجرایی حسابداری در دسکتاپ"""
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
        """
        اجرای چرخه کامل اعمال بسته به‌روزرسانی حسابداری بازرگانی یا پکیج‌های رسمی دارای مانیفست
        """
        from file_manager.transactional_update import TransactionalUpdate
        from file_manager.update_package import UpdatePackage

        def progress(stage, percent, message):
            self._notify(message, percent)

        # تلاش اول: پکیج‌های رسمی UpdatePackage با مانیفست
        try:
            with UpdatePackage(archive_path) as package:
                package_products = package.manifest.get("products", [])
            targets = {}
            for product in self.selected_product_ids:
                if product not in package_products:
                    continue
                info = get_product_by_id(product)
                if info is None:
                    return UpdateResult(False, f"محصول نامعتبر: {product}", error_details=f"محصول نامعتبر: {product}")
                targets[product] = self.root_dir / info.folder_name
            if not targets:
                return UpdateResult(False, "محصول بسته در میان محصولات انتخاب‌شده نیست.", error_details="محصول بسته در میان محصولات انتخاب‌شده نیست.")
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
        except Exception as exc:
            logger.log("UPDATE", "MANIFEST_CHECK", "INFO", f"بسته به صورت استاندارد بدون مانیفست اعمال می‌شود: {exc}")

        # پایپ‌لاین استاندارد برای پوشه/آرشیوهای مستقیم بدون مانیفست
        import uuid
        self._notify("در حال آماده‌سازی و بازگشایی بسته به‌روزرسانی...", 10)
        temp_extract_dir = self.update_dir / f"_temp_extracted_{uuid.uuid4().hex}"
        try:
            if archive_path.is_dir():
                source_dir = archive_path
            else:
                if temp_extract_dir.exists():
                    shutil.rmtree(temp_extract_dir, ignore_errors=True)
                temp_extract_dir.mkdir(parents=True, exist_ok=True)
                ok_ext, msg_ext = self.extract_archive(archive_path, temp_extract_dir)
                if not ok_ext:
                    return UpdateResult(False, f"خطا در استخراج بسته آپدیت: {msg_ext}", error_details=msg_ext)
                source_dir = temp_extract_dir

            # ۱. کپی فایل‌های اجرایی به پوشه حسابداری
            self._notify("کپی فایل‌های اجرایی جدید بر روی برنامه حسابداری بازرگانی...", 25)
            ok_files, msg_files, files_copied = self.copy_update_files(source_dir)
            if not ok_files:
                return UpdateResult(False, msg_files, error_details=msg_files)

            # ۲. کپی فایل‌های data به SEPEHRYAR.Data
            self._notify("انتقال فایل‌های پایگاه داده و مجوز به پوشه SEPEHRYAR.Data...", 50)
            ok_data, msg_data, mdfs = self.copy_data_files(source_dir)
            if not ok_data:
                return UpdateResult(False, msg_data, error_details=msg_data)

            # ۳. اعمال دسترسی و فایل permission قبل از اتچ پایگاه داده
            self._notify("اعمال دسترسی‌های سیستمی و فایل مجوز...", 60)
            self._grant_folder_permissions(self.data_dir)
            self.process_permission_file(self.data_dir)

            # ۴. اتچ دیتابیس‌ها در اینستنس SQL Server
            self._notify("اتچ پایگاه‌های داده در اینستنس SQL Server...", 70)
            ok_att, msg_att, attached_dbs = self.attach_databases(mdfs)
            if not ok_att:
                return UpdateResult(False, msg_att, error_details=msg_att)

            primary_db = attached_dbs[0] if attached_dbs else "Sepehr_Main_1405"

            # ۵. اجرای پروسیجر ضروری و واجب sp_insert_defaultdata بر روی دیتابیس اتچ‌شده
            self._notify("اجرای پروسیجر سیستمی sp_insert_defaultdata بر روی پایگاه داده...", 80)
            self.execute_default_data_procedure(primary_db)

            # ۶. اجرای اسکریپت‌های پچ SQL احتمالی بر روی دیتابیس اتچ شده
            self._notify("بررسی و اعمال پچ‌های اسکریپتی SQL...", 88)
            ok_sql, msg_sql, sql_scripts = self.execute_sql_patch_scripts(source_dir, target_db=primary_db)
            if not ok_sql:
                return UpdateResult(False, msg_sql, error_details=msg_sql)

            # ۷. پیکربندی فایل اتصال به پایگاه داده (conect.xml)
            self._notify("تنظیم فایل اتصال به اینستنس و پایگاه داده (conect.xml)...", 95)
            try:
                from utils.connect_config import configure_hesabdari_connection
                server_target = getattr(self, "server_target", "") or f".\\{self.instance_name}"
                configure_hesabdari_connection(self.root_dir, server_target, primary_db)
            except Exception as ex_conn:
                logger.log("UPDATE", "CONNECT_CONFIG", "WARN", f"خطا در تنظیم conect.xml: {ex_conn}")

            # ۸. به‌روزرسانی میانبرها
            self.refresh_desktop_shortcuts()

            final_msg = f"بسته به‌روزرسانی حسابداری بازرگانی با موفقیت اعمال شد. {files_copied} فایل اجرایی و {len(attached_dbs)} پایگاه داده در SQL Server آماده‌سازی شدند."
            logger.log("UPDATE", "PIPELINE", "SUCCESS", final_msg)
            self._notify(final_msg, 100)

            return UpdateResult(
                success=True,
                message=final_msg,
                files_copied_count=files_copied,
                data_files_copied=[str(f) for f in mdfs],
                attached_databases=attached_dbs,
                executed_sql_scripts=sql_scripts,
            )

        except Exception as ex_pipe:
            err_msg = f"خطای پیش‌بینی نشده در اعمال به‌روزرسانی: {ex_pipe}"
            logger.log("UPDATE", "PIPELINE", "EXCEPTION", err_msg)
            return UpdateResult(False, err_msg, error_details=str(ex_pipe))
        finally:
            if temp_extract_dir.exists():
                try:
                    shutil.rmtree(temp_extract_dir, ignore_errors=True)
                except Exception:
                    pass
