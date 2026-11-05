# build_standalone_launcher.py
"""
ساخت نسخه تک‌فایل و کاملاً مستقل نصاب سپهریار با رابط کاربری اختصاصی (Standalone Luxury Launcher)
این اسکریپت:
۱. پکیج فشرده payload.zip را از نرم‌افزار، گزارش‌ها و ابزارها آماده می‌کند.
۲. آن را درون لانچر اختصاصی مشکی-طلایی سپهریار (setup_launcher) تزریق (Embed) می‌کند.
۳. یک فایل اجرایی تک‌فایل Sepehryar_Setup.exe می‌سازد که به تنهایی روی هر سیستم خام کار می‌کند.
۴. فایل نهایی را مستقیماً روی دسکتاپ قرار می‌دهد.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
SCRATCH_DIR = BASE_DIR / "scratch"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build" / "standalone_launcher"

SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
DIST_DIR.mkdir(parents=True, exist_ok=True)
BUILD_DIR.mkdir(parents=True, exist_ok=True)

SQL_EXCLUDE_PATTERNS = [
    "Microsoft.SQL.Server.2019.Enterprise.x64.rar",
    "SQL",
    "SQL_Extracted",
]

CLEANUP_EXCLUDE_PATTERNS = [
    "*.pdb",
    "*.downloading",
    "app.publish",
]

PROTECTED_PDB_FILES = {"net.pdb", "cod.pdb"}


def should_exclude(item_name: str) -> bool:
    item_lower = item_name.lower()
    for p in SQL_EXCLUDE_PATTERNS:
        if p.lower() == item_lower or item_lower.startswith(p.lower()):
            return True
    return False


def prepare_staging_dir(staging_dir: Path):
    """آماده‌سازی فایل‌های تمیز درون پوشه استیجینگ"""
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    print("[1/4] در حال آماده‌سازی فایل‌های برنامه و پیش‌نیازها...")

    # کپی SEPEHRYAR_Installer.exe
    installer_exe = BASE_DIR / "SEPEHRYAR_Installer.exe"
    if not installer_exe.exists():
        raise FileNotFoundError("SEPEHRYAR_Installer.exe یافت نشد. ابتدا اینستالر را بیلد کنید.")
    shutil.copy2(installer_exe, staging_dir / installer_exe.name)
    print("    [✓] اینستالر اصلی اضافه شد.")

    # کپی SETUP بدون SQL Server
    setup_dir = BASE_DIR / "SETUP"
    if setup_dir.exists():
        dst_setup = staging_dir / "SETUP"
        dst_setup.mkdir(parents=True, exist_ok=True)
        for item in setup_dir.iterdir():
            if should_exclude(item.name):
                continue
            dst = dst_setup / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)
        print("    [✓] پیش‌نیازها و گزارش‌ها اضافه شدند (بدون پکیج سنگین SQL).")

    # کپی exe full
    exe_full_dir = BASE_DIR / "exe full"
    if exe_full_dir.exists():
        dst_exe = staging_dir / "exe full"
        shutil.copytree(exe_full_dir, dst_exe, dirs_exist_ok=True)
        for pattern in CLEANUP_EXCLUDE_PATTERNS:
            if pattern.startswith("*."):
                ext = pattern[1:]
                for f in dst_exe.rglob(f"*{ext}"):
                    if f.name.lower() in PROTECTED_PDB_FILES:
                        continue
                    try:
                        f.unlink()
                    except Exception:
                        pass
            else:
                for f in dst_exe.rglob(pattern):
                    try:
                        if f.is_dir():
                            shutil.rmtree(f, ignore_errors=True)
                        else:
                            f.unlink()
                    except Exception:
                        pass
        print("    [✓] فایل‌های اصلی نرم‌افزار حسابداری سپهریار اضافه شدند.")

    # کپی assets
    assets_dir = BASE_DIR / "assets"
    if assets_dir.exists():
        shutil.copytree(assets_dir, staging_dir / "assets", dirs_exist_ok=True)
        print("    [✓] منابع گرافیکی اضافه شدند.")


def create_payload_zip(staging_dir: Path, output_zip: Path):
    """ساخت payload.zip با WinRAR یا ZipFile پایتون"""
    print("\n[2/4] در حال فشرده‌سازی پکیج داخلی (payload.zip)...")
    if output_zip.exists():
        output_zip.unlink()

    winrar_exe = Path(r"C:\Program Files\WinRAR\WinRAR.exe")
    if winrar_exe.exists():
        cmd = [
            str(winrar_exe),
            "a",
            "-afzip",
            "-r",
            "-ep1",
            "-m3",       # فشرده‌سازی استاندارد و فوق‌سریع
            str(output_zip),
            "*",
        ]
        proc = subprocess.run(cmd, cwd=str(staging_dir))
        if proc.returncode != 0:
            raise RuntimeError(f"خطا در ایجاد payload.zip با WinRAR (کد {proc.returncode})")
    else:
        import zipfile
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=4) as zf:
            for f in staging_dir.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(staging_dir)
                    zf.write(f, str(rel))

    size_mb = output_zip.stat().st_size / (1024 * 1024)
    print(f"    [✓] پکیج payload.zip با موفقیت ساخته شد: {size_mb:.1f} MB")


def compile_standalone_launcher(payload_zip: Path, output_exe_name: str = "Sepehryar_Setup.exe"):
    """کامپایل لانچر به همراه payload.zip به صورت یک فایل مستقل"""
    print("\n[3/4] در حال کامپایل لانچر تک‌فایل با رابط کاربری اختصاصی مشکی-طلایی...")

    launcher_script = BASE_DIR / "setup_launcher.py"
    ico_path = BASE_DIR / "assets" / "icons" / "app_icon.ico"
    icon_args = [f"--icon={ico_path}"] if ico_path.exists() else []

    add_data_args = [
        f"--add-data={payload_zip};.",
        f"--add-data={BASE_DIR / 'assets'};assets",
    ]
    font_file = BASE_DIR / "AradVF.ttf"
    if font_file.exists():
        add_data_args.append(f"--add-data={font_file};.")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        f"--name={Path(output_exe_name).stem}",
        "--noconsole",
        "--uac-admin",
        "--onefile",
        "--clean",
        "--noconfirm",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        "--hidden-import=psutil",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
    ] + icon_args + add_data_args + [str(launcher_script)]

    ret = subprocess.run(cmd)
    if ret.returncode != 0:
        raise RuntimeError(f"خطا در کامپایل PyInstaller با کد: {ret.returncode}")

    final_exe = DIST_DIR / output_exe_name
    if not final_exe.exists():
        raise FileNotFoundError(f"فایل نهایی در {final_exe} یافت نشد.")

    final_size_mb = final_exe.stat().st_size / (1024 * 1024)
    print(f"    [✓] فایل اجرایی ساخته شد: {final_size_mb:.1f} MB")
    return final_exe


def copy_to_desktop(exe_path: Path):
    """کپی مستقیم فایل روی دسکتاپ کاربر"""
    print("\n[4/4] در حال کپی روی دسکتاپ...")
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        desktop_file = desktop / exe_path.name
        with open(exe_path, "rb") as fin:
            data = fin.read()
        with open(desktop_file, "wb") as fout:
            fout.write(data)
        print(f"    [✓] فایل نهایی با موفقیت روی دسکتاپ قرار گرفت: {desktop_file}")
        return desktop_file
    return None


def main():
    staging_dir = SCRATCH_DIR / "_standalone_staging"
    payload_zip = SCRATCH_DIR / "payload.zip"

    try:
        prepare_staging_dir(staging_dir)
        create_payload_zip(staging_dir, payload_zip)
        final_exe = compile_standalone_launcher(payload_zip, "Sepehryar_Setup.exe")
        copy_to_desktop(final_exe)

        print("\n" + "=" * 65)
        print("✓ پروژه با موفقیت به صورت یک تک‌فایل آماده شد!")
        print(f"  مسیر: {Path.home() / 'Desktop' / 'Sepehryar_Setup.exe'}")
        print("  ویژگی‌ها:")
        print("  - رابط کاربری لوکس مشکی-طلایی با لوگو و فونت فارسی")
        print("  - کاملاً مستقل: بدون نیاز به هیچ فایل کمکی روی سیستم مشتری")
        print("  - استخراج خودکار و بازخوانی هوشمند اینستالر اصلی")
        print("=" * 65)

    finally:
        # پاکسازی استیجینگ برای آزادسازی حافظه دیسک
        print("[*] در حال پاکسازی فایل‌های موقت استیجینگ...")
        shutil.rmtree(staging_dir, ignore_errors=True)
        if payload_zip.exists():
            try:
                payload_zip.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    main()
