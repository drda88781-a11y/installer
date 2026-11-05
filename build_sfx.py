# build_sfx.py
"""
اسکریپت ساخت فایل نصاب سبک و بهینه سپهریار (Slim SFX Installer)
با فشرده‌سازی فوق‌العاده 7-Zip LZMA2:
- بدون embed کردن SQL Server (دانلود آنلاین هنگام نصب)
- فشرده‌سازی حداکثری با 7-Zip LZMA2 Ultra (بهتر از WinRAR)
- Solid archive با dictionary بالا
- ساخت یک تک‌فایل اجرایی Sepehryar_Setup.exe
- استخراج خودکار و اجرای مستقیم SEPEHRYAR_Installer.exe
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# فایل‌ها و پوشه‌هایی که از بسته‌بندی حذف می‌شوند (SQL Server آنلاین دانلود می‌شود)
SQL_EXCLUDE_PATTERNS = [
    "Microsoft.SQL.Server.2019.Enterprise.x64.rar",
    "SQL",                   # پوشه SQL Server 2008 R2
    "SQL_Extracted",
]

# فایل‌های غیرضروری که از بسته‌بندی حذف می‌شوند
CLEANUP_EXCLUDE_PATTERNS = [
    "*.pdb",
    "*.downloading",
    "app.publish",
]

# فایل‌های حیاتی نرم‌افزار که پسوند pdb دارند ولی نباید حذف شوند
PROTECTED_PDB_FILES = {"net.pdb", "cod.pdb"}


def find_7zip() -> Path:
    """یافتن 7-Zip"""
    candidates = [
        Path(r"C:\Program Files\7-Zip\7z.exe"),
        Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
    ]
    for c in candidates:
        if c.exists():
            return c
    which_7z = shutil.which("7z")
    if which_7z:
        return Path(which_7z)
    raise FileNotFoundError("ابزار 7-Zip (7z.exe) در سیستم یافت نشد. لطفاً 7-Zip را نصب نمایید.")


def find_rar_tool() -> Path:
    """یافتن WinRAR (فال‌بک)"""
    candidates = [
        Path(r"C:\Program Files\WinRAR\Rar.exe"),
        Path(r"C:\Program Files (x86)\WinRAR\Rar.exe"),
        Path(r"C:\Program Files\WinRAR\WinRAR.exe"),
    ]
    for c in candidates:
        if c.exists():
            return c
    which_rar = shutil.which("rar")
    if which_rar:
        return Path(which_rar)
    raise FileNotFoundError("ابزار WinRAR (Rar.exe) در سیستم یافت نشد.")


def should_exclude_from_setup(item_name: str) -> bool:
    """بررسی اینکه آیا یک آیتم باید از پوشه SETUP حذف شود"""
    item_lower = item_name.lower()
    for pattern in SQL_EXCLUDE_PATTERNS:
        if pattern.lower() == item_lower:
            return True
        if item_lower.startswith(pattern.lower()):
            return True
    return False


def get_setup_items(setup_dir: Path) -> list:
    """
    دریافت لیست آیتم‌های SETUP بدون فایل‌های SQL Server
    """
    items = []
    if not setup_dir.exists():
        return items

    for item in setup_dir.iterdir():
        if should_exclude_from_setup(item.name):
            continue
        items.append(item)

    return items


def calculate_source_size(base_dir: Path) -> float:
    """محاسبه حجم کل فایل‌هایی که بسته‌بندی می‌شوند"""
    total = 0

    installer_exe = base_dir / "SEPEHRYAR_Installer.exe"
    if installer_exe.exists():
        total += installer_exe.stat().st_size

    # SETUP بدون SQL
    setup_dir = base_dir / "SETUP"
    if setup_dir.exists():
        for item in get_setup_items(setup_dir):
            if item.is_file():
                total += item.stat().st_size
            elif item.is_dir():
                for f in item.rglob("*"):
                    if f.is_file():
                        total += f.stat().st_size

    # exe full
    exe_full = base_dir / "exe full"
    if exe_full.exists():
        for f in exe_full.rglob("*"):
            if f.is_file():
                total += f.stat().st_size

    # assets
    assets = base_dir / "assets"
    if assets.exists():
        for f in assets.rglob("*"):
            if f.is_file():
                total += f.stat().st_size

    return total


def build_sfx_7zip(output_name: str = "Sepehryar_Setup.exe"):
    """ساخت SFX با 7-Zip LZMA2 Ultra"""
    base_dir = Path(__file__).resolve().parent
    dist_dir = base_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    output_path = dist_dir / output_name

    # بررسی 7-Zip
    seven_zip = find_7zip()
    print(f"[+] ابزار فشرده‌ساز: {seven_zip}")

    installer_exe = base_dir / "SEPEHRYAR_Installer.exe"
    setup_dir = base_dir / "SETUP"
    exe_full_dir = base_dir / "exe full"
    assets_dir = base_dir / "assets"

    if not installer_exe.exists():
        print(f"[-] فایل {installer_exe.name} یافت نشد. لطفاً ابتدا اینستالر را بیلد نمایید.")
        return False

    # محاسبه حجم قبل از فشرده‌سازی
    src_size = calculate_source_size(base_dir)
    src_size_mb = round(src_size / (1024 * 1024), 1)
    print(f"[+] حجم فایل‌های مبدأ (بدون SQL Server): {src_size_mb} MB")

    # پوشه موقت برای آماده‌سازی فایل‌ها
    staging_dir = base_dir / "scratch" / "_sfx_staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    print("[+] آماده‌سازی فایل‌ها برای بسته‌بندی...")

    # کپی SEPEHRYAR_Installer.exe
    shutil.copy2(installer_exe, staging_dir / installer_exe.name)

    # کپی SETUP بدون SQL
    if setup_dir.exists():
        staging_setup = staging_dir / "SETUP"
        staging_setup.mkdir(parents=True, exist_ok=True)
        for item in get_setup_items(setup_dir):
            dst = staging_setup / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)
        print(f"    SETUP/ (بدون SQL): {len(list(staging_setup.rglob('*')))} فایل")

    # کپی exe full
    if exe_full_dir.exists():
        staging_exe = staging_dir / "exe full"
        shutil.copytree(exe_full_dir, staging_exe, dirs_exist_ok=True)

        # حذف فایل‌های غیرضروری (به استثنای Net.pdb و فایل‌های حیاتی)
        for pattern in CLEANUP_EXCLUDE_PATTERNS:
            if pattern.startswith("*."):
                ext = pattern[1:]
                for f in staging_exe.rglob(f"*{ext}"):
                    if f.name.lower() in PROTECTED_PDB_FILES:
                        continue
                    f.unlink()
            else:
                for f in staging_exe.rglob(pattern):
                    if f.is_dir():
                        shutil.rmtree(f, ignore_errors=True)
                    elif f.is_file():
                        f.unlink()

        print(f"    exe full/: {len(list(staging_exe.rglob('*')))} فایل")

    # کپی assets
    if assets_dir.exists():
        shutil.copytree(assets_dir, staging_dir / "assets", dirs_exist_ok=True)

    # محاسبه حجم نهایی staging
    staging_size = sum(f.stat().st_size for f in staging_dir.rglob("*") if f.is_file())
    staging_mb = round(staging_size / (1024 * 1024), 1)
    print(f"[+] حجم کل آماده بسته‌بندی: {staging_mb} MB")

    # ساخت فایل تنظیمات SFX
    sfx_cfg_path = base_dir / "scratch" / "sfx_config.txt"
    sfx_cfg_content = (
        ';!@Install@!UTF-8!\n'
        'Title="نصاب جامع نرم‌افزار حسابداری سپهریار"\n'
        'BeginPrompt="آیا مایل به نصب نرم‌افزار حسابداری سپهریار هستید؟"\n'
        'RunProgram="SEPEHRYAR_Installer.exe"\n'
        'Directory="SEPEHRYAR_SETUP_FILES"\n'
        ';!@InstallEnd@!\n'
    )
    sfx_cfg_path.write_text(sfx_cfg_content, encoding="utf-8")

    if output_path.exists():
        try:
            output_path.unlink()
        except Exception:
            pass

    # مسیر SFX module 7-Zip
    sfx_module = seven_zip.parent / "7z.sfx"
    if not sfx_module.exists():
        # جستجوی مدل SFX
        alt_sfx = seven_zip.parent / "7zSD.sfx"
        sfx_module = alt_sfx if alt_sfx.exists() else sfx_module

    # مرحله ۱: ساخت آرشیو 7z با LZMA2 Ultra
    archive_7z = dist_dir / "Sepehryar_Setup.7z"
    if archive_7z.exists():
        archive_7z.unlink()

    print(f"\n[+] در حال فشرده‌سازی با 7-Zip LZMA2 Ultra...")
    print("[+] این فرایند ممکن است ۳ تا ۱۰ دقیقه زمان ببرد...")

    cmd = [
        str(seven_zip),
        "a",                    # Add to archive
        "-t7z",                 # فرمت 7z
        "-m0=LZMA2",           # الگوریتم LZMA2
        "-mx=9",               # Ultra compression
        "-mfb=273",            # Fast bytes
        "-md=256m",            # 256MB dictionary
        "-ms=on",              # Solid archive
        "-mmt=on",             # Multi-threading
        str(archive_7z),
        str(staging_dir) + "\\*",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(staging_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            clean = line.strip()
            if "%" in clean or "Everything" in clean or "Compressing" in clean:
                print(f"    {clean}")

    rc = proc.wait()

    if rc != 0 or not archive_7z.exists():
        print(f"\n[-] خطا در فشرده‌سازی 7z. کد خروج: {rc}")
        # پاکسازی staging
        shutil.rmtree(staging_dir, ignore_errors=True)
        return False

    archive_size_mb = round(archive_7z.stat().st_size / (1024 * 1024), 1)
    compression_ratio = round((1 - archive_7z.stat().st_size / staging_size) * 100, 1) if staging_size > 0 else 0
    print(f"\n[✓] آرشیو 7z ایجاد شد: {archive_size_mb} MB (فشرده‌سازی {compression_ratio}%)")

    # مرحله ۲: ساخت SFX
    if sfx_module.exists():
        print(f"[+] ترکیب SFX module + config + archive...")
        try:
            with open(output_path, "wb") as out_f:
                # SFX module
                with open(sfx_module, "rb") as sfx_f:
                    out_f.write(sfx_f.read())
                # Config
                with open(sfx_cfg_path, "rb") as cfg_f:
                    out_f.write(cfg_f.read())
                # Archive
                with open(archive_7z, "rb") as arc_f:
                    while True:
                        chunk = arc_f.read(1024 * 1024)
                        if not chunk:
                            break
                        out_f.write(chunk)

            # حذف آرشیو موقت
            archive_7z.unlink()
        except Exception as ex:
            print(f"[-] خطا در ساخت SFX: {ex}")
            shutil.rmtree(staging_dir, ignore_errors=True)
            return False
    else:
        # اگر SFX module پیدا نشد، فقط 7z خروجی میدیم
        print("[!] SFX module یافت نشد — خروجی به صورت آرشیو 7z ذخیره شد.")
        output_path = archive_7z

    # پاکسازی staging
    shutil.rmtree(staging_dir, ignore_errors=True)

    if output_path.exists():
        final_size_mb = round(output_path.stat().st_size / (1024 * 1024), 1)
        print(f"\n{'=' * 60}")
        print(f"[✓] فایل نهایی نصاب سبک سپهریار با موفقیت ایجاد گردید!")
        print(f"    مسیر:  {output_path}")
        print(f"    حجم:   {final_size_mb} MB")
        print(f"    فشرده: {compression_ratio}%")
        print(f"    (SQL Server هنگام نصب آنلاین دانلود می‌شود)")
        print(f"{'=' * 60}")
        return True
    else:
        print(f"\n[-] خطا در ایجاد فایل SFX نهایی.")
        return False


def build_sfx_winrar(output_name: str = "Sepehryar_Setup.exe"):
    """فال‌بک: ساخت SFX با WinRAR (روش قبلی، ولی بدون SQL)"""
    base_dir = Path(__file__).resolve().parent
    dist_dir = base_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    output_path = dist_dir / output_name

    rar_exe = find_rar_tool()
    print(f"[+] ابزار فشرده‌ساز (فال‌بک): {rar_exe}")

    installer_exe = base_dir / "SEPEHRYAR_Installer.exe"
    setup_dir = base_dir / "SETUP"
    exe_full_dir = base_dir / "exe full"
    assets_dir = base_dir / "assets"

    if not installer_exe.exists():
        print(f"[-] فایل {installer_exe.name} یافت نشد. لطفاً ابتدا اینستالر را بیلد نمایید.")
        return False

    # ساخت فایل پیکربندی SFX
    sfx_cfg_path = base_dir / "scratch" / "sfx_config.txt"
    sfx_cfg_path.parent.mkdir(parents=True, exist_ok=True)

    sfx_cfg_content = (
        ";The comment below contains SFX script commands\n"
        "Title=SEPEHRYAR ERP Setup\n"
        "Path=.\\SEPEHRYAR_SETUP_FILES\n"
        "Setup=SEPEHRYAR_Installer.exe\n"
        "Silent=1\n"
        "Overwrite=1\n"
    )
    sfx_cfg_path.write_text(sfx_cfg_content, encoding="ascii")

    if output_path.exists():
        try:
            output_path.unlink()
        except Exception:
            pass

    # پوشه موقت برای آماده‌سازی فایل‌ها
    staging_dir = base_dir / "scratch" / "_sfx_staging_winrar"
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    print("[+] آماده‌سازی فایل‌ها برای بسته‌بندی...")

    # کپی SEPEHRYAR_Installer.exe
    shutil.copy2(installer_exe, staging_dir / installer_exe.name)

    # کپی SETUP بدون SQL
    if setup_dir.exists():
        staging_setup = staging_dir / "SETUP"
        staging_setup.mkdir(parents=True, exist_ok=True)
        for item in get_setup_items(setup_dir):
            dst = staging_setup / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)

    # کپی exe full
    if exe_full_dir.exists():
        staging_exe = staging_dir / "exe full"
        shutil.copytree(exe_full_dir, staging_exe, dirs_exist_ok=True)
        # حذف فایل‌های غیرضروری (به استثنای Net.pdb و فایل‌های حیاتی)
        for pattern in CLEANUP_EXCLUDE_PATTERNS:
            if pattern.startswith("*."):
                ext = pattern[1:]
                for f in staging_exe.rglob(f"*{ext}"):
                    if f.name.lower() in PROTECTED_PDB_FILES:
                        continue
                    f.unlink()
            else:
                for f in staging_exe.rglob(pattern):
                    if f.is_dir():
                        shutil.rmtree(f, ignore_errors=True)
                    elif f.is_file():
                        f.unlink()

    # کپی assets
    if assets_dir.exists():
        shutil.copytree(assets_dir, staging_dir / "assets", dirs_exist_ok=True)

    print(f"[+] در حال فشرده‌سازی و ایجاد فایل SFX با WinRAR...")
    print("[+] این فرایند ممکن است ۲ تا ۵ دقیقه زمان ببرد...")

    cmd = [
        str(rar_exe),
        "a",
        "-sfx",             # ساخت Self-Extracting Archive
        "-s",               # Solid archive
        "-m5",              # Best compression
        "-md128m",          # 128MB dictionary
        "-r",               # Recursive
        "-ep1",             # Exclude base folder name from paths
        f"-z{sfx_cfg_path}",
        str(output_path),
        "*",                # بسته‌بندی تمام محتویات پوشه staging
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(staging_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            clean = line.strip()
            if clean.startswith("Adding") or "%" in clean or "Done" in clean:
                print(f"    {clean}")

    rc = proc.wait()

    # پاکسازی
    shutil.rmtree(staging_dir, ignore_errors=True)

    if rc == 0 and output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"\n[✓] فایل نهایی نصاب سبک با موفقیت ایجاد گردید!")
        print(f"    مسیر: {output_path}")
        print(f"    حجم نهایی: {size_mb:.1f} مگابایت")

        # کپی در ریشه پروژه
        root_exe = base_dir / output_name
        try:
            shutil.copy2(output_path, root_exe)
            print(f"[✓] کپی در ریشه پروژه: {root_exe}")
        except Exception as e:
            print(f"[!] خطا در کپی در ریشه: {e}")

        # کپی روی دسکتاپ کاربر
        desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        if desktop.exists():
            desktop_exe = desktop / output_name
            try:
                shutil.copy2(output_path, desktop_exe)
                print(f"[✓] کپی روی دسکتاپ کاربر: {desktop_exe}")
            except Exception as e:
                print(f"[!] خطا در کپی روی دسکتاپ: {e}")

        return True
    else:
        print(f"\n[-] خطا در ایجاد فایل SFX. کد خروج: {rc}")
        return False


def build_gui_launcher(output_name: str = "Sepehryar_Setup.exe") -> bool:
    """
    کامپایل و ساخت فایل اجرایی مدرن و لوکس لانچر ستاپ سپهریار (GUI Setup Launcher)
    با استایل مشکی و طلایی اختصاصی و مجوز Administrator با استفاده از PyInstaller
    """
    base_dir = Path(__file__).resolve().parent
    dist_dir = base_dir / "dist"
    work_dir = base_dir / "build" / "launcher"
    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 65)
    print("ساخت فایل اجرایی لانچر مدرن ستاپ سپهریار (SEPEHRYAR Setup Launcher)")
    print("=" * 65)

    launcher_script = base_dir / "setup_launcher.py"
    if not launcher_script.exists():
        print(f"[-] اسکریپت {launcher_script} یافت نشد.")
        return False

    ico_path = base_dir / "assets" / "icons" / "app_icon.ico"
    icon_args = [f"--icon={ico_path}"] if ico_path.exists() else []

    add_data_args = [
        f"--add-data={base_dir / 'assets'};assets",
    ]
    font_file = base_dir / "AradVF.ttf"
    if font_file.exists():
        add_data_args.append(f"--add-data={font_file};.")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        f"--name={Path(output_name).stem}",
        "--noconsole",
        "--uac-admin",
        "--onefile",
        "--clean",
        "--noconfirm",
        f"--distpath={dist_dir}",
        f"--workpath={work_dir}",
        "--hidden-import=psutil",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
    ] + icon_args + add_data_args + [str(launcher_script)]

    print(f"[+] در حال کامپایل با PyInstaller...")
    print(f"    دستور: {' '.join(cmd)}")
    print("-" * 65)

    ret = subprocess.run(cmd)
    if ret.returncode == 0:
        exe_dist = dist_dir / output_name
        exe_root = base_dir / output_name
        if exe_dist.exists():
            try:
                shutil.copy2(exe_dist, exe_root)
                print(f"\n[✓] فایل اجرایی در ریشه پروژه ذخیره گردید: {exe_root}")
            except Exception as e:
                print(f"[!] کپی در ریشه انجام نشد: {e}")

        print("\n" + "=" * 65)
        print(f"[✓] فایل نهایی لانچر ستاپ با موفقیت ساخته شد: {exe_dist}")
        print("=" * 65)
        return True
    else:
        print(f"\n[-] خطای کامپایل لانچر با کد: {ret.returncode}")
        return False


def build_sfx_installer(output_name: str = "Sepehryar_Setup.exe"):
    """
    ساخت فایل نصاب:
    به طور پیش‌فرض، ساخت لانچر گرافیکی اختصاصی با طراحی لوکس سپهریار (GUI Launcher)
    یا ساخت با 7-Zip / WinRAR در صورت ارسال پارامتر --legacy
    """
    if "--legacy" in sys.argv or "--sfx" in sys.argv:
        try:
            return build_sfx_7zip(output_name)
        except FileNotFoundError:
            print("[!] 7-Zip یافت نشد — استفاده از WinRAR به عنوان فال‌بک...")
            try:
                return build_sfx_winrar(output_name)
            except FileNotFoundError:
                print("[-] هیچ ابزار فشرده‌سازی (7-Zip یا WinRAR) یافت نشد.")
                return False
    else:
        return build_gui_launcher(output_name)


if __name__ == "__main__":
    build_sfx_installer()

