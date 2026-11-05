"""Create a checksummed update ZIP from an extracted Files/Data/Scripts directory."""

import argparse
import json
from pathlib import Path
import zipfile

from config.settings import PRODUCTS_CONFIG
from file_manager.update_package import MANIFEST_NAME, UpdatePackage, validate_database_name, version_tuple
from utils.durable_state import relative_path, sha256_file


def build_package(source, output, products, version, databases=None, minimum_version="0", sql_versions=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    version_tuple(version)
    version_tuple(minimum_version)
    if not source.is_dir() or not products or any(p not in PRODUCTS_CONFIG for p in products):
        raise ValueError("Source directory and known product IDs are required")
    if output.is_relative_to(source) or output.exists():
        raise ValueError("Output must be a new ZIP outside the source directory")
    databases = [validate_database_name(name) for name in (databases or [])]
    files, db_entries = [], [{"name": name, "scripts": []} for name in databases]
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symbolic links are not supported")
        if not path.is_file():
            continue
        relative = relative_path(path.relative_to(source).as_posix())
        if relative == MANIFEST_NAME:
            continue
        suffix = path.suffix.lower()
        kind = "sql" if suffix == ".sql" else "data" if suffix in (".mdf", ".ldf") else "application"
        target = relative.split("/", 1)[-1] if relative.split("/")[0].lower() in ("files", "data", "scripts") else relative
        entry = {"path": relative, "kind": kind, "target": target, "size": path.stat().st_size, "sha256": sha256_file(path)}
        files.append(entry)
        if kind == "sql":
            if len(db_entries) != 1:
                raise ValueError("SQL scripts require exactly one --database; use a hand-authored manifest for multiple databases")
            db_entries[0]["scripts"].append(relative)
        elif kind == "data":
            candidates = [db for db in db_entries if path.stem.casefold() in (db["name"].casefold(), db["name"].casefold() + "_log")]
            if len(candidates) != 1:
                raise ValueError(f"Cannot map database file {relative}; specify its --database name")
            key = suffix[1:]
            if key in candidates[0]:
                raise ValueError("Multiple MDF/LDF files require a hand-authored package manifest")
            candidates[0][key] = relative
    manifest = {"schema_version": 1, "products": products, "version": version,
                "minimum_version": minimum_version, "sql_versions": sql_versions or [],
                "prerequisites": [], "files": files, "databases": db_entries}
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
            for entry in files:
                archive.write(source / entry["path"], entry["path"])
        with UpdatePackage(output):
            pass
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--product", choices=PRODUCTS_CONFIG, action="append", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--minimum-version", default="0")
    parser.add_argument("--database", action="append", default=[])
    parser.add_argument("--sql-version", choices=("2014", "2019"), action="append", default=[])
    args = parser.parse_args()
    print(build_package(args.source, args.output, args.product, args.version, args.database, args.minimum_version, args.sql_version))


if __name__ == "__main__":
    main()
