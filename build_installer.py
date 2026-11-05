# build_installer.py
"""
اسکریپت بیلد و کامپایل رسمی پروژه به فایل اجرایی ویندوز (Windows EXE) با PyInstaller
Build script to compile SEPEHRYAR Installer into a standalone Windows EXE
"""

import os
import subprocess
import sys
from pathlib import Path

# ایمن‌سازی خروجی کنسول ویندوز برای یونیکد
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent


def build():
    print("=" * 60)
    print("SEPEHRYAR INSTALLER - STANDALONE EXE BUILDER")
    print("=" * 60)

    dist_dir = BASE_DIR / "dist"
    build_dir = BASE_DIR / "build"

    # آرگومان‌های داده‌های همراه
    add_data_args = [
        f"--add-data={BASE_DIR / 'assets'};assets",
    ]
    if (BASE_DIR / "AradVF.ttf").exists():
        add_data_args.append(f"--add-data={BASE_DIR / 'AradVF.ttf'};.")

    onefile = "--onedir" not in sys.argv
    mode_flag = "--onefile" if onefile else "--onedir"

    ico_path = BASE_DIR / "assets" / "icons" / "app_icon.ico"
    icon_args = [f"--icon={ico_path}"] if ico_path.exists() else []

    hidden_imports = [
        "--hidden-import=pyodbc",
        "--hidden-import=pefile",
        "--hidden-import=psutil",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=SEPEHRYAR_Installer",
        "--noconsole",
        "--uac-admin",
        mode_flag,
    ] + icon_args + hidden_imports + [
        "--clean",
        "--noconfirm",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
    ] + add_data_args + [str(BASE_DIR / "main.py")]

    print(f"Building mode: {mode_flag}")
    print("Running command:")
    print(" ".join(cmd))
    print("-" * 60)

    ret = subprocess.run(cmd)
    if ret.returncode == 0:
        import shutil
        print("\n" + "=" * 60)
        print("✓ BUILD SUCCESSFUL!")
        if onefile:
            exe_src = dist_dir / "SEPEHRYAR_Installer.exe"
            exe_dst = BASE_DIR / "SEPEHRYAR_Installer.exe"
            if exe_src.exists():
                shutil.copy2(exe_src, exe_dst)
                print(f"فایل اجرایی مستقل (Standalone .EXE) با موفقیت در ریشه پروژه کپی شد:\n{exe_dst}")
        else:
            print(f"خروجی در مسیر زیر ایجاد شد:\n{dist_dir / 'SEPEHRYAR_Installer'}")
        print("=" * 60)
    else:
        print(f"\n✕ Build failed with exit code: {ret.returncode}", file=sys.stderr)
        sys.exit(ret.returncode)


if __name__ == "__main__":
    build()
