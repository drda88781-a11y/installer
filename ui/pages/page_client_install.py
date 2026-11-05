# ui/pages/page_client_install.py
"""
صفحه اختصاصی نصب سریع کلاینت و پیش‌نیازها (بدون نیاز به SQL Server)
Dedicated Client Quick Setup Page (Installs Stimulsoft, Crystal Reports, Fonts & Selected Products)
"""

from pathlib import Path
from typing import Dict, List, Set, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from app_logging.app_logger import logger
from config.settings import (
    EXE_FULL_DIR,
    INSTALL_ROOT_DIR_NAME,
    PRODUCTS_CONFIG,
    THEME_COLORS,
)
from file_manager.drive_scanner import scan_drives, DriveInfo
from file_manager.file_copier import FileCopier, create_sepehryar_root_structure
from packages.product_catalog import (
    resolve_installed_exe_path,
    resolve_product_source_dir,
)
from prerequisites.prereq_installer import PrerequisiteManager, PrereqStatus
from utils.icon_factory import IconFactory
from utils.shortcut_manager import create_shortcuts_for_product


class ClientInstallWorker(QThread):
    """ورکر پردازش نصب در پس‌زمینه بدون فریز کردن رابط کاربری"""
    sig_progress = Signal(int, str)         # percent, message
    sig_log = Signal(str, str)              # text, color/level
    sig_finished = Signal(bool, str)        # success, summary_message

    def __init__(self, target_drive: str, selected_product_ids: List[str]):
        super().__init__()
        self.target_drive = target_drive
        self.selected_product_ids = selected_product_ids
        self._is_cancelled = False

    def run(self):
        try:
            self.sig_progress.emit(5, "آغاز آماده‌سازی و بررسی پیش‌نیازهای کلاینت...")
            self.sig_log.emit(f"درایو مقصد: {self.target_drive} | محصولات انتخابی: {', '.join(self.selected_product_ids)}", "INFO")
            logger.log("CLIENT_INSTALL", "START", "RUNNING", f"شروع نصب کلاینت در {self.target_drive}")

            # ۱. نصب پیش‌نیازها
            prereq = PrerequisiteManager()

            # ۱-۱. استیمول‌سافت
            self.sig_progress.emit(15, "در حال بررسی و نصب سایلنت استیمول‌سافت (Stimulsoft 2013)...")
            self.sig_log.emit("بررسی بسته Stimulsoft Reports.Net 2013...", "INFO")
            if not prereq.install_stimulsoft():
                self.sig_log.emit("هشدار: فایل نصبی استیمول‌سافت اجرا نشد یا قبلاً نصب بوده است.", "WARN")
            else:
                self.sig_log.emit("استیمول‌سافت با موفقیت آماده شد.", "SUCCESS")

            # ۱-۲. کریستال ریپورتز
            self.sig_progress.emit(35, "در حال بررسی و نصب سایلنت کریستال ریپورتز (Crystal Reports)...")
            self.sig_log.emit("بررسی ران‌تایم Crystal Reports 10.5 (نسخه ۳۲ و ۶۴ بیتی)...", "INFO")
            if not prereq.install_crystal_reports():
                self.sig_log.emit("هشدار: کریستال ریپورتز نصب نشد یا قبلاً در رجیستری موجود است.", "WARN")
            else:
                self.sig_log.emit("کریستال ریپورتز با موفقیت آماده شد.", "SUCCESS")

            # ۱-۳. فونت‌های فارسی
            self.sig_progress.emit(50, "در حال انتقال و ثبت فونت‌های فارسی (IRANSans و Arad)...")
            self.sig_log.emit("کپی فونت‌ها در پوشه C:\\Windows\\Fonts و ثبت در رجیستری...", "INFO")
            prereq.install_farsi_fonts()
            self.sig_log.emit("فونت‌های سیستم با موفقیت ثبت شدند.", "SUCCESS")

            # ۲. ساخت ساختار پوشه SEPEHRYAR در درایو مقصد
            self.sig_progress.emit(60, f"ایجاد ساختار پوشه SEPEHRYAR در درایو {self.target_drive}...")
            root_paths = create_sepehryar_root_structure(self.target_drive, needs_setup=False)
            root_dir = root_paths["root"]
            self.sig_log.emit(f"ساختار ریشه کلاینت در {root_dir} ایجاد گردید.", "SUCCESS")

            # ۳. کپی فایل‌های اجرایی محصولات انتخابی
            total_prods = len(self.selected_product_ids)
            for idx, pid in enumerate(self.selected_product_ids, start=1):
                cfg = PRODUCTS_CONFIG.get(pid, {})
                title = cfg.get("title", pid)
                folder_name = cfg.get("folder_name", pid)
                
                pct = 60 + int((idx / total_prods) * 30)
                self.sig_progress.emit(pct, f"کپی فایل‌های اجرایی {title} ({idx} از {total_prods})...")
                self.sig_log.emit(f"در حال کپی بسته {title} ({folder_name})...", "INFO")

                src_dir = resolve_product_source_dir(pid)
                if not src_dir or not src_dir.exists():
                    self.sig_log.emit(f"خطا: پوشه منبع {title} در exe full یافت نشد!", "ERROR")
                    continue

                dest_dir = root_dir / folder_name
                dest_dir.mkdir(parents=True, exist_ok=True)

                copier = FileCopier()
                copier.copy_directory_contents(
                    source_dir=src_dir,
                    destination_dir=dest_dir,
                    stage_name=f"COPY_{folder_name}"
                )
                self.sig_log.emit(f"پکیج {title} با موفقیت در {dest_dir} کپی شد.", "SUCCESS")

                # ۴. ایجاد میانبر دسکتاپ و استارت منو
                target_exe = resolve_installed_exe_path(root_dir, pid)
                if target_exe and target_exe.exists():
                    shortcut_name = cfg.get("shortcut_name", f"سپهریار - {title}")
                    shortcuts = create_shortcuts_for_product(title, shortcut_name, target_exe)
                    if shortcuts:
                        self.sig_log.emit(f"میانبر «{shortcut_name}» روی دسکتاپ ایجاد شد.", "SUCCESS")

            self.sig_progress.emit(100, "عملیات استقرار کلاینت و پیش‌نیازها با موفقیت تکمیل شد.")
            self.sig_log.emit("✅ تمام پیش‌نیازها و برنامه‌های کلاینت با موفقیت نصب و فعال شدند.", "SUCCESS")
            logger.log("CLIENT_INSTALL", "FINISH", "SUCCESS", "نصب کلاینت با موفقیت به پایان رسید.")
            self.sig_finished.emit(True, "استقرار کلاینت با موفقیت به پایان رسید.")

        except Exception as ex:
            logger.log("CLIENT_INSTALL", "ERROR", "EXCEPTION", str(ex), error=str(ex))
            self.sig_log.emit(f"خطای غیرمنتظره در نصب کلاینت: {ex}", "ERROR")
            self.sig_finished.emit(False, str(ex))


class ClientProductCard(QFrame):
    """کارت تعاملی انتخاب نسخه نرم‌افزار در تب کلاینت"""
    clicked = Signal(str, bool)

    def __init__(self, product_id: str, title: str, symbol: str, exe_name: str, desc: str, checked: bool = False, parent=None):
        super().__init__(parent)
        self.product_id = product_id
        self.is_checked = checked
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui(title, symbol, exe_name, desc)
        self._update_style()

    def _init_ui(self, title: str, symbol: str, exe_name: str, desc: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # ردیف بالا: آیکون، نام و چک‌باکس
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        lbl_symbol = QLabel(symbol, self)
        lbl_symbol.setStyleSheet("font-size: 20px;")
        top_row.addWidget(lbl_symbol)

        lbl_title = QLabel(title, self)
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {THEME_COLORS['text_primary']};")
        top_row.addWidget(lbl_title, stretch=1)

        self.lbl_check = QLabel("✓" if self.is_checked else "", self)
        self.lbl_check.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: #0E1015;
            background-color: {THEME_COLORS['gold_primary']};
            border-radius: 4px;
            padding: 1px 5px;
        """)
        self.lbl_check.setVisible(self.is_checked)
        top_row.addWidget(self.lbl_check)

        layout.addLayout(top_row)

        lbl_desc = QLabel(desc, self)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"font-size: 11px; color: {THEME_COLORS['text_secondary']};")
        layout.addWidget(lbl_desc)

        lbl_exe = QLabel(f"فایل اجرایی: {exe_name}", self)
        lbl_exe.setStyleSheet(f"font-size: 10px; color: {THEME_COLORS['text_muted']}; font-family: Consolas, monospace;")
        layout.addWidget(lbl_exe)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle()
        super().mousePressEvent(event)

    def toggle(self):
        self.set_checked(not self.is_checked)
        self.clicked.emit(self.product_id, self.is_checked)

    def set_checked(self, checked: bool):
        self.is_checked = checked
        self.lbl_check.setVisible(checked)
        self._update_style()

    def _update_style(self):
        if self.is_checked:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(216, 168, 78, 0.12);
                    border: 1.5px solid {THEME_COLORS['gold_primary']};
                    border-radius: 10px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {THEME_COLORS['card_bg']};
                    border: 1px solid {THEME_COLORS['card_border']};
                    border-radius: 10px;
                }}
                QFrame:hover {{
                    border-color: {THEME_COLORS['card_border_active']};
                    background-color: {THEME_COLORS['card_hover']};
                }}
            """)


class ClientInstallPage(QWidget):
    """
    صفحه کامل و یکپارچه تب «نصب کلاینت و پیش‌نیازها»
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: Optional[ClientInstallWorker] = None
        self.selected_products: Set[str] = {"SEPEHRYAR.Hesabdari"}  # پیش‌فرض: حسابداری
        self.product_cards: Dict[str, ClientProductCard] = {}
        self._init_ui()
        self._populate_drives()
        self._check_prerequisites_status()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 18, 28, 18)
        main_layout.setSpacing(12)

        # ۱. سربرگ صفحه
        header_card = QFrame(self)
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 10px;
            }}
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(16, 10, 16, 10)
        h_layout.setSpacing(12)

        icon_client = QLabel(header_card)
        icon_client.setPixmap(IconFactory.get_icon("client", size=32, color_override=THEME_COLORS["gold_primary"]).pixmap(32, 32))
        h_layout.addWidget(icon_client)

        v_head = QVBoxLayout()
        v_head.setSpacing(3)
        lbl_title = QLabel("راه‌اندازی ایستگاه کاری کلاینت سپهریار", header_card)
        lbl_title.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {THEME_COLORS['gold_primary']};")
        v_head.addWidget(lbl_title)

        lbl_sub = QLabel("نصب خودکار ران‌تایم‌های چاپ (استیمول‌سافت و کریستال) + فونت‌های فارسی + کپی نسخه انتخابی (بدون نیاز به SQL Server)", header_card)
        lbl_sub.setStyleSheet(f"font-size: 11.5px; color: {THEME_COLORS['text_secondary']};")
        v_head.addWidget(lbl_sub)
        h_layout.addLayout(v_head, stretch=1)

        # انتخاب درایو مقصد
        drive_box = QHBoxLayout()
        drive_box.setSpacing(6)
        lbl_drv = QLabel("درایو مقصد:", header_card)
        lbl_drv.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME_COLORS['text_primary']};")
        drive_box.addWidget(lbl_drv)

        self.cmb_drive = QComboBox(header_card)
        self.cmb_drive.setStyleSheet(f"""
            QComboBox {{
                background-color: #0E1015;
                color: {THEME_COLORS['gold_primary']};
                border: 1px solid {THEME_COLORS['card_border_active']};
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 12px;
                min-width: 140px;
            }}
        """)
        drive_box.addWidget(self.cmb_drive)
        h_layout.addLayout(drive_box)

        main_layout.addWidget(header_card)

        # ۲. انتخاب محصولات (پکیج‌های ۵ گانه)
        lbl_sec1 = QLabel("📦 مرحله ۱: انتخاب نسخه یا پکیج‌های سپهریار جهت نصب روی این سیستم:", self)
        lbl_sec1.setStyleSheet(f"font-size: 12.5px; font-weight: bold; color: {THEME_COLORS['gold_hover']};")
        main_layout.addWidget(lbl_sec1)

        prods_layout = QHBoxLayout()
        prods_layout.setSpacing(10)

        for pid, cfg in PRODUCTS_CONFIG.items():
            card = ClientProductCard(
                product_id=pid,
                title=cfg["title"],
                symbol=cfg.get("icon_symbol", "📦"),
                exe_name=cfg.get("main_exe", ""),
                desc=cfg.get("description", ""),
                checked=(pid in self.selected_products),
                parent=self
            )
            card.clicked.connect(self._on_product_toggled)
            self.product_cards[pid] = card
            prods_layout.addWidget(card)

        main_layout.addLayout(prods_layout)

        # ۳. پیش‌نیازهای ضروری چاپ و فونت‌ها
        lbl_sec2 = QLabel("⚙️ مرحله ۲: پیش‌نیازهای ضروری چاپ و سیستم (به طور خودکار و سایلنت نصب خواهند شد):", self)
        lbl_sec2.setStyleSheet(f"font-size: 12.5px; font-weight: bold; color: {THEME_COLORS['gold_hover']};")
        main_layout.addWidget(lbl_sec2)

        prereq_layout = QHBoxLayout()
        prereq_layout.setSpacing(10)

        # استیمول سافت
        self.card_stimul = self._create_prereq_card(
            title="استیمول‌سافت (Stimulsoft Reports)",
            desc="موتور طراحی و چاپ قالب‌های مدرن و فاکتور رسمی (.mrt)",
            icon_name="database",
            badge_text="در انتظار..."
        )
        prereq_layout.addWidget(self.card_stimul)

        # کریستال ریپورتز
        self.card_crystal = self._create_prereq_card(
            title="کریستال ریپورتز (Crystal Reports)",
            desc="ران‌تایم CRRedist 10.5 نسخه ۳۲ و ۶۴ بیتی جهت چاپ اسناد و چک",
            icon_name="tools",
            badge_text="در انتظار..."
        )
        prereq_layout.addWidget(self.card_crystal)

        # فونت‌ها
        self.card_fonts = self._create_prereq_card(
            title="فونت‌های فارسی و رجیستری",
            desc="قلم‌های استاندارد Arad و IRANSans در پوشه Fonts و رجیستری ویندوز",
            icon_name="technician",
            badge_text="آماده ثبت"
        )
        prereq_layout.addWidget(self.card_fonts)

        main_layout.addLayout(prereq_layout)

        # ۴. کنسول لاگ و نوار پیشرفت
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #0E1015;
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {THEME_COLORS['gold_primary']};
                border-radius: 4px;
            }}
        """)
        main_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("جهت شروع، روی دکمه «شروع نصب کلاینت» کلیک فرمایید.", self)
        self.lbl_status.setStyleSheet(f"font-size: 12px; color: {THEME_COLORS['text_primary']}; font-weight: bold;")
        main_layout.addWidget(self.lbl_status)

        self.txt_log = QPlainTextEdit(self)
        self.txt_log.setReadOnly(True)
        self.txt_log.setFixedHeight(100)
        self.txt_log.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: #0A0C10;
                color: #A0A7B5;
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 8px;
                font-family: Consolas, "Courier New", monospace;
                font-size: 11px;
                padding: 6px;
            }}
        """)
        main_layout.addWidget(self.txt_log)

        # ۵. نوار دکمه اقدام
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        self.lbl_summary = QLabel(self)

        self.btn_start = QPushButton("🚀 شروع نصب کلاینت و پیش‌نیازها", self)
        self.btn_start.setProperty("class", "GoldPrimary")
        self.btn_start.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {THEME_COLORS['gold_primary']}, stop:1 {THEME_COLORS['gold_dark']});
                color: #0E1015;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {THEME_COLORS['gold_hover']};
            }}
            QPushButton:disabled {{
                background: #2C3140;
                color: #6E7585;
            }}
        """)
        self.btn_start.clicked.connect(self._start_client_installation)

        self._update_summary_label()
        bottom_bar.addWidget(self.lbl_summary, stretch=1)
        bottom_bar.addWidget(self.btn_start)

        main_layout.addLayout(bottom_bar)

    def _create_prereq_card(self, title: str, desc: str, icon_name: str, badge_text: str) -> QFrame:
        card = QFrame(self)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 8px;
                padding: 2px;
            }}
        """)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        icon_lbl = QLabel(card)
        icon_lbl.setPixmap(IconFactory.get_icon(icon_name, size=24, color_override=THEME_COLORS["gold_primary"]).pixmap(24, 24))
        lay.addWidget(icon_lbl)

        v_box = QVBoxLayout()
        v_box.setSpacing(2)

        t_lbl = QLabel(title, card)
        t_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME_COLORS['text_primary']};")
        v_box.addWidget(t_lbl)

        d_lbl = QLabel(desc, card)
        d_lbl.setStyleSheet(f"font-size: 10.5px; color: {THEME_COLORS['text_secondary']};")
        v_box.addWidget(d_lbl)
        lay.addLayout(v_box, stretch=1)

        b_lbl = QLabel(badge_text, card)
        b_lbl.setObjectName("badge")
        b_lbl.setStyleSheet(f"""
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 6px;
            background-color: {THEME_COLORS['card_hover']};
            color: {THEME_COLORS['gold_primary']};
            border: 1px solid {THEME_COLORS['card_border']};
        """)
        lay.addWidget(b_lbl)

        return card

    def _populate_drives(self):
        """اسکن درایوهای فعال و افزودن به کامبوباکس"""
        self.cmb_drive.clear()
        drives = scan_drives()
        default_idx = 0

        for idx, drv in enumerate(drives):
            text = f"درایو {drv.letter} ({drv.free_gb:.0f} GB آزاد)"
            self.cmb_drive.addItem(text, drv.letter)
            # ترجیح پیش‌فرض درایو غیر C در صورت وجود
            if drv.letter.upper() != "C:" and default_idx == 0:
                default_idx = idx

        if self.cmb_drive.count() > 0:
            self.cmb_drive.setCurrentIndex(default_idx)

    def _check_prerequisites_status(self):
        """بررسی سریع وضعیت فعلی نصب پیش‌نیازها روی سیستم"""
        prereq = PrerequisiteManager()
        
        # استیمول
        is_stimul = prereq.is_stimulsoft_installed()
        b_stimul = self.card_stimul.findChild(QLabel, "badge")
        if b_stimul:
            if is_stimul:
                b_stimul.setText("نصب شده ✓")
                b_stimul.setStyleSheet("color: #10B981; background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; border-radius: 6px; padding: 3px 8px;")
            else:
                b_stimul.setText("آماده نصب")

        # کریستال
        is_crystal = prereq.is_crystal_reports_installed()
        b_crystal = self.card_crystal.findChild(QLabel, "badge")
        if b_crystal:
            if is_crystal:
                b_crystal.setText("نصب شده ✓")
                b_crystal.setStyleSheet("color: #10B981; background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; border-radius: 6px; padding: 3px 8px;")
            else:
                b_crystal.setText("آماده نصب")

    def _on_product_toggled(self, product_id: str, checked: bool):
        if checked:
            self.selected_products.add(product_id)
        else:
            self.selected_products.discard(product_id)
        self._update_summary_label()

    def _update_summary_label(self):
        count = len(self.selected_products)
        if count == 0:
            self.lbl_summary.setText("⚠️ لطفاً حداقل یک نسخه از نرم‌افزار را انتخاب نمایید.")
            self.lbl_summary.setStyleSheet("color: #EF4444; font-size: 12px; font-weight: bold;")
            self.btn_start.setEnabled(False)
        else:
            titles = [PRODUCTS_CONFIG[p]["title"] for p in self.selected_products if p in PRODUCTS_CONFIG]
            self.lbl_summary.setText(f"نسخه‌های انتخابی ({count} مورد): {', '.join(titles)}")
            self.lbl_summary.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 12px; font-weight: bold;")
            self.btn_start.setEnabled(True)

    def _start_client_installation(self):
        if not self.selected_products:
            return

        target_drive = self.cmb_drive.currentData() or "D:"
        self.btn_start.setEnabled(False)
        self.cmb_drive.setEnabled(False)
        for card in self.product_cards.values():
            card.setEnabled(False)

        self.txt_log.clear()
        self.progress_bar.setValue(0)
        self.lbl_status.setText("در حال آماده‌سازی و شروع نصب...")

        self.worker = ClientInstallWorker(target_drive, list(self.selected_products))
        self.worker.sig_progress.connect(self._on_worker_progress)
        self.worker.sig_log.connect(self._on_worker_log)
        self.worker.sig_finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_progress(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(message)

    def _on_worker_log(self, text: str, level: str):
        color_map = {
            "INFO": "#A0A7B5",
            "SUCCESS": "#10B981",
            "WARN": "#F59E0B",
            "ERROR": "#EF4444",
        }
        color = color_map.get(level, "#A0A7B5")
        self.txt_log.appendHtml(f'<span style="color: {color};">[{level}] {text}</span>')
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    def _on_worker_finished(self, success: bool, message: str):
        self.btn_start.setEnabled(True)
        self.cmb_drive.setEnabled(True)
        for card in self.product_cards.values():
            card.setEnabled(True)
        self._check_prerequisites_status()

        if success:
            self.btn_start.setText("✅ نصب کلاینت مجدداً آماده است")
            QMessageBox.information(
                self,
                "نصب موفق کلاینت",
                "نصب پیش‌نیازهای گزارش‌ساز، فونت‌ها و کپی فایل‌های اجرایی با موفقیت انجام شد.\n"
                "میانبر برنامه‌ها روی دسکتاپ ایجاد گردید.",
                QMessageBox.Ok
            )
        else:
            self.btn_start.setText("تلاش مجدد")
            QMessageBox.warning(
                self,
                "خطا در نصب کلاینت",
                f"فرآیند نصب کلاینت با خطا مواجه شد:\n{message}",
                QMessageBox.Ok
            )
