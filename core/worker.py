# core/worker.py
"""
ترد پردازشی و ناهمگام (QThread Worker) برای اجرای بدون وقفه و واقعی کل فرایند نصب
Asynchronous QThread installation worker preventing UI freezing
"""

from pathlib import Path
from typing import List, Optional, Tuple
from PySide6.QtCore import QThread, Signal

from config.settings import SETUP_DIR, requires_sql
from core.orchestrator import get_install_stages_for_products
from downloader.ssms_downloader import SSMSDownloader
from file_manager.file_copier import FileCopier, create_sepehryar_root_structure
from app_logging.app_logger import logger
from packages.product_catalog import (
    get_product_by_id,
    resolve_installed_exe_path,
    resolve_product_source_dir,
)
from prerequisites.prereq_installer import PrerequisiteManager
from sql.sql_installer import SQLServerInstaller
from utils.shortcut_manager import create_shortcuts_for_product
from verification.final_verifier import FinalVerifier, VerificationSummary


class InstallWorker(QThread):
    """
    اجرای ترتیبی مراحل نصب روی ترد مجزا به صورت هوشمند و داینامیک
    """
    sig_stage_started = Signal(int, str)             # stage_idx, stage_title
    sig_stage_finished = Signal(int, bool, str)      # stage_idx, success, details
    sig_progress = Signal(int, int, str)             # overall_percent, stage_percent, current_op
    sig_log = Signal(object)                         # LogEntry
    sig_error = Signal(str, str, bool)               # stage_id, error_message, can_retry
    sig_finished = Signal(bool, object)              # success, VerificationSummary

    def __init__(
        self,
        selected_drive: str,
        selected_product_ids: List[str],
        install_mode: str = "server",
        sql_version: str = "2019",
        sql_instance_name: Optional[str] = None,
        server_target: str = "",
        update_archive_path: Optional[Path] = None,
        parent=None,
        checkpoint_path: Optional[Path] = None,
        resume_installation: bool = True,
        force_new_sql_instance: bool = False,
    ):
        super().__init__(parent)
        from config.settings import get_sql_instance_name
        self.selected_drive = selected_drive
        self.selected_product_ids = selected_product_ids
        self.install_mode = install_mode
        self.sql_version = str(sql_version)
        self.sql_instance_name = (sql_instance_name or get_sql_instance_name(self.sql_version)).strip()
        self.force_new_sql_instance = force_new_sql_instance
        self._requested_sql_version = self.sql_version
        self.server_target = server_target
        self.update_archive_path = update_archive_path
        has_upd = update_archive_path is not None
        self.stages = get_install_stages_for_products(
            selected_product_ids,
            install_mode=install_mode,
            sql_version=self.sql_version,
            has_update=has_upd,
        )
        self.is_cancelled = False
        self.retry_from_stage_idx: Optional[int] = None
        self.skipped_stage_ids: set = set()
        self.root_path: Optional[Path] = None
        self.setup_target_dir: Optional[Path] = None
        self._active_copier: Optional[FileCopier] = None
        self.checkpoint_path = checkpoint_path
        self.resume_installation = resume_installation
        self._checkpoint = None
        self._lock_held = False

    def skip_current_stage(self, stage_idx: int):
        if 0 <= stage_idx < len(self.stages):
            stage = self.stages[stage_idx]
            logger.log("WORKER", stage.id, "SKIPPED", f"مرحله «{stage.title_fa}» توسط کاربر نادیده گرفته شد و ادامه می‌یابد.")
            self.skipped_stage_ids.add(stage.id)
            if self._checkpoint:
                self._checkpoint.skipped(stage.id)
            self.retry_from_stage_idx = stage_idx + 1

    def cancel(self):
        self.is_cancelled = True
        logger.log("WORKER", "CANCEL", "CANCELLING", "درخواست لغو ثبت شد؛ منتظر پایان عملیات جاری هستیم.")
        if self._active_copier is not None:
            self._active_copier.request_cancel()

    def run(self):
        if self.checkpoint_path is None:
            self._run_stages()
            return
        from config.settings import EXE_FULL_DIR, PRODUCTS_CONFIG
        from core.install_checkpoint import InstallCheckpoint, request_identity, source_identity
        from file_manager.transactional_update import TransactionalUpdate
        from utils.durable_state import installation_lock
        root = self.checkpoint_path.parent.parent
        try:
            with installation_lock(root):
                self._lock_held = True
                targets = {pid: root / PRODUCTS_CONFIG[pid]["folder_name"] for pid in self.selected_product_ids}
                TransactionalUpdate(root, targets).recover_pending()
                request = request_identity(self.selected_product_ids, self.install_mode, self._requested_sql_version,
                                           self.server_target, self.update_archive_path)
                sources = [SETUP_DIR, EXE_FULL_DIR / "_shared", EXE_FULL_DIR / "shared_manifest.json"] + [EXE_FULL_DIR / PRODUCTS_CONFIG[pid]["folder_name"] for pid in self.selected_product_ids]
                self._checkpoint = InstallCheckpoint(self.checkpoint_path, request, source_identity(sources), self.resume_installation)
                self.root_path, self.setup_target_dir = root, root / "SEPEHRYAR.Setup"
                self.sql_version = self._checkpoint.state["sql_version"]
                self._run_stages()
        except Exception as exc:
            self.sig_error.emit("resume", str(exc), True)
            self.sig_finished.emit(False, None)
        finally:
            self._lock_held = False

    def _can_resume_stage(self, stage):
        if not self._checkpoint:
            return False
        if stage in self._checkpoint.state.get("skipped", []):
            self.skipped_stage_ids.add(stage)
            return True
        if stage not in self._checkpoint.state["completed"]:
            return False
        if stage == "create_folders":
            from config.settings import SUBFOLDERS
            return all((self.root_path / folder).is_dir() for folder in SUBFOLDERS)
        if stage in ("copy_setup", "copy_app", "apply_update"):
            return self._checkpoint.valid_files(stage)
        if stage in ("sql_server", "sql_config"):
            return self._step_sql_config()[0]
        return False  # Recheck prerequisites, shortcuts and final verification.

    def _stage_files(self, stage):
        if stage == "copy_setup":
            return [path for path in self.setup_target_dir.rglob("*") if path.is_file()
                    and path != self.checkpoint_path and path.suffix.lower() != ".log"]
        if stage in ("copy_app", "apply_update"):
            from config.settings import PRODUCTS_CONFIG
            return [path for pid in self.selected_product_ids
                    for path in (self.root_path / PRODUCTS_CONFIG[pid]["folder_name"]).rglob("*") if path.is_file()]
        return []

    def _run_stages(self):
        logger.log("WORKER", "START", "RUNNING", f"آغاز اجرای پایپ‌لاین نصب در درایو {self.selected_drive}")
        total_stages = len(self.stages)
        start_idx = self.retry_from_stage_idx or 0
        self.retry_from_stage_idx = None

        if start_idx >= total_stages:
            self.sig_finished.emit(True, None)
            return

        for idx in range(start_idx, total_stages):
            if self.is_cancelled:
                logger.log("WORKER", "CANCEL", "CANCELLED", "فرایند توسط کاربر لغو گردید.")
                self.sig_error.emit("cancelled", "فرایند نصب لغو گردید.", False)
                self.sig_finished.emit(False, None)
                return

            stage = self.stages[idx]

            # اگر این مرحله قبلاً توسط کاربر صرف‌نظر شده بود
            if stage.id in self.skipped_stage_ids:
                self.sig_stage_finished.emit(idx, True, "توسط کاربر صرف‌نظر شد.")
                self.sig_progress.emit(int((idx + 1) * 100 / total_stages), 100, stage.title_fa)
                continue

            # رد شدن زنجیره‌ای: اگر کاربر از نصب SQL Server رد شده باشد، تست اتصال SQL نیز نادیده گرفته می‌شود
            if stage.id == "sql_config" and "sql_server" in self.skipped_stage_ids:
                logger.log("WORKER", stage.id, "SKIPPED", "به دلیل صرف‌نظر از نصب پایگاه داده، تنظیمات SQL نادیده گرفته شد.")
                self.skipped_stage_ids.add(stage.id)
                self.sig_stage_finished.emit(idx, True, "به دلیل رد شدن نصب پایگاه داده، این مرحله نادیده گرفته شد.")
                self.sig_progress.emit(int((idx + 1) * 100 / total_stages), 100, stage.title_fa)
                continue

            if self._checkpoint:
                if self._can_resume_stage(stage.id):
                    self.sig_stage_finished.emit(idx, True, "مرحله قبلی بررسی شد و نیازی به تکرار ندارد.")
                    self.sig_progress.emit(int((idx + 1) * 100 / total_stages), 100, stage.title_fa)
                    continue
                if stage.id in ("copy_setup", "copy_app", "apply_update", "create_folders"):
                    self._checkpoint.invalidate_from(stage.id, [item.id for item in self.stages])
                self._checkpoint.start(stage.id)
            self.sig_stage_started.emit(idx, stage.title_fa)
            overall_base = int((idx / total_stages) * 100)
            self.sig_progress.emit(overall_base, 0, f"شروع {stage.title_fa}...")

            success = False
            details = ""
            summary = None

            try:
                if stage.id == "create_folders":
                    success, details = self._step_create_folders()

                elif stage.id == "copy_setup":
                    success, details = self._step_copy_setup(overall_base, total_stages)

                elif stage.id == "prerequisites":
                    success, details = self._step_prerequisites()

                elif stage.id == "sql_server":
                    success, details = self._step_sql_server(overall_base, total_stages)

                elif stage.id == "sql_config":
                    success, details = self._step_sql_config()

                elif stage.id == "ssms":
                    success, details = self._step_ssms(overall_base, total_stages)

                elif stage.id == "copy_app":
                    success, details = self._step_copy_app(overall_base, total_stages)

                elif stage.id == "apply_update":
                    success, details = self._step_apply_update(overall_base, total_stages)

                elif stage.id == "shortcuts":
                    success, details = self._step_shortcuts()

                elif stage.id == "verify":
                    success, details, summary = self._step_verify()

                else:
                    details = f"مرحله نصب ناشناخته است: {stage.id}"

            except Exception as ex:
                logger.log("WORKER", stage.id, "EXCEPTION", str(ex), error=str(ex))
                success = False
                details = f"خطای پیش‌بینی نشده: {ex}"

            self._active_copier = None
            if self.is_cancelled:
                self.sig_stage_finished.emit(idx, False, "فرایند نصب لغو گردید.")
                self.sig_error.emit("cancelled", "فرایند نصب لغو گردید.", False)
                self.sig_finished.emit(False, summary)
                return

            if not success:
                if self._checkpoint:
                    self._checkpoint.state["status"] = "failed"
                    self._checkpoint.save()
                self.retry_from_stage_idx = idx
                self.sig_stage_finished.emit(idx, False, details)
                self.sig_progress.emit(overall_base, 0, details)
                self.sig_error.emit(stage.id, details, True)
                self.sig_finished.emit(False, summary)
                return

            if self._checkpoint:
                self._checkpoint.completed(stage.id, self._stage_files(stage.id), self.sql_version)
            self.sig_stage_finished.emit(idx, True, details)
            overall_done = int(((idx + 1) / total_stages) * 100)
            self.sig_progress.emit(overall_done, 100, f"{stage.title_fa} با موفقیت انجام شد.")

            if stage.id == "verify":
                self.sig_finished.emit(True, summary)
                return

        self.sig_finished.emit(True, None)

    # ==================== پیاده‌سازی متدهای اختصاصی هر مرحله ====================

    def _step_create_folders(self) -> Tuple[bool, str]:
        needs_setup = True
        folder_dict = create_sepehryar_root_structure(self.selected_drive, needs_setup=needs_setup)
        self.root_path = folder_dict["root"]
        self.setup_target_dir = folder_dict.get("SEPEHRYAR.Setup")
        return True, f"ساختار درایو در {self.root_path} ایجاد گردید."

    def _step_copy_setup(self, overall_base: int, total_stages: int) -> Tuple[bool, str]:
        if not self.setup_target_dir:
            return False, "پوشه مقصد Setup آماده نیست."

        needs_sql = requires_sql(self.selected_product_ids, install_mode=self.install_mode)
        # در صورتی که دیتابیس نیاز نباشد کلیه فایل‌های SQL حذف می‌شوند
        # در صورت انتخاب 2014، فایل‌های 2019 و SSMS کپی نمی‌شوند؛ و در صورت انتخاب 2019، پوشه ستاپ 2014 کپی نمی‌شود
        if not needs_sql:
            exclude_patterns = ["^sql$", "2019", "ssms"]
        elif str(self.sql_version) == "2014":
            exclude_patterns = ["2019", "ssms"]
        else:  # 2019
            exclude_patterns = ["^sql$"]

        copier = FileCopier()
        self._active_copier = copier
        tot_files, tot_bytes = copier.calculate_total_size([SETUP_DIR], exclude_patterns=exclude_patterns)
        if tot_files == 0:
            return False, "پوشه Setup وجود ندارد یا فاقد فایل قابل نصب است."

        def on_copy_prog(copied, total, cur_file, cur_idx, tfiles):
            if self.is_cancelled:
                copier.request_cancel()
            pct = int((copied / total) * 100) if total > 0 else 50
            sub_contrib = int(pct / total_stages)
            cur_overall = min(overall_base + sub_contrib, 99)
            self.sig_progress.emit(cur_overall, pct, f"کپی Setup: {cur_file} ({cur_idx}/{tfiles})")

        copier.progress_callback = on_copy_prog
        c_bytes, c_files, errs = copier.copy_directory_contents(
            SETUP_DIR,
            self.setup_target_dir,
            stage_name="COPY_SETUP",
            overall_total_bytes=tot_bytes,
            overall_total_files=tot_files,
            exclude_patterns=exclude_patterns,
        )
        if errs > 0:
            return False, f"کپی {errs} فایل پکیج Setup ناموفق بود؛ جزئیات در گزارش ثبت شده است."
        return True, f"{c_files} فایل پکیج Setup کپی گردید."

    def _step_prerequisites(self) -> Tuple[bool, str]:
        pm = PrerequisiteManager()
        results = [
            ("Crystal Reports", pm.install_crystal_reports()),
            ("Stimulsoft", pm.install_stimulsoft()),
            ("فونت‌های فارسی", pm.install_farsi_fonts()),
        ]
        failed = [name for name, ok in results if not ok]
        if failed:
            return False, "نصب پیش‌نیازهای زیر ناموفق بود: " + "، ".join(failed)
        return True, "پیش‌نیازها و فونت‌ها با موفقیت پیکربندی شدند."

    def _step_sql_server(self, overall_base: int, total_stages: int) -> Tuple[bool, str]:
        def on_sql_prog(msg: str, pct: int):
            p = max(0, min(pct, 100))
            sub_contrib = int(p / total_stages)
            self.sig_progress.emit(overall_base + sub_contrib, p, msg)

        installer = SQLServerInstaller(
            progress_callback=on_sql_prog,
            sql_version=self.sql_version,
            instance_name=self.sql_instance_name,
            force_new_instance=getattr(self, "force_new_sql_instance", False),
        )
        ok, res = installer.execute_flow(self.setup_target_dir or SETUP_DIR)
        if not ok:
            return False, f"نصب یا اعتبارسنجی SQL Server {self.sql_version} ناموفق بود: {res.error_message}"
        # نصب‌کننده ممکن است اینستنس موجود نسخه دیگر را انتخاب کرده باشد.
        self.sql_version = installer.sql_version
        self.sql_instance_name = getattr(res, "instance_name", None) or getattr(installer, "instance_name", self.sql_instance_name)
        return True, f"اتصال به SQL Server {self.sql_version} ({res.instance_name}) برقرار شد."

    def _step_sql_config(self) -> Tuple[bool, str]:
        # تست نهایی سرویس و اتصال
        from sql.sql_verifier import verify_sql_connection
        from config.settings import get_sql_instance_name, SQL_SA_USER, SQL_SA_PASSWORD
        inst_name = self.sql_instance_name or get_sql_instance_name(self.sql_version)
        res = verify_sql_connection(instance_name=inst_name, sql_user=SQL_SA_USER, sql_password=SQL_SA_PASSWORD)
        if res.is_connected:
            return True, f"ارتباط با پایگاه داده پایدار است ({res.auth_method})."

        # فال‌بک با Windows Authentication
        res_win = verify_sql_connection(instance_name=inst_name)
        if res_win.is_connected:
            return True, f"ارتباط با پایگاه داده برقرار است ({res_win.auth_method})."

        return False, f"خطای تنظیمات پایگاه داده: {res.error_message}"

    def _step_ssms(self, overall_base: int, total_stages: int) -> Tuple[bool, str]:
        if self.sql_version == "2014":
            return True, "در نسخه SQL Server 2014 نیازی به دانلود و نصب جداگانه SSMS نیست."

        def on_ssms_prog(downloaded, total, pct, status_str):
            sub_contrib = int(pct / total_stages)
            self.sig_progress.emit(overall_base + sub_contrib, int(pct), status_str)

        try:
            downloader = SSMSDownloader(progress_callback=on_ssms_prog)
            dest = self.setup_target_dir or SETUP_DIR
            ok, msg = downloader.download_and_install(dest)
            if not ok:
                logger.log("WORKER", "SSMS", "WARN", f"دانلود SSMS انجام نشد: {msg} — اما نصب اصلی برنامه ادامه می‌یابد.")
                return True, "نصب برنامه ادامه یافت (ابزار اختیاری SSMS در دسترس نبود)."
            return True, msg
        except Exception as ex_ssms:
            logger.log("WORKER", "SSMS", "WARN", f"خطا در SSMS: {ex_ssms} — ادامه نصب برنامه.")
            return True, "نصب برنامه ادامه یافت (صرف‌نظر از ابزار اختیاری SSMS)."

    def _step_copy_app(self, overall_base: int, total_stages: int) -> Tuple[bool, str]:
        from config.settings import EXE_FULL_DIR
        from file_manager.transactional_update import TransactionalUpdate
        from utils.durable_state import contained_path, installation_lock
        import json
        if not self.root_path or not self.selected_product_ids:
            return False, "مسیر نصب یا محصولات مشخص نشده‌اند."
        try:
            targets, destinations = {}, []
            manifest_path = EXE_FULL_DIR / "shared_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            for pid in self.selected_product_ids:
                source = resolve_product_source_dir(pid)
                if not source or not source.is_dir():
                    return False, f"پوشه مبدأ محصول {pid} یافت نشد."
                info = get_product_by_id(pid)
                target = self.root_path / (info.folder_name if info else pid)
                targets[pid] = target
                destinations.extend(contained_path(target, file.relative_to(source).as_posix()) for file in source.rglob("*") if file.is_file())
                for entry in manifest.get("products", {}).get(pid, {}).get("shared_files", []):
                    destinations.append(contained_path(target, entry.get("relative_path", entry["shared_name"])))
            engine = TransactionalUpdate(self.root_path, targets)
            action = lambda: self._copy_app_files(overall_base, total_stages)
            if self._lock_held:
                return engine.protect_file_deployment(destinations, action)
            with installation_lock(self.root_path):
                return engine.protect_file_deployment(destinations, action)
        except Exception as exc:
            return False, str(exc)

    def _copy_app_files(self, overall_base: int, total_stages: int) -> Tuple[bool, str]:
        if not self.root_path:
            return False, "مسیر ریشه نصب مشخص نیست."

        from config.settings import EXE_FULL_DIR

        if not self.selected_product_ids:
            return False, "هیچ محصولی برای نصب انتخاب نشده است."
        sources: List[Path] = []
        for pid in self.selected_product_ids:
            src = resolve_product_source_dir(pid)
            if not src or not src.is_dir():
                return False, f"پوشه مبدأ محصول {pid} یافت نشد."
            sources.append(src)

        copier = FileCopier()
        self._active_copier = copier
        tot_files, tot_bytes = copier.calculate_total_size(sources)

        total_copied_bytes = 0
        total_copied_files = 0

        for pid in self.selected_product_ids:
            src = resolve_product_source_dir(pid)
            if not src or not src.exists():
                return False, f"پوشه مبدأ محصول {pid} دیگر در دسترس نیست."

            cfg = get_product_by_id(pid)
            folder_name = cfg.folder_name if cfg else pid
            dst = self.root_path / folder_name

            def on_copy_prog(copied, total, cur_file, cur_idx, tfiles):
                if self.is_cancelled:
                    copier.request_cancel()
                pct = int((copied / total) * 100) if total > 0 else 50
                sub_contrib = int(pct / total_stages)
                cur_overall = min(overall_base + sub_contrib, 99)
                self.sig_progress.emit(cur_overall, pct, f"کپی {folder_name}: {cur_file} ({cur_idx}/{tfiles})")

            copier.progress_callback = on_copy_prog
            cb, cf, errors = copier.copy_directory_contents(
                src,
                dst,
                stage_name=f"COPY_{pid}",
                overall_offset_bytes=total_copied_bytes,
                overall_total_bytes=tot_bytes,
                file_offset_idx=total_copied_files,
                overall_total_files=tot_files,
                preserve_existing_config=True,
            )
            total_copied_bytes += cb
            total_copied_files += cf
            if errors:
                return False, f"کپی {errors} فایل محصول {folder_name} ناموفق بود."
            if self.is_cancelled:
                return False, "کپی فایل‌ها لغو گردید."

        # ── کپی فایل‌های مشترک از _shared/ به هر محصول ──
        shared_dir = EXE_FULL_DIR / "_shared"
        manifest_file = EXE_FULL_DIR / "shared_manifest.json"

        if shared_dir.exists() or manifest_file.exists():
            if not shared_dir.is_dir() or not manifest_file.is_file():
                return False, "پوشه فایل‌های مشترک یا فهرست shared_manifest.json موجود نیست."
            import json
            try:
                with open(manifest_file, "r", encoding="utf-8") as mf:
                    manifest = json.load(mf)

                shared_copied = 0
                for pid in self.selected_product_ids:
                    cfg = get_product_by_id(pid)
                    folder_name = cfg.folder_name if cfg else pid
                    dst = self.root_path / folder_name

                    product_manifest = manifest["products"][folder_name]
                    shared_files = product_manifest["shared_files"]

                    for sf_info in shared_files:
                        shared_name = sf_info.get("shared_name", "")
                        rel_path = sf_info.get("relative_path", shared_name)
                        src_file = shared_dir / shared_name
                        dst_file = dst / rel_path

                        if self.is_cancelled:
                            return False, "کپی فایل‌های مشترک لغو گردید."
                        if not shared_name or not src_file.is_file():
                            return False, f"فایل مشترک موردنیاز موجود نیست: {shared_name}"
                        # مسیرهای manifest باید داخل پوشه‌های مبدأ و مقصد بمانند.
                        src_file.resolve().relative_to(shared_dir.resolve())
                        dst_file.resolve().relative_to(dst.resolve())
                        dst_file.parent.mkdir(parents=True, exist_ok=True)
                        from file_manager.transactional_update import PRESERVED_NAMES
                        if dst_file.exists() and (dst_file.name.lower() in PRESERVED_NAMES or dst_file.suffix.lower() in (".config", ".lic", ".license")):
                            continue
                        import shutil
                        shutil.copy2(src_file, dst_file)
                        shared_copied += 1

                if shared_copied > 0:
                    logger.log("WORKER", "SHARED_COPY", "SUCCESS",
                               f"تعداد {shared_copied} فایل مشترک از _shared/ به محصولات کپی شد.")
                    total_copied_files += shared_copied

            except Exception as ex:
                return False, f"آماده‌سازی فایل‌های مشترک ناموفق بود: {ex}"

        # فایل اتصال ممکن است در _shared باشد؛ تنظیم آن پس از تمام کپی‌ها انجام می‌شود.
        effective_target = self.server_target
        if not effective_target and self.install_mode == "server":
            inst = self.sql_instance_name or get_sql_instance_name(self.sql_version)
            if inst.upper() == "MSSQLSERVER":
                effective_target = "."
            else:
                effective_target = f".\\{inst}"

        if effective_target:
            from utils.connect_config import update_all_connect_files_in_folder
            for pid in self.selected_product_ids:
                cfg = get_product_by_id(pid)
                dst = self.root_path / (cfg.folder_name if cfg else pid)
                update_all_connect_files_in_folder(dst, effective_target)

        return True, f"تعداد {total_copied_files} فایل نرم‌افزار به پوشه نصب کپی شد."

    def _step_apply_update(self, overall_base: int, total_stages: int) -> Tuple[bool, str]:
        if not self.update_archive_path or not self.update_archive_path.is_file():
            return False, "بسته آپدیت انتخاب‌شده دیگر در دسترس نیست."

        if not self.root_path:
            return False, "مسیر ریشه نصب یافت نشد."

        from file_manager.update_manager import UpdateManager

        def on_update_prog(msg: str, pct: int):
            p = max(0, min(pct, 100)) if pct >= 0 else 50
            sub_contrib = int(p / total_stages)
            self.sig_progress.emit(overall_base + sub_contrib, p, f"آپدیت: {msg}")

        manager = UpdateManager(
            root_dir=self.root_path,
            selected_product_ids=self.selected_product_ids,
            install_mode=self.install_mode,
            sql_version=self.sql_version,
            sql_instance=self.sql_instance_name,
            server_target=self.server_target,
            progress_callback=on_update_prog,
        )

        res = manager.execute_update_pipeline(self.update_archive_path, lock_held=self._lock_held)
        if not res.success:
            return False, f"خطا در اعمال پکیج آپدیت: {res.message}"
        return True, res.message

    def _step_shortcuts(self) -> Tuple[bool, str]:
        if not self.root_path:
            return False, "مسیر ریشه نصب مشخص نیست."

        total_shortcuts = 0
        for pid in self.selected_product_ids:
            p_info = get_product_by_id(pid)
            exe_path = resolve_installed_exe_path(self.root_path, pid)
            if p_info and exe_path and exe_path.exists():
                created = create_shortcuts_for_product(
                    p_info.title,
                    p_info.shortcut_name,
                    exe_path,
                )
                total_shortcuts += len(created)

        return True, f"تعداد {total_shortcuts} میانبر فارسی ایجاد گردید."

    def _step_verify(self) -> Tuple[bool, str, VerificationSummary]:
        if not self.root_path:
            return False, "مسیر ریشه نصب مشخص نیست.", VerificationSummary(False, [], 1)
            
        verifier = FinalVerifier(
            self.root_path,
            self.selected_product_ids,
            install_mode=self.install_mode,
            sql_version=self.sql_version,
            instance_name=self.sql_instance_name,
        )
        summary = verifier.verify_all()
        if summary.all_passed:
            return True, "تمامی مؤلفه‌ها با موفقیت اعتبارسنجی شدند.", summary
        else:
            if self.skipped_stage_ids:
                return True, f"اعتبارسنجی تکمیل شد (با در نظر گرفتن موارد صرف‌نظر شده: {', '.join(self.skipped_stage_ids)}).", summary
            return False, f"تعداد {summary.failed_critical_count} مورد بحرانی در اعتبارسنجی رد شدند.", summary
