"""Read-only installation summary used immediately before starting a worker."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil

from config.settings import SETUP_DIR, EXE_FULL_DIR, PRODUCTS_CONFIG, get_sql_instance_name, requires_sql
from core.install_checkpoint import request_identity
from file_manager.update_package import UpdatePackage
from utils.durable_state import contained_path


@dataclass
class InstallPlan:
    root: Path
    products: list
    mode: str
    sql_description: str
    minimum_bytes: int = 0
    available_bytes: int = 0
    update_version: str = ""
    database_names: list = field(default_factory=list)
    resume_available: bool = False
    checkpoint_path: Path | None = None
    errors: list = field(default_factory=list)


def create_install_plan(drive, products, mode, sql_version, server_target="", update_path=None, sql_instance=""):
    root = Path(str(drive).rstrip("\\/") + "\\") / "SEPEHRYAR"
    needs_sql = requires_sql(products, mode)
    inst_name = sql_instance or get_sql_instance_name(sql_version)
    sql_description = f"{inst_name} (SQL {sql_version})" if needs_sql else server_target or "بدون SQL محلی"
    plan = InstallPlan(root, list(products), mode, sql_description)
    plan.checkpoint_path = root / "SEPEHRYAR.Setup" / "installation-state.json"
    if not products:
        plan.errors.append("هیچ محصولی انتخاب نشده است.")
    if root.drive.upper() == "C:":
        plan.errors.append("نصب در درایو C مجاز نیست.")
    try:
        for product in products:
            config = PRODUCTS_CONFIG[product]
            source = EXE_FULL_DIR / config["folder_name"]
            if not source.is_dir():
                raise ValueError(f"پوشه محصول {config['title']} موجود نیست.")
            plan.minimum_bytes += sum(path.stat().st_size for path in source.rglob("*") if path.is_file())
            target = root / config["folder_name"]
            if target.is_dir():
                plan.minimum_bytes += sum(path.stat().st_size for path in target.rglob("*") if path.is_file())
        manifest_file = EXE_FULL_DIR / "shared_manifest.json"
        if manifest_file.is_file():
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            for product in products:
                for entry in manifest["products"][product]["shared_files"]:
                    plan.minimum_bytes += contained_path(EXE_FULL_DIR / "_shared", entry["shared_name"]).stat().st_size
        if not SETUP_DIR.is_dir():
            raise ValueError("پوشه پیش‌نیازهای SETUP موجود نیست.")
        for path in SETUP_DIR.rglob("*"):
            relative = path.relative_to(SETUP_DIR)
            if not path.is_file():
                continue
            if not needs_sql and any("2019" in part.lower() or part.lower() in ("sql", "ssms") for part in relative.parts):
                continue
            if sql_version == "2014" and "2019" in str(relative):
                continue
            if sql_version == "2019" and relative.parts[0].lower() == "sql":
                continue
            plan.minimum_bytes += path.stat().st_size
        if update_path:
            with UpdatePackage(Path(update_path)) as package:
                matched = set(products) & set(package.manifest["products"])
                package.validate_target(matched, sql_version, needs_sql)
                plan.update_version = package.manifest["version"]
                plan.database_names = [db["name"] for db in package.manifest.get("databases", [])]
                plan.minimum_bytes += 2 * sum(entry.size for entry in package.files)
        plan.available_bytes = shutil.disk_usage(root.anchor).free
        if plan.minimum_bytes > plan.available_bytes:
            plan.errors.append("فضای محاسبه‌شده برای فایل‌ها، استخراج و بک‌آپ کافی نیست.")
        if plan.checkpoint_path.is_file():
            state = json.loads(plan.checkpoint_path.read_text(encoding="utf-8"))
            plan.resume_available = state.get("status") != "complete" and state.get("request") == request_identity(products, mode, sql_version, server_target, update_path)
    except Exception as exc:
        plan.errors.append(str(exc))
    return plan
