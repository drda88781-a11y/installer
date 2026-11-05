# updater.py
"""
برنامه مستقل به‌روزرسانی دستی نرم‌افزار سپهریار (SEPEHRYAR Standalone Manual Updater)
کامپایل شونده به SepehryarUpdater.exe

روند عملیاتی:
Sepehryar.exe -> درخواست Update -> Sepehryar.exe بسته می‌شود -> SepehryarUpdater.exe اجرا می‌شود -> Backup -> Replace Files -> Process Data -> Verify -> Rollback در صورت خطا -> اجرای Sepehryar.exe
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# ایمن‌سازی یونیکد کنسول ویندوز
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

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from config.settings import (
    APP_ICON_ICO,
    APP_ICON_PNG,
    APP_LOGO_CIRCLE_PNG,
    THEME_COLORS,
)
from file_manager.update_engine import (
    InstalledAppInfo,
    ManualUpdatePipeline,
    UpdatePipelineResult,
    UpdateStageItem,
    UpdateStageStatus,
    UpdateValidationReport,
    compare_versions,
    detect_installed_applications,
    detect_sepehryar_data_dir,
    find_best_sql_instance,
    get_pe_file_version,
    validate_update_archive,
)
from ui.theme import get_application_stylesheet, load_application_fonts
from utils.icon_factory import IconFactory


class UpdateWorkerThread(QThread):
    """ترد پس‌زمینه برای اجرای بدون انجماد پایپ‌لاین آپدیت"""
    sig_progress = Signal(str, int, str)
    sig_stage_updated = Signal(int, object)
    sig_finished = Signal(object)

    def __init__(
        self,
        archive_path: Path,
        target_app_dir: Path,
        target_data_dir: Optional[Path] = None,
        sql_instance: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.archive_path = archive_path
        self.target_app_dir = target_app_dir
        self.target_data_dir = target_data_dir
        self.sql_instance = sql_instance
        self.pipeline: Optional[ManualUpdatePipeline] = None

    def run(self):
        self.pipeline = ManualUpdatePipeline(
            archive_path=self.archive_path,
            target_app_dir=self.target_app_dir,
            target_data_dir=self.target_data_dir,
            sql_instance=self.sql_instance,
            progress_callback=self._on_prog,
            stage_callback=self._on_stage,
        )
        res = self.pipeline.execute()
        self.sig_finished.emit(res)

    def _on_prog(self, stage_id: str, pct: int, text: str):
        self.sig_progress.emit(stage_id, pct, text)

    def _on_stage(self, idx: int, stage_item: UpdateStageItem):
        self.sig_stage_updated.emit(idx, stage_item)


class UpdaterWindow(QWidget):
    """پنجره مستقل کاربری سیستم به‌روزرسانی سپهریار"""

    def __init__(self, target_app_dir: Optional[Path] = None, zip_path: Optional[Path] = None, auto_start: bool = False):
        super().__init__()
        self.target_app_dir = target_app_dir
        self.zip_path = zip_path
        self.auto_start = auto_start
        self.validation_report: Optional[UpdateValidationReport] = None
        self.current_app_version = "0.0.0.0"
        self.installed_apps: list[InstalledAppInfo] = []
        self.stage_rows: list[dict] = []
        self.worker: Optional[UpdateWorkerThread] = None
        self.last_result: Optional[UpdatePipelineResult] = None
        self._pending_result = None

        self._setup_window()
        self._init_ui()
        self._load_detected_apps()

        if self.zip_path and self.zip_path.exists():
            self.txt_zip_path.setText(str(self.zip_path))

        if self.auto_start and self.can_start_update():
            # شروع خودکار پس از بارگذاری پنجره
            self._start_update()

    def _setup_window(self):
        self.setWindowTitle("سیستم مدیریت به‌روزرسانی نرم‌افزار سپهریار - Sepehryar Updater")
        self.setMinimumSize(980, 680)
        self.resize(1050, 720)
        if APP_ICON_PNG.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PNG)))
        elif APP_ICON_ICO.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_ICO)))

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(36, 28, 36, 28)
        main_layout.setSpacing(20)

        # ۱. سربرگ اصلی با لوگو و برندینگ
        header_card = QFrame(container)
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 12px;
                padding: 10px;
            }}
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(18, 14, 18, 14)
        h_layout.setSpacing(16)

        logo_lbl = QLabel(header_card)
        logo_lbl.setFixedSize(54, 54)
        if APP_LOGO_CIRCLE_PNG.exists():
            pix = QPixmap(str(APP_LOGO_CIRCLE_PNG)).scaled(54, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        else:
            logo_lbl.setPixmap(IconFactory.get_icon("database", size=40).pixmap(40, 40))
        h_layout.addWidget(logo_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(4)
        lbl_head = QLabel("سامانه رسمی و مستقل به‌روزرسانی دستی سپهریار", header_card)
        lbl_head.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 19px; font-weight: bold;")
        lbl_sub = QLabel("ارتقای امن و ساختاریافته فایل‌های نرم‌افزار و پایگاه داده با قابلیت بازگشت خودکار (Rollback)", header_card)
        lbl_sub.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12.5px;")
        title_vbox.addWidget(lbl_head)
        title_vbox.addWidget(lbl_sub)
        h_layout.addLayout(title_vbox, stretch=1)
        main_layout.addWidget(header_card)

        # ۲. کارت انتخاب برنامه نصب‌شده
        app_card = QFrame(container)
        app_card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 10px;
            }}
        """)
        app_card_layout = QVBoxLayout(app_card)
        app_card_layout.setContentsMargins(18, 16, 18, 16)
        app_card_layout.setSpacing(12)

        lbl_app_title = QLabel("۱. نرم‌افزار نصب‌شده بر روی سیستم:", app_card)
        lbl_app_title.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 13.5px; font-weight: bold;")
        app_card_layout.addWidget(lbl_app_title)

        app_select_layout = QHBoxLayout()
        app_select_layout.setSpacing(10)

        self.cmb_apps = QComboBox(app_card)
        self.cmb_apps.setStyleSheet(f"""
            QComboBox {{
                background-color: #0E1015;
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #141720;
                color: #FFFFFF;
                selection-background-color: {THEME_COLORS['gold_muted']};
                selection-color: #FFFFFF;
            }}
        """)
        self.cmb_apps.currentIndexChanged.connect(self._on_app_selected)
        app_select_layout.addWidget(self.cmb_apps, stretch=1)

        self.btn_browse_app = QPushButton("تغییر پوشه نصب...", app_card)
        self.btn_browse_app.setProperty("class", "GoldSecondary")
        self.btn_browse_app.setIcon(IconFactory.get_icon("folder", size=16))
        self.btn_browse_app.setFixedHeight(36)
        self.btn_browse_app.clicked.connect(self._browse_app_folder)
        app_select_layout.addWidget(self.btn_browse_app)
        app_card_layout.addLayout(app_select_layout)

        # جزئیات نرم‌افزار انتخابی
        self.lbl_app_details = QLabel(app_card)
        self.lbl_app_details.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px; line-height: 1.4;")
        self.lbl_app_details.setWordWrap(True)
        app_card_layout.addWidget(self.lbl_app_details)

        main_layout.addWidget(app_card)

        # ۳. کارت انتخاب فایل ZIP آپدیت و مشخصات نسخه
        zip_card = QFrame(container)
        zip_card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 10px;
            }}
        """)
        zip_layout = QVBoxLayout(zip_card)
        zip_layout.setContentsMargins(18, 16, 18, 16)
        zip_layout.setSpacing(12)

        lbl_zip_title = QLabel("۲. فایل فشرده بسته به‌روزرسانی (Update.zip):", zip_card)
        lbl_zip_title.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 13.5px; font-weight: bold;")
        zip_layout.addWidget(lbl_zip_title)

        zip_input_layout = QHBoxLayout()
        zip_input_layout.setSpacing(10)

        self.txt_zip_path = QLineEdit(zip_card)
        self.txt_zip_path.setPlaceholderText("مسیر فایل ZIP بسته آپدیت را انتخاب نمایید...")
        self.txt_zip_path.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0E1015;
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12.5px;
            }}
            QLineEdit:focus {{
                border-color: {THEME_COLORS['gold_primary']};
            }}
        """)
        self.txt_zip_path.textChanged.connect(self._on_zip_path_changed)
        zip_input_layout.addWidget(self.txt_zip_path, stretch=1)

        self.btn_browse_zip = QPushButton("انتخاب فایل ZIP...", zip_card)
        self.btn_browse_zip.setProperty("class", "GoldSecondary")
        self.btn_browse_zip.setIcon(IconFactory.get_icon("archive", size=16))
        self.btn_browse_zip.setFixedHeight(36)
        self.btn_browse_zip.clicked.connect(self._browse_zip_file)
        zip_input_layout.addWidget(self.btn_browse_zip)
        zip_layout.addLayout(zip_input_layout)

        # ۴ نشانگر وضعیت اعتبارسنجی (Badges) مطابق بخش ۱۴ پرامپت
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(12)

        self.badge_valid = self._create_status_badge("فایل معتبر")
        self.badge_version = self._create_status_badge("نسخه جدیدتر")
        self.badge_files = self._create_status_badge("Files موجود")
        self.badge_data = self._create_status_badge("Data موجود")

        badges_layout.addWidget(self.badge_valid)
        badges_layout.addWidget(self.badge_version)
        badges_layout.addWidget(self.badge_files)
        badges_layout.addWidget(self.badge_data)
        zip_layout.addLayout(badges_layout)

        self.lbl_zip_status_msg = QLabel("لطفاً فایل ZIP معتبر را انتخاب فرمایید.", zip_card)
        self.lbl_zip_status_msg.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px;")
        zip_layout.addWidget(self.lbl_zip_status_msg)

        main_layout.addWidget(zip_card)

        # ۴. خلاصه اقدامات و تضمین تراکنش
        summary_card = QFrame(container)
        summary_card.setStyleSheet(f"""
            QFrame {{
                background-color: #12141D;
                border: 1px solid #242938;
                border-radius: 10px;
                padding: 6px;
            }}
        """)
        sum_layout = QHBoxLayout(summary_card)
        sum_layout.setContentsMargins(16, 12, 16, 12)
        sum_layout.setSpacing(24)

        sum_items = [
            ("📁", "Files", "بروزرسانی فایل‌های برنامه"),
            ("🗄️", "Data", "بروزرسانی دیتابیس"),
            ("💾", "Backup", "پشتیبان‌گیری فعال"),
            ("🛡️", "Rollback", "بازگشت خودکار فعال"),
        ]
        for icon, title, desc in sum_items:
            item_box = QHBoxLayout()
            item_box.setSpacing(8)
            lbl_ic = QLabel(icon, summary_card)
            lbl_ic.setStyleSheet("font-size: 18px;")
            v_t = QVBoxLayout()
            v_t.setSpacing(1)
            t_lbl = QLabel(title, summary_card)
            t_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_light']}; font-size: 12.5px; font-weight: bold;")
            d_lbl = QLabel(desc, summary_card)
            d_lbl.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11px;")
            v_t.addWidget(t_lbl)
            v_t.addWidget(d_lbl)
            item_box.addWidget(lbl_ic)
            item_box.addLayout(v_t)
            sum_layout.addLayout(item_box)

        main_layout.addWidget(summary_card)

        # ۵. دکمه شروع به‌روزرسانی
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("شروع به‌روزرسانی دستی", container)
        self.btn_start.setProperty("class", "GoldPrimary")
        self.btn_start.setFixedHeight(46)
        self.btn_start.setIcon(IconFactory.get_icon("play", size=18, color_override="#0E1015"))
        self.btn_start.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {THEME_COLORS['gold_light']}, stop:0.5 {THEME_COLORS['gold_primary']}, stop:1 {THEME_COLORS['gold_dark']});
                color: #0E1015;
                font-size: 15px;
                font-weight: bold;
                border-radius: 8px;
                padding: 0 28px;
            }}
            QPushButton:hover {{
                background: {THEME_COLORS['gold_hover']};
            }}
            QPushButton:disabled {{
                background: #252834;
                color: #555866;
            }}
        """)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._start_update)
        btn_layout.addWidget(self.btn_start, stretch=1)
        main_layout.addLayout(btn_layout)

        # ۶. پیشرفت و مراحل واقعی ۱۱ گانه
        self.progress_card = QFrame(container)
        self.progress_card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 10px;
                padding: 8px;
            }}
        """)
        prog_layout = QVBoxLayout(self.progress_card)
        prog_layout.setContentsMargins(16, 14, 16, 14)
        prog_layout.setSpacing(12)

        lbl_stages_title = QLabel("مراحل واقعی اجرای به‌روزرسانی:", self.progress_card)
        lbl_stages_title.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 13.5px; font-weight: bold;")
        prog_layout.addWidget(lbl_stages_title)

        self.bar_progress = QProgressBar(self.progress_card)
        self.bar_progress.setFixedHeight(12)
        self.bar_progress.setValue(0)
        self.bar_progress.setTextVisible(False)
        self.bar_progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #0E1015;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {THEME_COLORS['gold_primary']};
                border-radius: 5px;
            }}
        """)
        prog_layout.addWidget(self.bar_progress)

        self.lbl_active_op = QLabel("در انتظار شروع عملیات...", self.progress_card)
        self.lbl_active_op.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12.5px;")
        prog_layout.addWidget(self.lbl_active_op)

        # فهرست ردیف‌های ۱۱ مرحله
        self.stages_container = QWidget(self.progress_card)
        stages_vbox = QVBoxLayout(self.stages_container)
        stages_vbox.setContentsMargins(0, 4, 0, 0)
        stages_vbox.setSpacing(6)

        for s_idx, (s_id, s_title) in enumerate(ManualUpdatePipeline.STAGES_DEF):
            row = QHBoxLayout()
            row.setSpacing(10)

            lbl_ico = QLabel("⚪", self.stages_container)
            lbl_ico.setFixedWidth(20)

            lbl_t = QLabel(f"{s_idx + 1}. {s_title}", self.stages_container)
            lbl_t.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12.5px;")

            lbl_msg = QLabel("", self.stages_container)
            lbl_msg.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11.5px;")
            lbl_msg.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            row.addWidget(lbl_ico)
            row.addWidget(lbl_t)
            row.addWidget(lbl_msg, stretch=1)
            stages_vbox.addLayout(row)

            self.stage_rows.append({
                "icon": lbl_ico,
                "title": lbl_t,
                "msg": lbl_msg,
            })

        prog_layout.addWidget(self.stages_container)
        main_layout.addWidget(self.progress_card)

        # ۷. دکمه‌های پس از اتمام (اجرای برنامه / مشاهده لاگ / خروج)
        self.bottom_actions = QHBoxLayout()
        self.btn_launch_app = QPushButton("اجرای نرم‌افزار سپهریار", container)
        self.btn_launch_app.setProperty("class", "GoldPrimary")
        self.btn_launch_app.setFixedHeight(40)
        self.btn_launch_app.setVisible(False)
        self.btn_launch_app.clicked.connect(self._launch_updated_app)
        self.bottom_actions.addWidget(self.btn_launch_app)

        self.btn_view_log = QPushButton("مشاهده لاگ کامل بروزرسانی", container)
        self.btn_view_log.setProperty("class", "GoldSecondary")
        self.btn_view_log.setFixedHeight(40)
        self.btn_view_log.setVisible(False)
        self.btn_view_log.clicked.connect(self._view_log_file)
        self.bottom_actions.addWidget(self.btn_view_log)

        self.bottom_actions.addStretch()

        self.btn_exit = QPushButton("بستن", container)
        self.btn_exit.setProperty("class", "GoldSecondary")
        self.btn_exit.setFixedHeight(40)
        self.btn_exit.clicked.connect(self.close)
        self.bottom_actions.addWidget(self.btn_exit)

        main_layout.addLayout(self.bottom_actions)

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def _create_status_badge(self, text: str) -> QLabel:
        lbl = QLabel(f"⚪ {text}", self)
        lbl.setStyleSheet(f"""
            QLabel {{
                background-color: #141720;
                color: {THEME_COLORS['text_muted']};
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }}
        """)
        lbl.setAlignment(Qt.AlignCenter)
        return lbl

    def _update_badge(self, badge: QLabel, is_success: Optional[bool], text: str):
        if is_success is True:
            badge.setText(f"✓ {text}")
            badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {THEME_COLORS['success_bg']};
                    color: {THEME_COLORS['success']};
                    border: 1px solid {THEME_COLORS['success']};
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: bold;
                }}
            """)
        elif is_success is False:
            badge.setText(f"✕ {text}")
            badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {THEME_COLORS['error_bg']};
                    color: {THEME_COLORS['error']};
                    border: 1px solid {THEME_COLORS['error']};
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: bold;
                }}
            """)
        else:
            badge.setText(f"⚪ {text}")
            badge.setStyleSheet(f"""
                QLabel {{
                    background-color: #141720;
                    color: {THEME_COLORS['text_muted']};
                    border: 1px solid {THEME_COLORS['border_medium']};
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                }}
            """)

    def _load_detected_apps(self):
        self.cmb_apps.clear()
        self.installed_apps = detect_installed_applications()

        if not self.installed_apps:
            # در صورتی که برنامه‌ای خودکار یافت نشد، مسیر پیش‌فرض بررسی شود
            default_p = Path(r"D:\SEPEHRYAR\SEPEHRYAR.TaxGov")
            if default_p.exists():
                main_exe = default_p / "SepandYar_TaxGov.exe"
                self.installed_apps.append(InstalledAppInfo(
                    product_id="SEPEHRYAR.TaxGov",
                    title="سپهریار - سامانه مودیان",
                    install_dir=default_p,
                    main_exe_path=main_exe,
                    version=get_pe_file_version(main_exe),
                    data_dir=detect_sepehryar_data_dir(default_p),
                ))

        for app in self.installed_apps:
            display_str = f"{app.title} (نسخه: {app.version}) - {app.install_dir}"
            self.cmb_apps.addItem(display_str, userData=app)

        if self.target_app_dir:
            # انتخاب برنامه متناظر با آرگومان ورودی
            for i in range(self.cmb_apps.count()):
                app_obj = self.cmb_apps.itemData(i)
                if app_obj and app_obj.install_dir.resolve() == self.target_app_dir.resolve():
                    self.cmb_apps.setCurrentIndex(i)
                    break

        self._refresh_selected_app_info()

    def _refresh_selected_app_info(self):
        app_obj = self.cmb_apps.currentData()
        if app_obj:
            self.target_app_dir = app_obj.install_dir
            self.current_app_version = app_obj.version
            data_dir = app_obj.data_dir or detect_sepehryar_data_dir(self.target_app_dir)
            sql_inst = find_best_sql_instance() or "SEPEHRYAR2019"
            detail_text = (
                f"📁 پوشه نصب: {self.target_app_dir}\n"
                f"🏷️ فایل اجرایی: {app_obj.main_exe_path.name} | نسخه فعلی: {self.current_app_version}\n"
                f"🗄️ پوشه داده‌ها: {data_dir} | اینستنس پایگاه داده: {sql_inst}"
            )
            self.lbl_app_details.setText(detail_text)
        else:
            self.lbl_app_details.setText("هیچ برنامه‌ای انتخاب نشده است. از دکمه تغییر پوشه نصب استفاده نمایید.")

        self._revalidate()

    def _on_app_selected(self, idx: int):
        self._refresh_selected_app_info()

    def _browse_app_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "انتخاب پوشه نصب برنامه سپهریار",
            str(Path.home()),
        )
        if folder:
            p_folder = Path(folder)
            exes = list(p_folder.glob("*.exe"))
            main_exe = exes[0] if exes else p_folder / "Sepehryar.exe"
            ver = get_pe_file_version(main_exe) if exes else "0.0.0.0"
            custom_app = InstalledAppInfo(
                product_id="CUSTOM",
                title=f"برنامه انتخابی ({p_folder.name})",
                install_dir=p_folder,
                main_exe_path=main_exe,
                version=ver,
                data_dir=detect_sepehryar_data_dir(p_folder),
            )
            self.installed_apps.insert(0, custom_app)
            self.cmb_apps.insertItem(0, f"{custom_app.title} (نسخه: {ver}) - {p_folder}", userData=custom_app)
            self.cmb_apps.setCurrentIndex(0)

    def _browse_zip_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "انتخاب بسته یا اسکریپت به‌روزرسانی سپهریار",
            str(Path.home()),
            "کلیه بسته‌های معتبر (*.zip *.rar *.7z *.sql);;فایل‌های فشرده (*.zip *.rar *.7z);;اسکریپت‌های SQL (*.sql);;کلیه فایل‌ها (*.*)"
        )
        if filepath:
            self.txt_zip_path.setText(filepath)

    def _on_zip_path_changed(self, text: str):
        clean = text.strip().strip('"').strip("'")
        if clean:
            self.zip_path = Path(clean)
        else:
            self.zip_path = None
        self._revalidate()

    def _revalidate(self):
        self.validation_report = None
        if not self.zip_path or not self.zip_path.exists():
            self._update_badge(self.badge_valid, None, "فایل معتبر")
            self._update_badge(self.badge_version, None, "نسخه جدیدتر")
            self._update_badge(self.badge_files, None, "Files موجود")
            self._update_badge(self.badge_data, None, "Data موجود")
            self.lbl_zip_status_msg.setText("لطفاً فایل ZIP معتبر را انتخاب فرمایید.")
            self.lbl_zip_status_msg.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px;")
            self.btn_start.setEnabled(False)
            return

        report = validate_update_archive(self.zip_path)
        self.validation_report = report

        if report.is_valid and self.target_app_dir:
            from file_manager.update_package import UpdatePackage
            from config.settings import PRODUCTS_CONFIG
            with UpdatePackage(self.zip_path) as package:
                matches = [product for product in package.manifest["products"]
                           if self.target_app_dir.name == PRODUCTS_CONFIG[product]["folder_name"]]
                if not matches and len(package.manifest["products"]) == 1:
                    product = package.manifest["products"][0]
                    if (self.target_app_dir / PRODUCTS_CONFIG[product]["main_exe"]).is_file():
                        matches = [product]
                if len(matches) != 1:
                    report.is_valid = False
                    report.error_message = "محصول بسته با پوشه نصب انتخاب‌شده مطابقت ندارد."
                else:
                    from file_manager.transactional_update import installed_version
                    self.current_app_version = installed_version(self.target_app_dir, matches[0])

        if not report.is_valid:
            self._update_badge(self.badge_valid, False, "فایل معتبر")
            self._update_badge(self.badge_version, None, "نسخه جدیدتر")
            self._update_badge(self.badge_files, report.has_files_folder, "Files موجود")
            self._update_badge(self.badge_data, report.has_data_folder, "Data موجود")
            self.lbl_zip_status_msg.setText(f"✕ {report.error_message}")
            self.lbl_zip_status_msg.setStyleSheet(f"color: {THEME_COLORS['error']}; font-size: 12px; font-weight: bold;")
            self.btn_start.setEnabled(False)
            return

        # بررسی نسخه
        cmp_res = compare_versions(self.current_app_version, report.package_version)
        is_newer = (cmp_res > 0)
        is_same = (cmp_res == 0)

        self._update_badge(self.badge_valid, True, "فایل معتبر")
        self._update_badge(self.badge_files, True, f"Files موجود ({report.files_count})")
        self._update_badge(self.badge_data, report.has_data_folder, "Data موجود" if report.has_data_folder else "بدون Data")

        if is_newer:
            self._update_badge(self.badge_version, True, f"نسخه جدیدتر ({report.package_version})")
            self.lbl_zip_status_msg.setText(f"✓ نسخه جدید آماده نصب است: {report.package_version} (نسخه فعلی: {self.current_app_version})")
            self.lbl_zip_status_msg.setStyleSheet(f"color: {THEME_COLORS['success']}; font-size: 12.5px; font-weight: bold;")
            self.btn_start.setEnabled(True)
        elif is_same:
            self._update_badge(self.badge_version, True, f"همان نسخه ({report.package_version})")
            self.lbl_zip_status_msg.setText("این نسخه نصب شده است؛ بسته جدیدتری انتخاب کنید.")
            self.lbl_zip_status_msg.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 12px; font-weight: bold;")
            self.btn_start.setEnabled(False)
        else:
            self._update_badge(self.badge_version, True, f"جایگزینی ({report.package_version})")
            self.lbl_zip_status_msg.setText("بسته از نسخه فعلی قدیمی‌تر است و قابل اعمال نیست.")
            self.lbl_zip_status_msg.setStyleSheet(f"color: {THEME_COLORS['warning']}; font-size: 12px;")
            self.btn_start.setEnabled(False)

    def can_start_update(self) -> bool:
        return self.btn_start.isEnabled()

    def _start_update(self):
        if not self.zip_path or not self.target_app_dir:
            return

        self._revalidate()
        if not self.can_start_update():
            return
        if not self.auto_start:
            report = self.validation_report
            message = (f"پوشه محصول: {self.target_app_dir}\n"
                       f"نسخه فعلی: {self.current_app_version} → نسخه جدید: {report.package_version}\n"
                       f"فایل‌ها: {report.files_count}\n"
                       f"دیتابیس‌ها: {'، '.join(report.database_names) or 'ندارد'}\n\n"
                       "برنامه بسته می‌شود و پیش از تغییر، بک‌آپ تأییدشده تهیه خواهد شد.")
            if QMessageBox.question(self, "خلاصه به‌روزرسانی", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return

        self.btn_start.setEnabled(False)
        self.btn_browse_app.setEnabled(False)
        self.btn_browse_zip.setEnabled(False)
        self.txt_zip_path.setEnabled(False)
        self.cmb_apps.setEnabled(False)

        # ریست کردن نشانگرهای ۱۱ مرحله
        for r in self.stage_rows:
            r["icon"].setText("⚪")
            r["title"].setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12.5px;")
            r["msg"].setText("")

        data_dir = detect_sepehryar_data_dir(self.target_app_dir)
        sql_inst = find_best_sql_instance()

        self.worker = UpdateWorkerThread(
            archive_path=self.zip_path,
            target_app_dir=self.target_app_dir,
            target_data_dir=data_dir,
            sql_instance=sql_inst,
            parent=self,
        )
        self.worker.sig_progress.connect(self._on_worker_progress)
        self.worker.sig_stage_updated.connect(self._on_stage_updated)
        self.worker.sig_finished.connect(self._store_worker_result)
        self.worker.finished.connect(self._worker_thread_finished)
        self.worker.start()

    def _store_worker_result(self, result):
        self._pending_result = result

    def _worker_thread_finished(self):
        self.worker.wait()
        if self._pending_result is not None:
            result, self._pending_result = self._pending_result, None
            self._on_worker_finished(result)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "به‌روزرسانی در حال اجرا", "برای حفظ امکان بازیابی، تا پایان آپدیت یا بازگردانی صبر کنید.")
            event.ignore()
        else:
            event.accept()

    def _on_worker_progress(self, stage_id: str, pct: int, text: str):
        self.bar_progress.setValue(pct)
        self.lbl_active_op.setText(text)

    def _on_stage_updated(self, idx: int, stage_item: UpdateStageItem):
        if idx >= len(self.stage_rows):
            return
        row = self.stage_rows[idx]
        st = stage_item.status

        if st == UpdateStageStatus.RUNNING:
            row["icon"].setText("⏳")
            row["title"].setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-weight: bold; font-size: 12.5px;")
            row["msg"].setText("در حال انجام...")
            row["msg"].setStyleSheet(f"color: {THEME_COLORS['gold_light']}; font-size: 11.5px;")
        elif st == UpdateStageStatus.SUCCESS:
            row["icon"].setText("✓")
            row["icon"].setStyleSheet(f"color: {THEME_COLORS['success']}; font-weight: bold;")
            row["title"].setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 12.5px;")
            dur_str = f"({stage_item.duration_seconds} ثانیه)" if stage_item.duration_seconds > 0 else ""
            row["msg"].setText(f"{stage_item.message} {dur_str}")
            row["msg"].setStyleSheet(f"color: {THEME_COLORS['success']}; font-size: 11.5px;")
        elif st == UpdateStageStatus.FAILED:
            row["icon"].setText("✕")
            row["icon"].setStyleSheet(f"color: {THEME_COLORS['error']}; font-weight: bold;")
            row["title"].setStyleSheet(f"color: {THEME_COLORS['error']}; font-weight: bold; font-size: 12.5px;")
            row["msg"].setText(stage_item.message)
            row["msg"].setStyleSheet(f"color: {THEME_COLORS['error']}; font-size: 11.5px;")
        elif st == UpdateStageStatus.SKIPPED:
            row["icon"].setText("—")
            row["title"].setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12.5px;")
            row["msg"].setText(stage_item.message or "صرف‌نظر شد")
            row["msg"].setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11.5px;")

    def _on_worker_finished(self, result: UpdatePipelineResult):
        self.last_result = result
        self.bar_progress.setValue(100 if result.success else 0)

        if result.success:
            self.lbl_active_op.setText("✓ عملیات به‌روزرسانی با موفقیت کامل انجام شد.")
            self.lbl_active_op.setStyleSheet(f"color: {THEME_COLORS['success']}; font-size: 13.5px; font-weight: bold;")
            self.btn_launch_app.setVisible(True)
            self.btn_view_log.setVisible(True)
            QMessageBox.information(
                self,
                "به‌روزرسانی موفق",
                f"نرم‌افزار سپهریار با موفقیت به نسخه {result.new_version} ارتقا یافت.\nتعداد {result.files_updated_count} فایل جایگزین گردید.",
            )
        else:
            self.lbl_active_op.setText(f"✕ {result.message}")
            self.lbl_active_op.setStyleSheet(f"color: {THEME_COLORS['error']}; font-size: 13px; font-weight: bold;")
            self.btn_view_log.setVisible(True)
            self.btn_start.setEnabled(True)
            QMessageBox.critical(
                self,
                "خطا در بروزرسانی",
                f"{result.message}\n\nبرای جزئیات بیشتر به فایل لاگ مراجعه فرمایید.",
            )

        self.btn_browse_app.setEnabled(True)
        self.btn_browse_zip.setEnabled(True)
        self.txt_zip_path.setEnabled(True)
        self.cmb_apps.setEnabled(True)

    def _launch_updated_app(self):
        if not self.target_app_dir:
            return
        exes = list(self.target_app_dir.glob("*.exe"))
        if not exes:
            return
        target_exe = exes[0]
        # اولویت با فایل اصلی
        preferred = ["Hesabdari.exe", "SepandResturan.exe", "SepandYar_TaxGov.exe", "ClientSepand.exe"]
        for p in preferred:
            cand = self.target_app_dir / p
            if cand.exists():
                target_exe = cand
                break
        try:
            subprocess.Popen([str(target_exe)], cwd=str(self.target_app_dir))
            self.close()
        except Exception as ex:
            QMessageBox.warning(self, "خطا در اجرا", f"امکان اجرای برنامه وجود ندارد: {ex}")

    def _view_log_file(self):
        if self.last_result and self.last_result.log_file_path and self.last_result.log_file_path.exists():
            os.system(f'notepad.exe "{self.last_result.log_file_path}"')
        else:
            QMessageBox.information(self, "فایل لاگ", "فایل لاگ در دسترس نیست.")


def main():
    parser = argparse.ArgumentParser(description="SEPEHRYAR Standalone Manual Updater")
    parser.add_argument("--app-dir", type=str, default="", help="Path to installed application directory")
    parser.add_argument("--zip", type=str, default="", help="Path to update ZIP archive")
    parser.add_argument("--auto", action="store_true", help="Automatically start update if valid")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("SepehryarUpdater")
    app.setApplicationDisplayName("مدیریت به‌روزرسانی سپهریار")
    app.setLayoutDirection(Qt.RightToLeft)

    font_family = load_application_fonts()
    app_font = QFont(font_family, 10)
    app_font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(app_font)
    app.setStyleSheet(get_application_stylesheet(font_family))

    target_app_dir = Path(args.app_dir) if args.app_dir else None
    zip_path = Path(args.zip) if args.zip else None

    window = UpdaterWindow(
        target_app_dir=target_app_dir,
        zip_path=zip_path,
        auto_start=args.auto,
    )
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
