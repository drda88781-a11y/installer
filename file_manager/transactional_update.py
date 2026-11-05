"""One update transaction for both the installer and standalone updater.

Backups must pass verification before mutation. Every mutation is journalled first;
an interrupted transaction is rolled back before another update may start.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import uuid

from config.settings import PRODUCTS_CONFIG
from file_manager.update_package import UpdatePackage, version_tuple
from utils.durable_state import atomic_json, contained_path, installation_lock, sha256_file

VERSION_FILE = ".sepehryar-version.json"
PRESERVED_NAMES = {"conect.xml", "connect.xml", "setting.stg", "pos.stg"}
STAGES = [
    ("validate_update", "بررسی شناسنامه و سلامت بسته"),
    ("check_version", "بررسی محصول و نسخه نصب‌شده"),
    ("backup_app", "پشتیبان‌گیری و بررسی فایل‌های برنامه"),
    ("backup_db", "پشتیبان‌گیری و تأیید پایگاه داده"),
    ("extract_files", "آماده‌سازی فایل‌های تأییدشده"),
    ("replace_files", "اعمال فایل‌ها با حفظ تنظیمات"),
    ("transfer_data", "آماده‌سازی داده‌های جدید"),
    ("db_operation", "اعمال تغییرات دیتابیس"),
    ("test_connection", "بررسی سلامت دیتابیس"),
    ("final_verify", "بررسی نهایی فایل‌ها"),
    ("complete", "ثبت نسخه و تکمیل به‌روزرسانی"),
]


@dataclass
class TransactionResult:
    success: bool = False
    message: str = ""
    new_version: str = ""
    previous_version: str = ""
    files_updated_count: int = 0
    data_files_transferred: list = field(default_factory=list)
    attached_databases: list = field(default_factory=list)
    executed_sql_scripts: list = field(default_factory=list)
    backup_dir: Path | None = None
    log_file_path: Path | None = None
    rollback_executed: bool = False
    rollback_success: bool = False
    failed_stage_id: str | None = None


def close_product_processes(target_dirs):
    import psutil
    processes = []
    roots = [path.resolve() for path in target_dirs]
    for process in psutil.process_iter(["pid", "exe"]):
        try:
            exe = process.info["exe"]
            if exe and any(Path(exe).resolve().is_relative_to(root) for root in roots):
                if process.pid == os.getpid():
                    raise RuntimeError("آپدیتر باید خارج از پوشه برنامه هدف اجرا شود.")
                process.terminate()
                processes.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _, alive = psutil.wait_procs(processes, timeout=8)
    if alive:
        raise RuntimeError("برنامه هنوز باز است؛ آن را ببندید و دوباره تلاش کنید.")


def installed_version(directory, product):
    marker = directory / VERSION_FILE
    if marker.is_file():
        value = json.loads(marker.read_text(encoding="utf-8"))["version"]
        version_tuple(value)
        return value
    from file_manager.update_engine import get_pe_file_version
    exe = directory / PRODUCTS_CONFIG[product]["main_exe"]
    return get_pe_file_version(exe) if exe.exists() else "0.0.0.0"


class TransactionalUpdate:
    def __init__(self, root_dir, targets, sql_instance=None, sql_version=None,
                 data_dir=None, allow_database=True, allow_equal_version=False,
                 progress_callback=None, stage_callback=None, db_backend=None,
                 process_closer=None, version_reader=None):
        self.root = Path(root_dir).resolve()
        self.targets = {product: Path(path).resolve() for product, path in targets.items()}
        for product, target in self.targets.items():
            if product not in PRODUCTS_CONFIG or target == self.root:
                raise ValueError("مسیر یا محصول هدف معتبر نیست.")
            target.relative_to(self.root)
        self.data_dir = Path(data_dir or self.root / "SEPEHRYAR.Data").resolve()
        self.data_dir.relative_to(self.root)
        self.backup_root = self.root / "SEPEHRYAR.Backup" / "transactions"
        self.sql_instance, self.sql_version = sql_instance, sql_version
        self.allow_database, self.allow_equal_version = allow_database, allow_equal_version
        self.progress_callback, self.stage_callback = progress_callback, stage_callback
        self.db = db_backend
        self._injected_db = db_backend is not None
        self.process_closer = process_closer or close_product_processes
        self.version_reader = version_reader or installed_version
        self.state, self.journal = None, None
        self.current_stage = "validate_update"

    def _database(self, instance=None):
        if self.db is None:
            from sql.update_database import UpdateDatabase
            self.db = UpdateDatabase(instance or self.sql_instance)
        return self.db

    def _stage(self, stage, message):
        self.current_stage = stage
        index = next(i for i, item in enumerate(STAGES) if item[0] == stage)
        if self.progress_callback:
            self.progress_callback(stage, int(index * 100 / len(STAGES)), message)
        if self.stage_callback:
            self.stage_callback(index, message)

    def _save(self):
        atomic_json(self.journal, self.state)

    def _relative(self, path):
        return path.resolve().relative_to(self.root).as_posix()

    def _copy_verified(self, source, destination, digest):
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(".update-" + uuid.uuid4().hex)
        try:
            with source.open("rb") as reader, temporary.open("xb") as writer:
                shutil.copyfileobj(reader, writer, 1024 * 1024)
                writer.flush()
                os.fsync(writer.fileno())
            if sha256_file(temporary) != digest:
                raise RuntimeError(f"فایل کپی‌شده با مبدأ مطابقت ندارد: {source.name}")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _snapshot_files(self):
        snapshots = []
        for target in self.targets.values():
            if not target.is_dir():
                continue
            for source in sorted(target.rglob("*")):
                if source.is_symlink() or getattr(source, "is_junction", lambda: False)():
                    raise ValueError("پشتیبان‌گیری از مسیر دارای پیوند یا Junction مجاز نیست.")
                if source.is_file():
                    relative = self._relative(source)
                    digest = sha256_file(source)
                    backup = contained_path(self.journal.parent / "files", relative)
                    self._copy_verified(source, backup, digest)
                    snapshots.append({"path": relative, "sha256": digest})
        self.state["files"] = snapshots
        self._save()

    def _plan(self, package):
        entries = []
        for entry in package.files:
            if entry.kind != "application":
                continue
            for product, directory in self.targets.items():
                if product not in entry.products:
                    continue
                target = contained_path(directory, entry.target)
                if target.exists() and (target.name.lower() in PRESERVED_NAMES or target.suffix.lower() in (".config", ".lic", ".license")):
                    continue
                entries.append((entry, target))
        return entries

    def _mark_new_file(self, target):
        relative = self._relative(target)
        backed_up = {item["path"] for item in self.state["files"]}
        if relative not in backed_up and relative not in self.state["new_files"]:
            if target.exists():
                raise RuntimeError(f"فایل جدید خارج از بک‌آپ ظاهر شده است: {target}")
            self.state["new_files"].append(relative)
            self._save()

    def recover_pending(self):
        for journal in sorted(self.backup_root.glob("*/transaction.json")):
            state = json.loads(journal.read_text(encoding="utf-8"))
            if state.get("status") in ("committed", "rolled_back", "aborted"):
                continue
            if state.get("schema_version") != 1 or state.get("root") != str(self.root):
                raise RuntimeError("دفتر ثبت بازیابی معتبر نیست؛ ادامه عملیات متوقف شد.")
            if state.get("status") == "preparing":
                state["status"] = "aborted"
                atomic_json(journal, state)
                continue
            self.process_closer([contained_path(self.root, path) for path in state["targets"]])
            self._rollback(journal, state)
            if not self._injected_db and state["sql_instance"] != self.sql_instance:
                self.db = None

    def _rollback(self, journal, state):
        if not state.get("backups_verified"):
            raise RuntimeError("بک‌آپ تأییدشده برای بازیابی موجود نیست.")
        # Verify all backups before restoring any data.
        for item in state["files"]:
            source = contained_path(journal.parent / "files", item["path"])
            contained_path(self.root, item["path"])
            if not source.is_file() or sha256_file(source) != item["sha256"]:
                raise RuntimeError(f"بک‌آپ فایل سالم نیست: {item['path']}")
        for db in state["databases"]:
            if db.get("backup"):
                source = contained_path(journal.parent, db["backup"])
                if not source.is_file() or sha256_file(source) != db["sha256"]:
                    raise RuntimeError(f"بک‌آپ دیتابیس سالم نیست: {db['name']}")
        state["status"] = "rolling_back"
        atomic_json(journal, state)
        backend = self._database(state["sql_instance"]) if state["changed_databases"] else None
        for db in reversed(state["databases"]):
            if db["name"] not in state["changed_databases"]:
                continue
            if db["existed"]:
                backend.restore(db["name"], contained_path(journal.parent, db["backup"]))
            else:
                backend.drop_created(db["name"])
        for relative in state["new_files"]:
            contained_path(self.root, relative).unlink(missing_ok=True)
        for item in state["files"]:
            self._copy_verified(contained_path(journal.parent / "files", item["path"]),
                                contained_path(self.root, item["path"]), item["sha256"])
        state["status"] = "rolled_back"
        atomic_json(journal, state)

    def execute(self, source, lock_held=False):
        if lock_held:
            return self._execute_locked(Path(source))
        with installation_lock(self.root):
            return self._execute_locked(Path(source))

    def protect_file_deployment(self, destinations, operation):
        """Verified backup barrier for base application copying; caller owns the lock."""
        self.recover_pending()
        self.process_closer(list(self.targets.values()))
        self.journal = self.backup_root / ("install_" + uuid.uuid4().hex) / "transaction.json"
        self.state = {"schema_version": 1, "root": str(self.root), "status": "preparing",
                      "targets": [self._relative(path) for path in self.targets.values()],
                      "sql_instance": None, "files": [], "new_files": [], "databases": [],
                      "changed_databases": [], "backups_verified": False}
        try:
            self._save()
            self._snapshot_files()
            self.state["backups_verified"] = True
            # Persist every potential new file before allowing the copier to run.
            for destination in destinations:
                self._mark_new_file(destination)
            self.state["status"] = "applying"
            self._save()
            success, message = operation()
            if not success:
                raise RuntimeError(message)
            self.state["status"] = "committed"
            self._save()
            return True, message
        except Exception as exc:
            if self.state["status"] == "applying":
                try:
                    self._rollback(self.journal, self.state)
                    return False, f"{exc} فایل‌های قبلی بازیابی شدند."
                except Exception as restore_error:
                    return False, f"{exc} بازیابی کامل نشد: {restore_error}"
            self.state["status"] = "aborted"
            self._save()
            return False, str(exc)

    def _execute_locked(self, source):
        result = TransactionResult()
        try:
            self.recover_pending()
            self._stage("validate_update", "بررسی محصول، شناسنامه و SHA-256 فایل‌ها...")
            with UpdatePackage(source) as package:
                package.validate_target(self.targets, self.sql_version, self.allow_database)
                result.new_version = package.manifest["version"]
                self._stage("check_version", "بررسی نسخه‌های فعلی و پیش‌نیازها...")
                versions, already_applied = [], []
                for product, directory in self.targets.items():
                    if not directory.is_dir():
                        raise ValueError(f"پوشه محصول نصب‌شده یافت نشد: {directory}")
                    old = self.version_reader(directory, product)
                    versions.append(old)
                    marker = directory / VERSION_FILE
                    already_applied.append(marker.is_file() and json.loads(marker.read_text(encoding="utf-8")).get("package_sha256") == package.digest)
                    if version_tuple(old) < version_tuple(package.manifest.get("minimum_version", "0")):
                        raise ValueError("نسخه نصب‌شده از حداقل موردنیاز بسته قدیمی‌تر است.")
                    if version_tuple(old) > version_tuple(result.new_version):
                        raise ValueError("بسته از نسخه نصب‌شده قدیمی‌تر است.")
                    if version_tuple(old) == version_tuple(result.new_version) and not self.allow_equal_version and not already_applied[-1]:
                        raise ValueError("نسخه بسته با نسخه نصب‌شده یکسان است.")
                result.previous_version = ", ".join(versions)
                if all(already_applied):
                    result.success, result.message = True, "این بسته قبلاً با موفقیت اعمال شده است."
                    return result
                if package.manifest.get("prerequisites"):
                    from prerequisites.prereq_installer import PrerequisiteManager
                    manager = PrerequisiteManager()
                    for requirement in package.manifest["prerequisites"]:
                        if not getattr(manager, f"is_{requirement}_installed")():
                            raise ValueError(f"پیش‌نیاز {requirement} نصب نیست.")
                databases = package.manifest.get("databases", [])
                if databases and package.manifest.get("sql_versions"):
                    if self._database().version() not in package.manifest["sql_versions"]:
                        raise ValueError("نسخه واقعی SQL با شناسنامه بسته مطابقت ندارد.")
                self.process_closer(list(self.targets.values()))
                required = sum(p.stat().st_size for target in self.targets.values() for p in target.rglob("*") if p.is_file())
                required += 2 * sum(entry.size for entry in package.files)
                if shutil.disk_usage(self.root).free < required:
                    raise RuntimeError("فضای کافی برای پشتیبان‌گیری و استخراج بسته موجود نیست.")
                transaction_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex
                self.journal = self.backup_root / transaction_id / "transaction.json"
                result.backup_dir = self.journal.parent
                result.log_file_path = self.journal
                self.state = {"schema_version": 1, "root": str(self.root), "status": "preparing",
                              "package_sha256": package.digest, "version": result.new_version,
                              "targets": [self._relative(path) for path in self.targets.values()],
                              "sql_instance": self.sql_instance, "files": [], "new_files": [],
                              "databases": [], "changed_databases": [], "backups_verified": False}
                self._save()
                self._stage("backup_app", "تهیه و تأیید نسخه پشتیبان تمام فایل‌های برنامه...")
                self._snapshot_files()
                self._stage("backup_db", "تهیه و تأیید بک‌آپ دیتابیس‌های هدف...")
                for index, db in enumerate(databases):
                    exists = self._database().exists(db["name"])
                    record = {"name": db["name"], "existed": exists}
                    if exists:
                        backup = self.journal.parent / "databases" / f"{index}.bak"
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        self.db.backup(db["name"], backup)
                        record.update(backup=backup.relative_to(self.journal.parent).as_posix(), sha256=sha256_file(backup))
                    elif not db.get("mdf"):
                        raise ValueError(f"دیتابیس {db['name']} موجود نیست و فایل اولیه ندارد.")
                    self.state["databases"].append(record)
                    self._save()
                self._stage("extract_files", "استخراج و بررسی مجدد محتوای بسته...")
                extracted = self.journal.parent / "payload"
                package.extract_to(extracted)
                self.state.update(backups_verified=True, status="applying")
                self._save()
                self._stage("replace_files", "جایگزینی فایل‌های برنامه با حفظ تنظیمات...")
                planned = self._plan(package)
                for entry, target in planned:
                    self._mark_new_file(target)
                    self._copy_verified(contained_path(extracted, entry.path), target, entry.sha256)
                    result.files_updated_count += 1
                self._stage("transfer_data", "آماده‌سازی فایل‌های پایگاه داده جدید...")
                entries = {entry.path: entry for entry in package.files}
                for db, record in zip(databases, self.state["databases"]):
                    if record["existed"]:
                        continue  # Never replace an existing customer's database with a seed.
                    for key in ("mdf", "ldf"):
                        if db.get(key):
                            entry = entries[db[key]]
                            target = contained_path(self.data_dir, entry.target)
                            self._mark_new_file(target)
                            self._copy_verified(contained_path(extracted, entry.path), target, entry.sha256)
                            result.data_files_transferred.append(str(target))
                self._stage("db_operation", "اعمال تغییرات روی دیتابیس‌های اعلام‌شده...")
                for db, record in zip(databases, self.state["databases"]):
                    if not record["existed"] or db.get("scripts"):
                        self.state["changed_databases"].append(db["name"])
                        self._save()
                    if not record["existed"]:
                        mdf = contained_path(self.data_dir, entries[db["mdf"]].target)
                        ldf = contained_path(self.data_dir, entries[db["ldf"]].target) if db.get("ldf") else None
                        self.db.attach(db["name"], mdf, ldf)
                        result.attached_databases.append(db["name"])
                    for script in db.get("scripts", []):
                        self.db.execute_script(db["name"], contained_path(extracted, script))
                        result.executed_sql_scripts.append(script)
                self._stage("test_connection", "بررسی آماده‌بودن دیتابیس‌های هدف...")
                for db in databases:
                    self.db.verify(db["name"])
                self._stage("final_verify", "تأیید فایل‌های جایگزین‌شده...")
                for entry, target in planned:
                    if sha256_file(target) != entry.sha256:
                        raise RuntimeError(f"اعتبارسنجی فایل نصب‌شده ناموفق بود: {target.name}")
                for product, directory in self.targets.items():
                    marker = directory / VERSION_FILE
                    self._mark_new_file(marker)
                    atomic_json(marker, {"product": product, "version": result.new_version, "package_sha256": package.digest})
                self.state["status"] = "committed"
                self._save()
                result.success, result.message = True, "به‌روزرسانی با بک‌آپ تأییدشده انجام شد."
                self._stage("complete", result.message)
                return result
        except Exception as exc:
            result.failed_stage_id = self.current_stage
            result.message = str(exc)
            if self.state and self.state.get("status") in ("applying", "rolling_back"):
                result.rollback_executed = True
                try:
                    self._rollback(self.journal, self.state)
                    result.rollback_success = True
                    result.message += " نسخه قبلی با موفقیت بازیابی شد."
                except Exception as rollback_error:
                    result.message += f" بازیابی کامل نشد؛ بک‌آپ حفظ شده است: {rollback_error}"
            elif self.state and self.state.get("status") == "preparing":
                self.state["status"] = "aborted"
                self._save()
            return result
