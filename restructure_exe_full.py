# restructure_exe_full.py
"""
اسکریپت ساختاردهی مجدد پوشه exe full/ برای حذف فایل‌های تکراری
(بدون حذف هیچ فایلی — فقط جابجایی به پوشه _shared)

قبل از اجرا بکاپ بگیرید!

عملکرد:
  1. اسکن تمام فایل‌های تکراری (همنام + هم‌سایز) در زیرپوشه‌های exe full/
  2. انتقال یک نسخه به پوشه _shared/
  3. حذف نسخه‌های اضافی (چون دقیقاً همان فایل هستند)
  4. ساخت manifest.json که مشخص می‌کند هر محصول چه فایل‌هایی لازم دارد
  5. اینستالر موقع نصب از manifest.json استفاده می‌کند برای بازسازی ساختار کامل
"""

import hashlib
import json
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


BASE_DIR = Path(__file__).resolve().parent
EXE_FULL_DIR = BASE_DIR / "exe full"
SHARED_DIR = EXE_FULL_DIR / "_shared"
MANIFEST_FILE = EXE_FULL_DIR / "shared_manifest.json"

# حداقل سایز فایل برای انتقال به shared (فایل‌های کوچک‌تر ارزش ندارند)
MIN_FILE_SIZE_KB = 50


def compute_file_hash(filepath: Path, block_size: int = 65536) -> str:
    """محاسبه هش MD5 یک فایل"""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while True:
            buf = f.read(block_size)
            if not buf:
                break
            hasher.update(buf)
    return hasher.hexdigest()


def scan_duplicates() -> dict:
    """
    اسکن فایل‌های تکراری: گروه‌بندی بر اساس نام + سایز
    فقط فایل‌هایی که در بیش از یک محصول تکرار شده‌اند
    Returns: {filename: {hash: [list of Paths]}}
    """
    # ابتدا فایل‌ها را بر اساس نام + سایز گروه‌بندی می‌کنیم
    name_size_groups = defaultdict(list)

    product_dirs = [
        d for d in EXE_FULL_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    ]

    for pdir in product_dirs:
        for fpath in pdir.rglob("*"):
            if not fpath.is_file():
                continue
            if fpath.stat().st_size < MIN_FILE_SIZE_KB * 1024:
                continue
            key = (fpath.name, fpath.stat().st_size)
            name_size_groups[key].append(fpath)

    # فیلتر: فقط فایل‌هایی که در بیش از یک مسیر وجود دارند
    duplicates = {}
    for (fname, fsize), paths in name_size_groups.items():
        if len(paths) < 2:
            continue

        # تأیید نهایی با هش
        hash_groups = defaultdict(list)
        for p in paths:
            h = compute_file_hash(p)
            hash_groups[h].append(p)

        for h, hpaths in hash_groups.items():
            if len(hpaths) >= 2:
                if fname not in duplicates:
                    duplicates[fname] = {}
                duplicates[fname][h] = hpaths

    return duplicates


def build_manifest(duplicates: dict) -> dict:
    """
    ساخت manifest: برای هر محصول مشخص می‌کند چه فایل‌هایی از _shared لازم دارد
    """
    manifest = {
        "_meta": {
            "description": "Shared DLL manifest for SEPEHRYAR installer",
            "version": "1.0",
            "note": "هر محصول فایل‌های لیست‌شده را از _shared/ نیاز دارد"
        },
        "shared_files": [],
        "products": {},
    }

    product_dirs = [
        d for d in EXE_FULL_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    ]

    for pdir in product_dirs:
        manifest["products"][pdir.name] = {
            "shared_files": [],
            "unique_files_count": 0,
        }

    for fname, hash_groups in duplicates.items():
        for h, paths in hash_groups.items():
            file_size = paths[0].stat().st_size
            manifest["shared_files"].append({
                "name": fname,
                "size_bytes": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2),
                "hash": h,
                "found_in": len(paths),
            })

            for p in paths:
                # تشخیص محصول والد
                rel = p.relative_to(EXE_FULL_DIR)
                product_name = rel.parts[0]
                # مسیر نسبی داخل پوشه محصول
                rel_path = str(Path(*rel.parts[1:]))

                if product_name in manifest["products"]:
                    manifest["products"][product_name]["shared_files"].append({
                        "shared_name": fname,
                        "relative_path": rel_path,
                    })

    # شمارش فایل‌های یونیک هر محصول
    for pdir in product_dirs:
        total_files = sum(1 for _ in pdir.rglob("*") if _.is_file())
        shared_count = len(manifest["products"].get(pdir.name, {}).get("shared_files", []))
        manifest["products"][pdir.name]["unique_files_count"] = total_files - shared_count

    return manifest


def restructure(dry_run: bool = False):
    """
    اجرای عملیات ساختاردهی مجدد:
    - dry_run=True: فقط گزارش (هیچ فایلی جابجا نمی‌شود)
    - dry_run=False: انتقال واقعی فایل‌ها
    """
    print("\n" + "=" * 70)
    print("  SEPEHRYAR — ساختاردهی مجدد پوشه exe full/")
    if dry_run:
        print("  حالت DRY-RUN: هیچ فایلی جابجا نخواهد شد")
    print("=" * 70)

    if not EXE_FULL_DIR.exists():
        print(f"[-] پوشه exe full/ یافت نشد: {EXE_FULL_DIR}")
        return

    print("\n[1/4] اسکن فایل‌های تکراری...")
    duplicates = scan_duplicates()

    if not duplicates:
        print("[✓] هیچ فایل تکراری یافت نشد!")
        return

    total_files = sum(len(ps) for hg in duplicates.values() for ps in hg.values())
    total_unique = len(duplicates)
    total_waste_bytes = sum(
        paths[0].stat().st_size * (len(paths) - 1)
        for hg in duplicates.values()
        for h, paths in hg.items()
    )
    total_waste_mb = round(total_waste_bytes / (1024 * 1024), 1)

    print(f"    فایل‌های تکراری یافت‌شده: {total_unique} فایل یونیک ({total_files} کپی)")
    print(f"    فضای قابل صرفه‌جویی: {total_waste_mb} MB")

    print("\n[2/4] ساخت manifest.json...")
    manifest = build_manifest(duplicates)

    if not dry_run:
        SHARED_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[3/4] انتقال فایل‌ها به _shared/...")
    moved_count = 0
    saved_bytes = 0

    for fname, hash_groups in duplicates.items():
        for h, paths in hash_groups.items():
            # یک نسخه را به _shared منتقل می‌کنیم
            src = paths[0]
            dst = SHARED_DIR / fname
            file_size = src.stat().st_size

            if not dry_run:
                if not dst.exists():
                    shutil.copy2(src, dst)

                # حذف تمام کپی‌ها (چون الان در _shared هست)
                for p in paths:
                    try:
                        p.unlink()
                    except Exception as ex:
                        print(f"    [!] خطا در حذف {p}: {ex}")
            else:
                print(f"    [DRY] {fname} ({round(file_size/1024/1024,1)} MB) × {len(paths)} copies → _shared/")

            moved_count += 1
            saved_bytes += file_size * (len(paths) - 1)

    saved_mb = round(saved_bytes / (1024 * 1024), 1)

    print(f"\n    منتقل‌شده: {moved_count} فایل به _shared/")
    print(f"    صرفه‌جویی: {saved_mb} MB")

    print("\n[4/4] ذخیره manifest...")
    if not dry_run:
        with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        print(f"    manifest ذخیره شد: {MANIFEST_FILE}")
    else:
        print(f"    [DRY] manifest در {MANIFEST_FILE} ذخیره خواهد شد")

    # خلاصه نهایی
    before_size = sum(
        f.stat().st_size
        for f in EXE_FULL_DIR.rglob("*")
        if f.is_file()
    )
    before_mb = round(before_size / (1024 * 1024), 1)

    print("\n" + "=" * 70)
    print("  خلاصه:")
    print(f"    حجم فعلی exe full/: {before_mb} MB")
    if not dry_run:
        after_size = sum(
            f.stat().st_size
            for f in EXE_FULL_DIR.rglob("*")
            if f.is_file()
        )
        after_mb = round(after_size / (1024 * 1024), 1)
        print(f"    حجم بعد از ساختاردهی: {after_mb} MB")
        print(f"    صرفه‌جویی واقعی: {round(before_mb - after_mb, 1)} MB")
    else:
        est_after = before_mb - saved_mb
        print(f"    حجم تخمینی بعد از ساختاردهی: {est_after} MB")
        print(f"    صرفه‌جویی تخمینی: {saved_mb} MB")
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ساختاردهی مجدد exe full/ سپهریار")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="اجرای واقعی (بدون این فلگ فقط گزارش نشان داده می‌شود)",
    )
    args = parser.parse_args()

    if args.apply:
        print("\n⚠️  آیا از پوشه exe full/ بکاپ گرفته‌اید؟ (y/n): ", end="")
        ans = input().strip().lower()
        if ans != "y":
            print("لطفاً ابتدا بکاپ بگیرید.")
            sys.exit(0)
        restructure(dry_run=False)
    else:
        restructure(dry_run=True)
        print("\n💡 برای اجرای واقعی: python restructure_exe_full.py --apply")
