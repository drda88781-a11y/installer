# setup_launcher.py
"""
لانچر و آماده‌ساز فوق‌العاده مدرن، لوکس و اختصاصی ستاپ سپهریار (SEPEHRYAR Setup Launcher)
Modern, Luxury Black & Gold SFX/Setup Launcher & Extractor GUI
ویژه بسته‌بندی فایل اجرایی مستقل (.EXE) با رابط کاربری فارسی و طراحی پریمیوم مشکی-طلایی
"""

import os
import sys
import time
import shutil
import ctypes
import platform
import zipfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# فعال‌سازی مقیاس‌بندی وضوح بالا در مانیتورهای مدرن
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon, QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config.settings import (
    THEME_COLORS,
    APP_NAME_FA,
    APP_ICON_PNG,
    APP_ICON_ICO,
    APP_LOGO_PNG,
    APP_LOGO_CIRCLE_PNG,
)
from ui.theme import load_application_fonts, get_application_stylesheet
from utils.icon_factory import IconFactory
from utils.win_helpers import format_bytes


def get_base_dir() -> Path:
    """دریافت مسیر ریشه برنامه (سازگار با حالت توسعه و فایل‌های فریز شده PyInstaller)"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def is_running_as_admin() -> bool:
    """بررسی برخورداری فرآیند جاری از دسترسی مدیر سیستم (Administrator)"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_system_ram_gb() -> float:
    """دریافت میزان حافظه رم فیزیکی سیستم برحسب گیگابایت"""
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return round(stat.ullTotalPhys / (1024 ** 3), 1)
        except Exception:
            return 8.0


def launch_installer_as_admin(exe_path: Path, work_dir: Optional[Path] = None) -> bool:
    """اجرای اینستالر اصلی با دسترسی کامل مدیر سیستم (UAC Elevation)"""
    cwd_str = str(work_dir or exe_path.parent)
    exe_str = str(exe_path)

    try:
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            exe_str,
            "",
            cwd_str,
            1,  # SW_SHOWNORMAL
        )
        if ret > 32:
            return True
    except Exception:
        pass

    try:
        subprocess.Popen([exe_str], cwd=cwd_str)
        return True
    except Exception:
        return False


class ExtractionWorker(QThread):
    """
    ترد پردازشی جهت استخراج سریع و بهینه بسته نصبی با گزارش لحظه‌ای سرعت و زمان باقیمانده
    """
    sig_progress = Signal(int, int, str, int, int, float, int)  # copied_bytes, total_bytes, cur_file, cur_idx, total_files, speed_bytes_per_sec, eta_seconds
    sig_finished = Signal(bool, str, Path)                       # success, message, target_dir

    def __init__(self, source_archive_or_dir: Path, target_dir: Path, parent=None):
        super().__init__(parent)
        self.source = source_archive_or_dir
        self.target_dir = target_dir
        self.is_cancelled = False
        self._start_time = 0.0
        self._last_emit_time = 0.0

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            self._start_time = time.time()
            self._last_emit_time = self._start_time
            self.target_dir.mkdir(parents=True, exist_ok=True)

            if self.source.is_file() and self.source.suffix.lower() == ".zip":
                self._extract_zip()
                return

            if self.source.is_dir():
                self._copy_dir()
                return

            if self.source.is_file() and self.source.suffix.lower() in (".rar", ".7z"):
                self._extract_external_archive()
                return

            self.sig_finished.emit(False, f"فرمت بسته نصبی ناشناخته است: {self.source}", self.target_dir)

        except Exception as ex:
            self.sig_finished.emit(False, f"خطا در استخراج بسته نصبی: {ex}", self.target_dir)

    def _extract_zip(self):
        with zipfile.ZipFile(self.source, "r") as zf:
            infolist = zf.infolist()
            total_files = len(infolist)
            total_bytes = sum(i.file_size for i in infolist)
            copied_bytes = 0
            copied_files = 0
            chunk_size = 1024 * 512

            for member in infolist:
                if self.is_cancelled:
                    self.sig_finished.emit(False, "عملیات استخراج توسط کاربر لغو گردید.", self.target_dir)
                    return

                if member.is_dir():
                    (self.target_dir / member.filename).mkdir(parents=True, exist_ok=True)
                    copied_files += 1
                    continue

                dest_file = self.target_dir / member.filename
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                with zf.open(member) as src_f, open(dest_file, "wb") as dst_f:
                    while True:
                        if self.is_cancelled:
                            break
                        chunk = src_f.read(chunk_size)
                        if not chunk:
                            break
                        dst_f.write(chunk)
                        copied_bytes += len(chunk)

                        now = time.time()
                        if now - self._last_emit_time > 0.08:
                            elapsed = max(0.1, now - self._start_time)
                            speed = copied_bytes / elapsed
                            rem_bytes = max(0, total_bytes - copied_bytes)
                            eta = int(rem_bytes / speed) if speed > 0 else 0

                            self.sig_progress.emit(
                                copied_bytes,
                                total_bytes,
                                member.filename,
                                copied_files,
                                total_files,
                                speed,
                                eta,
                            )
                            self._last_emit_time = now

                copied_files += 1

        self.sig_finished.emit(True, "استخراج فایل‌ها با موفقیت تکمیل شد.", self.target_dir)

    def _copy_dir(self):
        all_files = [f for f in self.source.rglob("*") if f.is_file()]
        total_files = len(all_files)
        total_bytes = sum(f.stat().st_size for f in all_files)
        copied_bytes = 0
        copied_files = 0
        chunk_size = 1024 * 1024 * 2

        for src_file in all_files:
            if self.is_cancelled:
                self.sig_finished.emit(False, "عملیات کپی توسط کاربر متوقف شد.", self.target_dir)
                return

            rel = src_file.relative_to(self.source)
            dst_file = self.target_dir / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                if dst_file.exists():
                    s_stat = src_file.stat()
                    d_stat = dst_file.stat()
                    if s_stat.st_size == d_stat.st_size and abs(s_stat.st_mtime - d_stat.st_mtime) < 1.0:
                        copied_bytes += s_stat.st_size
                        copied_files += 1
                        continue
            except Exception:
                pass

            with open(src_file, "rb") as fsrc, open(dst_file, "wb") as fdst:
                while True:
                    if self.is_cancelled:
                        break
                    chunk = fsrc.read(chunk_size)
                    if not chunk:
                        break
                    fdst.write(chunk)
                    copied_bytes += len(chunk)

                    now = time.time()
                    if now - self._last_emit_time > 0.08:
                        elapsed = max(0.1, now - self._start_time)
                        speed = copied_bytes / elapsed
                        rem_bytes = max(0, total_bytes - copied_bytes)
                        eta = int(rem_bytes / speed) if speed > 0 else 0

                        self.sig_progress.emit(
                            copied_bytes,
                            total_bytes,
                            str(rel),
                            copied_files,
                            total_files,
                            speed,
                            eta,
                        )
                        self._last_emit_time = now

            shutil.copystat(src_file, dst_file)
            copied_files += 1

        self.sig_finished.emit(True, "آماده‌سازی فایل‌های نصاب با موفقیت پایان یافت.", self.target_dir)

    def _extract_external_archive(self):
        candidates_7z = [
            Path(r"C:\Program Files\7-Zip\7z.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
        ]
        exe_7z = next((c for c in candidates_7z if c.exists()), None) or shutil.which("7z")

        if exe_7z:
            cmd = [str(exe_7z), "x", str(self.source), f"-o{self.target_dir}", "-y"]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            while True:
                if self.is_cancelled:
                    proc.kill()
                    self.sig_finished.emit(False, "استخراج لغو شد.", self.target_dir)
                    return
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if line and "%" in line:
                    self.sig_progress.emit(50, 100, line.strip(), 1, 1, 0.0, 0)

            if proc.returncode == 0:
                self.sig_finished.emit(True, "استخراج فایل‌ها با موفقیت پایان یافت.", self.target_dir)
            else:
                self.sig_finished.emit(False, f"خطا در استخراج آرشیو با کد {proc.returncode}", self.target_dir)
        else:
            self.sig_finished.emit(False, "ابزار استخراج آرشیو (7-Zip) در سیستم یافت نشد.", self.target_dir)


class SetupLauncherWindow(QWidget):
    """
    پنجره لوکس، مدرن و اختصاصی راه‌انداز ستاپ سپهریار (Setup Launcher)
    با استایل مشکی و طلایی پریمیوم و پشتیبانی کامل از زبان فارسی و راست‌به‌چپ (RTL)
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("نصاب هوشمند و یکپارچه حسابداری سپهریار")
        self.resize(750, 520)
        self.setMinimumSize(720, 490)
        self.setLayoutDirection(Qt.RightToLeft)

        if APP_ICON_PNG.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PNG)))
        elif APP_ICON_ICO.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_ICO)))

        self.worker: Optional[ExtractionWorker] = None
        self.payload_source: Optional[Path] = self._locate_payload()
        self.default_extract_path: Path = self._determine_default_extract_path()

        self.auto_launch_timer = QTimer(self)
        self.auto_launch_timer.setInterval(1000)
        self.auto_launch_timer.timeout.connect(self._on_auto_launch_tick)
        self.countdown_remaining = 3
        self.extracted_target_dir: Optional[Path] = None

        self._init_ui()
        self._center_window()

    def _center_window(self):
        geo = self.frameGeometry()
        center_point = self.screen().availableGeometry().center()
        geo.moveCenter(center_point)
        self.move(geo.topLeft())

    def _locate_payload(self) -> Optional[Path]:
        base_dir = get_base_dir()
        app_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else base_dir
        candidates = [
            base_dir / "payload.zip",
            base_dir / "payload.7z",
            base_dir / "SEPEHRYAR_SETUP_FILES",
            base_dir / "SETUP",
            app_dir / "payload.zip",
            app_dir / "payload.7z",
            app_dir / "SETUP.rar",
            app_dir / "SETUP",
            Path.cwd() / "payload.zip",
            Path.cwd() / "SETUP.rar",
            Path.cwd() / "SETUP",
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def _determine_default_extract_path(self) -> Path:
        for drive in ["D:", "E:", "F:"]:
            dp = Path(f"{drive}\\")
            if dp.exists():
                try:
                    usage = shutil.disk_usage(str(dp))
                    if usage.free > 6 * 1024 * 1024 * 1024:
                        return Path(f"{drive}\\SEPEHRYAR_SETUP_FILES")
                except Exception:
                    pass
        return Path(r"C:\SEPEHRYAR_SETUP_FILES")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(26, 22, 26, 22)
        main_layout.setSpacing(14)

        # ۱. سربرگ لوکس و اشرافی
        header_frame = QFrame(self)
        header_frame.setObjectName("HeaderFrame")
        header_frame.setStyleSheet(f"""
            QFrame#HeaderFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #141720,
                                            stop:0.65 #171B26,
                                            stop:1 #1C2030);
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 14px;
            }}
            QFrame#HeaderFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(20, 14, 20, 14)
        h_layout.setSpacing(18)

        # لوگوی سپهریار
        self.logo_lbl = QLabel(header_frame)
        logo_path = APP_LOGO_CIRCLE_PNG if APP_LOGO_CIRCLE_PNG.exists() else APP_LOGO_PNG
        if logo_path.exists():
            pix = QPixmap(str(logo_path)).scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_lbl.setPixmap(pix)
        else:
            self.logo_lbl.setPixmap(
                IconFactory.get_icon("database", size=50, color_override=THEME_COLORS["gold_primary"]).pixmap(50, 50)
            )
        h_layout.addWidget(self.logo_lbl)

        # متون عنوان و نسخه
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(4)

        t_row = QHBoxLayout()
        lbl_app_name = QLabel("راه‌انداز بسته جامع حسابداری سپهریار", header_frame)
        lbl_app_name.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 19px; font-weight: bold;")
        t_row.addWidget(lbl_app_name)
        t_row.addStretch()

        badge_ver = QLabel("نسخه سازمانی ۲۰۲۶.۱", header_frame)
        badge_ver.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(216, 168, 78, 0.15);
                color: {THEME_COLORS['gold_hover']};
                border: 1px solid rgba(216, 168, 78, 0.4);
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        t_row.addWidget(badge_ver)
        title_vbox.addLayout(t_row)

        lbl_sub = QLabel("SEPEHRYAR Enterprise ERP - Automated Setup Package Extractor & Bootstrapper", header_frame)
        lbl_sub.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 11.5px;")
        title_vbox.addWidget(lbl_sub)

        h_layout.addLayout(title_vbox, stretch=1)
        main_layout.addWidget(header_frame)

        # ۲. ویجت پشته‌ای صفحات (Pages Stack)
        self.stack = QStackedWidget(self)

        self.page_config = QWidget()
        self._init_page_config()
        self.stack.addWidget(self.page_config)  # Index 0

        self.page_progress = QWidget()
        self._init_page_progress()
        self.stack.addWidget(self.page_progress)  # Index 1

        self.page_done = QWidget()
        self._init_page_done()
        self.stack.addWidget(self.page_done)  # Index 2

        main_layout.addWidget(self.stack, stretch=1)

        # ۳. نوار پایینی دکمه‌های ناوبری
        self.bottom_bar = QHBoxLayout()
        self.bottom_bar.setSpacing(12)

        self.lbl_footer_status = QLabel("آماده جهت استخراج و راه‌اندازی ستاپ", self)
        self.lbl_footer_status.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px; border: none; background: transparent;")
        self.bottom_bar.addWidget(self.lbl_footer_status, stretch=1)

        self.btn_action = QPushButton("آماده‌سازی و شروع نصب >", self)
        self.btn_action.setProperty("class", "GoldPrimary")
        self.btn_action.setIcon(IconFactory.get_icon("check", size=16, color_override="#000000"))
        self.btn_action.setFixedSize(195, 40)
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.clicked.connect(self._on_primary_action)
        self.bottom_bar.addWidget(self.btn_action)

        self.btn_cancel = QPushButton("انصراف", self)
        self.btn_cancel.setProperty("class", "GoldSecondary")
        self.btn_cancel.setFixedSize(110, 40)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.close)
        self.bottom_bar.addWidget(self.btn_cancel)

        main_layout.addLayout(self.bottom_bar)

    def _init_page_config(self):
        layout = QVBoxLayout(self.page_config)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(10)

        # کارت توضیحات بسته
        info_card = QFrame(self.page_config)
        info_card.setObjectName("InfoCard")
        info_card.setStyleSheet(f"""
            QFrame#InfoCard {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 12px;
            }}
            QFrame#InfoCard QLabel {{
                border: none;
                background: transparent;
                padding: 0px;
            }}
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(6)

        lbl_desc = QLabel(
            "<b>کاربر گرامی، به سامانه راه‌انداز رسمی نرم‌افزار حسابداری و مالی سپهریار خوش آمدید.</b><br>"
            "این ابزار به صورت هوشمند و خودکار، بسته‌های پایگاه داده، ماژول‌های حسابداری، صنعتی، فروشگاهی "
            "و کتابخانه‌های سیستمی را در مسیر انتخابی شما آماده‌سازی نموده و محیط نصب اصلی را بازخوانی می‌نماید.",
            info_card,
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 12.5px; line-height: 1.5;")
        info_layout.addWidget(lbl_desc)

        layout.addWidget(info_card)

        # ردیف کارت‌های بررسی سریع وضعیت سیستم
        badges_frame = QFrame(self.page_config)
        badges_frame.setObjectName("BadgesFrame")
        badges_frame.setStyleSheet("QFrame#BadgesFrame { border: none; background: transparent; }")
        badges_layout = QHBoxLayout(badges_frame)
        badges_layout.setContentsMargins(0, 0, 0, 0)
        badges_layout.setSpacing(8)

        is_admin = is_running_as_admin()
        admin_text = "دسترسی مدیر: تأیید شده ✓" if is_admin else "دسترسی عادی (کاربر)"
        admin_color = THEME_COLORS["success"] if is_admin else THEME_COLORS["gold_hover"]
        pill_admin = self._create_info_pill("shield", admin_text, admin_color)
        badges_layout.addWidget(pill_admin)

        arch_text = f"سیستم: {platform.machine()} (ویندوز ۶۴ بیت)"
        pill_arch = self._create_info_pill("monitor", arch_text, THEME_COLORS["text_secondary"])
        badges_layout.addWidget(pill_arch)

        ram_gb = get_system_ram_gb()
        ram_text = f"رم سیستم: {ram_gb} GB"
        pill_ram = self._create_info_pill("cpu", ram_text, THEME_COLORS["text_secondary"])
        badges_layout.addWidget(pill_ram)

        layout.addWidget(badges_frame)

        # کارت مسیر استخراج و بررسی فضای دیسک
        path_card = QFrame(self.page_config)
        path_card.setObjectName("PathCard")
        path_card.setStyleSheet(f"""
            QFrame#PathCard {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 12px;
            }}
            QFrame#PathCard QLabel {{
                border: none;
                background: transparent;
                padding: 0px;
            }}
        """)
        path_layout = QVBoxLayout(path_card)
        path_layout.setContentsMargins(16, 14, 16, 14)
        path_layout.setSpacing(10)

        lbl_path_title = QLabel("مسیر استخراج و ذخیره‌سازی بسته‌های نصبی سپهریار:", path_card)
        lbl_path_title.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 13px; font-weight: bold;")
        path_layout.addWidget(lbl_path_title)

        row_path = QHBoxLayout()
        row_path.setSpacing(10)

        self.txt_extract_path = QLineEdit(path_card)
        self.txt_extract_path.setText(str(self.default_extract_path))
        self.txt_extract_path.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0E1015;
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 8px;
                padding: 7px 12px;
                font-size: 13px;
                min-height: 24px;
            }}
            QLineEdit:focus {{
                border-color: {THEME_COLORS['gold_primary']};
            }}
        """)
        self.txt_extract_path.textChanged.connect(self._update_free_space_badge)
        row_path.addWidget(self.txt_extract_path, stretch=1)

        btn_browse = QPushButton("تغییر مسیر...", path_card)
        btn_browse.setProperty("class", "GoldSecondary")
        btn_browse.setIcon(IconFactory.get_icon("folder", size=15))
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.setStyleSheet("padding: 7px 16px; font-size: 12px; min-width: 100px;")
        btn_browse.clicked.connect(self._browse_destination)
        row_path.addWidget(btn_browse)

        path_layout.addLayout(row_path)

        space_row = QHBoxLayout()
        self.lbl_free_space = QLabel(path_card)
        self.lbl_free_space.setStyleSheet("font-size: 12px;")
        space_row.addWidget(self.lbl_free_space, stretch=1)

        self.chk_auto_run = QCheckBox("راه‌اندازی خودکار اینستالر بلافاصله پس از آماده‌سازی", path_card)
        self.chk_auto_run.setChecked(True)
        self.chk_auto_run.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12px; border: none; background: transparent;")
        space_row.addWidget(self.chk_auto_run)

        path_layout.addLayout(space_row)
        layout.addWidget(path_card)

        self._update_free_space_badge()

    def _create_info_pill(self, icon_name: str, text: str, text_color: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("PillFrame")
        frame.setStyleSheet(f"""
            QFrame#PillFrame {{
                background-color: rgba(20, 23, 32, 0.9);
                border: 1px solid rgba(216, 168, 78, 0.25);
                border-radius: 8px;
            }}
            QFrame#PillFrame QLabel {{
                border: none;
                background: transparent;
                padding: 0px;
            }}
        """)
        hl = QHBoxLayout(frame)
        hl.setContentsMargins(10, 6, 10, 6)
        hl.setSpacing(8)

        lbl_icon = QLabel(frame)
        lbl_icon.setPixmap(IconFactory.get_icon(icon_name, size=15, color_override=THEME_COLORS["gold_primary"]).pixmap(15, 15))
        hl.addWidget(lbl_icon)

        lbl_txt = QLabel(text, frame)
        lbl_txt.setStyleSheet(f"color: {text_color}; font-size: 11.5px; font-weight: 500;")
        hl.addWidget(lbl_txt)

        return frame

    def _init_page_progress(self):
        layout = QVBoxLayout(self.page_progress)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(14)

        prog_card = QFrame(self.page_progress)
        prog_card.setObjectName("ProgCard")
        prog_card.setStyleSheet(f"""
            QFrame#ProgCard {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 14px;
            }}
            QFrame#ProgCard QLabel {{
                border: none;
                background: transparent;
                padding: 0px;
            }}
        """)
        p_layout = QVBoxLayout(prog_card)
        p_layout.setContentsMargins(20, 18, 20, 18)
        p_layout.setSpacing(12)

        top_prog_row = QHBoxLayout()
        self.lbl_prog_title = QLabel("در حال استخراج و آماده‌سازی فایل‌های نصاب...", prog_card)
        self.lbl_prog_title.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 14.5px; font-weight: bold;")
        top_prog_row.addWidget(self.lbl_prog_title, stretch=1)

        self.lbl_prog_percent = QLabel("۰٪", prog_card)
        self.lbl_prog_percent.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 18px; font-weight: bold;")
        top_prog_row.addWidget(self.lbl_prog_percent)
        p_layout.addLayout(top_prog_row)

        self.progress_bar = QProgressBar(prog_card)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #0E1015;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 10px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 {THEME_COLORS['gold_dark']},
                                            stop:0.45 {THEME_COLORS['gold_primary']},
                                            stop:0.8 {THEME_COLORS['gold_hover']},
                                            stop:1 #FDF2B8);
                border-radius: 9px;
            }}
        """)
        p_layout.addWidget(self.progress_bar)

        self.lbl_current_file = QLabel("آماده‌سازی مخزن بسته‌ها...", prog_card)
        self.lbl_current_file.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11.5px;")
        p_layout.addWidget(self.lbl_current_file)

        sep = QFrame(prog_card)
        sep.setObjectName("ProgSep")
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("QFrame#ProgSep { background-color: rgba(255, 255, 255, 0.08); border: none; max-height: 1px; }")
        p_layout.addWidget(sep)

        # شبکه آماری عملکرد زنده با کادرهای تفکیک‌شده شیک
        grid_metrics = QGridLayout()
        grid_metrics.setHorizontalSpacing(14)
        grid_metrics.setVerticalSpacing(10)

        box_speed = self._create_stat_box("سرعت انتقال:", "۰ MB/s")
        self.lbl_speed_val = box_speed.findChild(QLabel, "StatVal")
        grid_metrics.addWidget(box_speed, 0, 0)

        box_eta = self._create_stat_box("زمان باقیمانده:", "محاسبه...")
        self.lbl_eta_val = box_eta.findChild(QLabel, "StatVal")
        grid_metrics.addWidget(box_eta, 0, 1)

        box_files = self._create_stat_box("تعداد فایل‌ها:", "۰ از ۰")
        self.lbl_files_stat = box_files.findChild(QLabel, "StatVal")
        grid_metrics.addWidget(box_files, 1, 0)

        box_bytes = self._create_stat_box("حجم کل:", "۰ MB از ۰ MB")
        self.lbl_bytes_stat = box_bytes.findChild(QLabel, "StatVal")
        grid_metrics.addWidget(box_bytes, 1, 1)

        p_layout.addLayout(grid_metrics)
        layout.addWidget(prog_card)

    def _create_stat_box(self, title: str, initial_val: str) -> QFrame:
        box = QFrame()
        box.setObjectName("StatBox")
        box.setStyleSheet(f"""
            QFrame#StatBox {{
                background-color: #0E1015;
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 8px;
            }}
            QFrame#StatBox QLabel {{
                border: none;
                background: transparent;
                padding: 0px;
            }}
        """)
        hl = QHBoxLayout(box)
        hl.setContentsMargins(12, 8, 12, 8)
        hl.setSpacing(6)

        lbl_t = QLabel(title, box)
        lbl_t.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 11.5px;")
        hl.addWidget(lbl_t)

        lbl_v = QLabel(initial_val, box)
        lbl_v.setObjectName("StatVal")
        lbl_v.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 12px; font-weight: bold;")
        hl.addWidget(lbl_v, stretch=1)

        return box

    def _init_page_done(self):
        layout = QVBoxLayout(self.page_done)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(14)

        done_card = QFrame(self.page_done)
        done_card.setObjectName("DoneCard")
        done_card.setStyleSheet(f"""
            QFrame#DoneCard {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 14px;
            }}
            QFrame#DoneCard QLabel {{
                border: none;
                background: transparent;
                padding: 0px;
            }}
        """)
        d_layout = QVBoxLayout(done_card)
        d_layout.setContentsMargins(24, 28, 24, 28)
        d_layout.setAlignment(Qt.AlignCenter)
        d_layout.setSpacing(14)

        icon_check = QLabel(done_card)
        pix = IconFactory.get_icon("check", size=54, color_override=THEME_COLORS["success"]).pixmap(54, 54)
        icon_check.setPixmap(pix)
        icon_check.setAlignment(Qt.AlignCenter)
        d_layout.addWidget(icon_check)

        lbl_success = QLabel("بسته‌های نصبی با موفقیت استخراج و آماده‌سازی شدند", done_card)
        lbl_success.setStyleSheet(f"color: {THEME_COLORS['success']}; font-size: 16.5px; font-weight: bold;")
        lbl_success.setAlignment(Qt.AlignCenter)
        d_layout.addWidget(lbl_success)

        self.lbl_done_desc = QLabel("در حال فراخوانی اینستالر رسمی سپهریار...", done_card)
        self.lbl_done_desc.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 13px;")
        self.lbl_done_desc.setAlignment(Qt.AlignCenter)
        d_layout.addWidget(self.lbl_done_desc)

        done_btns_row = QHBoxLayout()
        done_btns_row.setSpacing(14)
        done_btns_row.setAlignment(Qt.AlignCenter)

        self.btn_run_now = QPushButton("اجرای فوری اینستالر", done_card)
        self.btn_run_now.setProperty("class", "GoldPrimary")
        self.btn_run_now.setIcon(IconFactory.get_icon("check", size=16, color_override="#000000"))
        self.btn_run_now.setFixedSize(185, 42)
        self.btn_run_now.setCursor(Qt.PointingHandCursor)
        self.btn_run_now.clicked.connect(self._launch_installer_now)
        done_btns_row.addWidget(self.btn_run_now)

        self.btn_open_folder = QPushButton("مشاهده پوشه فایل‌ها", done_card)
        self.btn_open_folder.setProperty("class", "GoldSecondary")
        self.btn_open_folder.setIcon(IconFactory.get_icon("folder", size=15))
        self.btn_open_folder.setFixedSize(185, 42)
        self.btn_open_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self._open_target_folder)
        done_btns_row.addWidget(self.btn_open_folder)

        d_layout.addLayout(done_btns_row)
        layout.addWidget(done_card)

    def _browse_destination(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "انتخاب پوشه استخراج بسته‌های نصبی",
            self.txt_extract_path.text().strip(),
        )
        if folder:
            self.txt_extract_path.setText(folder)

    def _update_free_space_badge(self):
        path_str = self.txt_extract_path.text().strip()
        if not path_str:
            return
        try:
            drive_anchor = Path(path_str).anchor or Path.cwd().anchor
            usage = shutil.disk_usage(drive_anchor)
            free_gb = round(usage.free / (1024 ** 3), 1)
            if usage.free > 3 * 1024 * 1024 * 1024:
                self.lbl_free_space.setText(f"✓ فضای آزاد درایو {drive_anchor}: <b style='color:#10B981'>{free_gb} GB</b> (کافی است)")
                self.btn_action.setEnabled(True)
            else:
                self.lbl_free_space.setText(f"⚠️ فضای آزاد درایو {drive_anchor}: <b style='color:#EF4444'>{free_gb} GB</b> (ناکافی؛ حداقل ۳ گیگابایت نیاز است)")
                self.btn_action.setEnabled(False)
        except Exception:
            self.lbl_free_space.setText("فضای درایو در دسترس نیست")

    def _on_primary_action(self):
        cur_idx = self.stack.currentIndex()
        if cur_idx == 0:
            target = Path(self.txt_extract_path.text().strip())
            if not self.payload_source or not self.payload_source.exists():
                self.lbl_footer_status.setText("⚠️ منبع بسته‌های نصبی یافت نشد.")
                return

            self.stack.setCurrentIndex(1)
            self.btn_action.setVisible(False)
            self.btn_cancel.setText("توقف عملیات")
            self.lbl_footer_status.setText("در حال استخراج و آماده‌سازی...")

            self.worker = ExtractionWorker(self.payload_source, target, parent=self)
            self.worker.sig_progress.connect(self._on_worker_progress)
            self.worker.sig_finished.connect(self._on_worker_finished)
            self.worker.start()

        elif cur_idx == 2:
            self._launch_installer_now()

    def _on_worker_progress(
        self,
        copied_bytes: int,
        total_bytes: int,
        cur_file: str,
        cur_idx: int,
        total_files: int,
        speed_bytes: float,
        eta_seconds: int,
    ):
        pct = int((copied_bytes / total_bytes) * 100) if total_bytes > 0 else 50
        pct = max(0, min(100, pct))
        self.progress_bar.setValue(pct)
        self.lbl_prog_percent.setText(f"{pct}٪")

        clean_file = cur_file
        if len(clean_file) > 55:
            clean_file = "..." + clean_file[-52:]
        self.lbl_current_file.setText(f"فایل در حال پردازش: {clean_file}")

        self.lbl_files_stat.setText(f"{cur_idx:,} از {total_files:,}")
        self.lbl_bytes_stat.setText(f"{format_bytes(copied_bytes)} از {format_bytes(total_bytes)}")

        speed_mb = speed_bytes / (1024 * 1024)
        self.lbl_speed_val.setText(f"{speed_mb:.1f} MB/s")

        if eta_seconds > 0:
            if eta_seconds > 60:
                mins = eta_seconds // 60
                secs = eta_seconds % 60
                self.lbl_eta_val.setText(f"{mins} دقیقه و {secs} ثانیه")
            else:
                self.lbl_eta_val.setText(f"{eta_seconds} ثانیه")
        else:
            self.lbl_eta_val.setText("لحظاتی بعد...")

    def _on_worker_finished(self, success: bool, message: str, target_dir: Path):
        self.extracted_target_dir = target_dir

        if success:
            self.stack.setCurrentIndex(2)
            self.btn_cancel.setVisible(False)
            self.btn_action.setVisible(False)
            self.lbl_footer_status.setText("عملیات آماده‌سازی با موفقیت پایان یافت.")

            if self.chk_auto_run.isChecked():
                self.countdown_remaining = 3
                self.lbl_done_desc.setText(f"در حال بازخوانی اینستالر رسمی سپهریار تا {self.countdown_remaining} ثانیه دیگر...")
                self.auto_launch_timer.start()
            else:
                self.lbl_done_desc.setText(f"فایل‌ها با موفقیت در مسیر زیر آماده‌سازی گردیدند:\n{target_dir}")
                self.btn_action.setText("خروج")
                self.btn_action.setVisible(True)
        else:
            self.stack.setCurrentIndex(0)
            self.btn_action.setVisible(True)
            self.btn_cancel.setText("انصراف")
            self.lbl_footer_status.setText(f"✕ {message}")

    def _on_auto_launch_tick(self):
        self.countdown_remaining -= 1
        if self.countdown_remaining > 0:
            self.lbl_done_desc.setText(f"در حال بازخوانی اینستالر رسمی سپهریار تا {self.countdown_remaining} ثانیه دیگر...")
        else:
            self.auto_launch_timer.stop()
            self._launch_installer_now()

    def _launch_installer_now(self):
        self.auto_launch_timer.stop()
        target_dir = self.extracted_target_dir or Path(self.txt_extract_path.text().strip())

        installer_candidates = [
            target_dir / "SEPEHRYAR_Installer.exe",
            target_dir / "SEPEHRYAR_Installer" / "SEPEHRYAR_Installer.exe",
            get_base_dir() / "SEPEHRYAR_Installer.exe",
            Path.cwd() / "SEPEHRYAR_Installer.exe",
        ]
        installer_exe = next((c for c in installer_candidates if c.exists()), None)

        if installer_exe:
            self.lbl_done_desc.setText(f"در حال فراخوانی اینستالر: {installer_exe.name}...")
            launch_installer_as_admin(installer_exe)
            QTimer.singleShot(1200, self.close)
        else:
            self.lbl_done_desc.setText(f"فایل‌های ستاپ در {target_dir} ذخیره شدند اما فایل اجرایی SEPEHRYAR_Installer.exe در آن یافت نشد.")
            self.btn_action.setText("بستن")
            self.btn_action.setVisible(True)

    def _open_target_folder(self):
        target_dir = self.extracted_target_dir or Path(self.txt_extract_path.text().strip())
        if target_dir.exists():
            os.startfile(str(target_dir))

    def closeEvent(self, event):
        if self.auto_launch_timer.isActive():
            self.auto_launch_timer.stop()
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1500)
        event.accept()


def run_launcher():
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setApplicationName("SEPEHRYAR_Setup_Launcher")

    font_family = load_application_fonts()
    app_font = QFont(font_family, 10)
    app.setFont(app_font)

    stylesheet = get_application_stylesheet(font_family)
    app.setStyleSheet(stylesheet)

    win = SetupLauncherWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_launcher()
