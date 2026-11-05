"""Versioned, checksummed update packages. Reading a package never changes an installation."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat
import zipfile

from config.settings import PRODUCTS_CONFIG
from utils.durable_state import contained_path, relative_path, sha256_file

MANIFEST_NAME = "update-manifest.json"
SCHEMA_VERSION = 1
SYSTEM_DATABASES = {"master", "model", "msdb", "tempdb"}


def version_tuple(value: str) -> tuple:
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d+){0,3}", value):
        raise ValueError("نسخه باید یک تا چهار بخش عددی مانند 2026.2.0 داشته باشد.")
    parts = tuple(int(item) for item in value.split("."))
    return parts + (0,) * (4 - len(parts))


def validate_database_name(name: str) -> str:
    if (not isinstance(name, str) or not name.strip() or len(name) > 128
            or any(ord(c) < 32 for c in name) or name.casefold() in SYSTEM_DATABASES):
        raise ValueError("نام پایگاه داده هدف معتبر نیست؛ دیتابیس‌های سیستمی مجاز نیستند.")
    return name


@dataclass(frozen=True)
class PackageFile:
    path: str
    kind: str
    size: int
    sha256: str
    target: str
    products: tuple


class UpdatePackage:
    def __init__(self, source: Path):
        self.source = Path(source)
        self.manifest = {}
        self.files = []
        self.digest = ""
        self._zip = None

    def __enter__(self):
        try:
            self._read()
            return self
        except Exception:
            self.close()
            raise

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self._zip:
            self._zip.close()
            self._zip = None

    def _read(self):
        if not self.source.is_file():
            raise ValueError("فایل بسته به‌روزرسانی یافت نشد.")
        members = {}
        if self.source.suffix.lower() == ".sql":
            sidecar = self.source.with_name(self.source.name + ".manifest.json")
            if not sidecar.is_file():
                raise ValueError("پچ SQL شناسنامه ندارد؛ با ابزار ساخت بسته، محصول و دیتابیس هدف را مشخص کنید.")
            raw_manifest = sidecar.read_bytes()
            members[self.source.name] = self.source.stat().st_size
        elif zipfile.is_zipfile(self.source):
            self._zip = zipfile.ZipFile(self.source)
            seen = set()
            for member in self._zip.infolist():
                name = relative_path(member.filename.rstrip("/"))
                if member.filename != name and not member.is_dir():
                    raise ValueError("نام فایل‌های ZIP باید با جداکننده / نوشته شود.")
                if name.casefold() in seen:
                    raise ValueError(f"مسیر تکراری در بسته: {name}")
                seen.add(name.casefold())
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("پیوند نمادین در بسته مجاز نیست.")
                if not member.is_dir():
                    members[name] = member.file_size
            if MANIFEST_NAME not in members:
                raise ValueError("بسته شناسنامه ندارد؛ ابتدا با build_update_package.py آن را آماده کنید.")
            if members[MANIFEST_NAME] > 4 * 1024 * 1024:
                raise ValueError("شناسنامه بسته بیش از حد بزرگ است.")
            raw_manifest = self._zip.read(MANIFEST_NAME)
            del members[MANIFEST_NAME]
        else:
            raise ValueError("بسته باید ZIP دارای شناسنامه باشد. محتوای RAR/7Z را با ابزار ساخت بسته به ZIP تبدیل کنید.")
        self.manifest = json.loads(raw_manifest.decode("utf-8-sig"))
        self._validate_manifest(members)
        for entry in self.files:
            digest = hashlib.sha256()
            with self.open_file(entry.path) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != entry.sha256:
                raise ValueError(f"سلامت فایل تأیید نشد: {entry.path}")
        self.digest = hashlib.sha256((sha256_file(self.source) + hashlib.sha256(raw_manifest).hexdigest()).encode()).hexdigest()

    def _validate_manifest(self, members):
        data = self.manifest
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("نسخه شناسنامه پشتیبانی نمی‌شود.")
        version_tuple(data.get("version"))
        version_tuple(data.get("minimum_version", "0"))
        products = data.get("products")
        if not isinstance(products, list) or not products or any(p not in PRODUCTS_CONFIG for p in products):
            raise ValueError("محصولات بسته نامعتبر یا خالی هستند.")
        if len(set(products)) != len(products):
            raise ValueError("محصول تکراری در شناسنامه.")
        if not isinstance(data.get("files"), list) or not data["files"]:
            raise ValueError("بسته فاقد فایل است.")
        if any(v not in ("2014", "2019") for v in data.get("sql_versions", [])):
            raise ValueError("نسخه SQL پشتیبانی‌نشده در شناسنامه.")
        if any(v not in ("crystal_reports", "stimulsoft") for v in data.get("prerequisites", [])):
            raise ValueError("پیش‌نیاز ناشناخته در شناسنامه.")
        seen, targets = set(), set()
        for entry in data["files"]:
            path = relative_path(entry["path"])
            kind = entry["kind"]
            if kind not in ("application", "data", "sql"):
                raise ValueError(f"نوع فایل نامعتبر است: {path}")
            size, digest = entry["size"], entry["sha256"]
            if type(size) is not int or size < 0 or size != members.get(path):
                raise ValueError(f"اندازه فایل نادرست است: {path}")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"SHA-256 نامعتبر است: {path}")
            selected = entry.get("products", products)
            if not isinstance(selected, list) or not selected or not set(selected).issubset(products):
                raise ValueError(f"محصول فایل نامعتبر است: {path}")
            target = relative_path(entry.get("target", path.split("/", 1)[-1]))
            if kind == "application" and Path(target).suffix.lower() in (".mdf", ".ldf", ".sql"):
                raise ValueError("فایل دیتابیس نباید به عنوان فایل برنامه کپی شود.")
            if kind == "data" and Path(target).suffix.lower() not in (".mdf", ".ldf"):
                raise ValueError("بخش داده فقط فایل‌های MDF/LDF را می‌پذیرد.")
            for product in selected if kind == "application" else [kind]:
                key = (product, target.casefold())
                if key in targets:
                    raise ValueError(f"دو فایل مقصد یکسان دارند: {target}")
                targets.add(key)
            if path in seen:
                raise ValueError(f"فایل تکراری در شناسنامه: {path}")
            seen.add(path)
            self.files.append(PackageFile(path, kind, size, digest, target, tuple(selected)))
        if seen != set(members):
            raise ValueError("فایل‌های ZIP با فهرست شناسنامه مطابقت ندارند.")
        declared = {entry.path: entry for entry in self.files}
        db_seen, referenced = set(), set()
        for db in data.get("databases", []):
            name = validate_database_name(db["name"])
            if name.casefold() in db_seen:
                raise ValueError("دیتابیس تکراری در شناسنامه.")
            db_seen.add(name.casefold())
            for key in ("mdf", "ldf"):
                if db.get(key):
                    entry = declared.get(db[key])
                    if not entry or entry.kind != "data" or Path(entry.target).suffix.lower() != "." + key:
                        raise ValueError(f"فایل {key} دیتابیس در شناسنامه نامعتبر است.")
                    referenced.add(entry.path)
            for path in db.get("scripts", []):
                if path not in declared or declared[path].kind != "sql":
                    raise ValueError("پچ SQL دیتابیس در شناسنامه نامعتبر است.")
                referenced.add(path)
        if {entry.path for entry in self.files if entry.kind != "application"} != referenced:
            raise ValueError("دیتابیس هدف تمام فایل‌های داده و SQL باید مشخص باشد.")

    def validate_target(self, products, sql_version=None, allow_database=True):
        if not products or not set(products).issubset(self.manifest["products"]):
            raise ValueError("این بسته برای محصولات انتخاب‌شده ساخته نشده است.")
        if self.manifest.get("databases") and not allow_database:
            raise ValueError("بسته دارای تغییر دیتابیس است و باید در حالت سرور اجرا شود.")
        versions = self.manifest.get("sql_versions", [])
        if versions and sql_version and sql_version not in versions:
            raise ValueError("نسخه SQL انتخاب‌شده با بسته به‌روزرسانی سازگار نیست.")

    def open_file(self, path):
        return self._zip.open(path) if self._zip else self.source.open("rb")

    def extract_to(self, destination: Path):
        destination.mkdir(parents=True, exist_ok=True)
        for entry in self.files:
            target = contained_path(destination, entry.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with self.open_file(entry.path) as source, target.open("xb") as output:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(block)
            if sha256_file(target) != entry.sha256:
                raise ValueError(f"فایل استخراج‌شده سالم نیست: {entry.path}")
