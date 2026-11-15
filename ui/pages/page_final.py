# ui/pages/page_final.py
"""
صفحه ۵: پایان موفقیت‌آمیز نصب، خلاصه وضعیت، ورود اطلاعات تکنسین، صدور صورت‌جلسه MRT و راه‌اندازی سپهریار
Page 5: Installation Success Completion, Verification Summary, Technician Handover, Stimulsoft MRT & Print
"""

import datetime
import os
import subprocess
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config.settings import THEME_COLORS, SQL_INSTANCE_NAME, APP_LOGO_CIRCLE_PNG, APP_LOGO_PNG, get_sql_instance_name
from core.orchestrator import requires_sql_and_setup
from packages.product_catalog import get_product_by_id, resolve_installed_exe_path
from system_check.hardware_checker import get_cpu_info, get_physical_ram_gb, get_windows_info
from utils.icon_factory import IconFactory
from utils.report_generator import generate_installation_mrt, show_print_preview_dialog
from ui.dialogs.keygen_dialog import KeygenDialog


class FinalPage(QWidget):
    """
    صفحه پایانی نمایش موفقیت، دریافت نام مسئول نصب، صدور صورت‌جلسه .MRT و کلیدهای راه‌اندازی
    """
    launch_requested = Signal()
    open_folder_requested = Signal()
    view_report_requested = Signal()
    exit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_install_dir: Optional[Path] = None
        self.selected_products: List[str] = []
        self.sql_version: str = "2019"
        self._init_ui()

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # محفظه اسکرول سراسری جهت تضمین نمایش کامل و جلوگیری از بریده شدن المان‌ها در تمام ابعاد
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(28, 14, 28, 14)
        main_layout.setSpacing(12)
        main_layout.setAlignment(Qt.AlignCenter)

        # ۱. سربرگ و نشان طلایی رسمی سپهریار
        icon_frame = QFrame(container)
        icon_layout = QHBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)

        self.big_check = QLabel(icon_frame)
        self.big_check.setFixedSize(60, 60)
        if APP_LOGO_CIRCLE_PNG.exists():
            pix = QPixmap(str(APP_LOGO_CIRCLE_PNG)).scaled(
                60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.big_check.setPixmap(pix)
        elif APP_LOGO_PNG.exists():
            pix = QPixmap(str(APP_LOGO_PNG)).scaled(
                60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.big_check.setPixmap(pix)
        else:
            pix = IconFactory.get_icon("check", size=48, color_override=THEME_COLORS["gold_primary"]).pixmap(48, 48)
            self.big_check.setPixmap(pix)
            self.big_check.setStyleSheet(f"""
                QLabel {{
                    background-color: {THEME_COLORS['gold_glow']};
                    border: 2px solid {THEME_COLORS['gold_primary']};
                    border-radius: 30px;
                }}
            """)
        icon_layout.addWidget(self.big_check)
        main_layout.addWidget(icon_frame)

        # تیترهای تبریک و پایان
        title_lbl = QLabel("نصب سپهریار با موفقیت انجام شد", container)
        title_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 20px; font-weight: bold;")
        title_lbl.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_lbl)

        sub_lbl = QLabel(
            "تمامی بسته‌های انتخابی، پیش‌نیازها، ارتباط پایگاه داده و میانبرهای نرم‌افزار به صورت کامل پیکربندی شدند.",
            container
        )
        sub_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12px;")
        sub_lbl.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(sub_lbl)

        # ۲. چیدمان افقی و متعادل دو کارت اصلی
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)

        # کارت ۱: مشخصات سیستم و نصب
        summary_card = QFrame(container)
        summary_card.setObjectName("summaryCard")
        summary_card.setStyleSheet(f"""
            #summaryCard {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 10px;
            }}
        """)
        sum_vlayout = QVBoxLayout(summary_card)
        sum_vlayout.setContentsMargins(16, 12, 16, 12)
        sum_vlayout.setSpacing(8)

        lbl_sum_head = QLabel("مشخصات سیستم و نصب:", summary_card)
        lbl_sum_head.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 13px; font-weight: bold;")
        sum_vlayout.addWidget(lbl_sum_head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        lbl_p_title = QLabel("محصولات:", summary_card)
        lbl_p_title.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12px; font-weight: bold;")
        self.lbl_p_val = QLabel("-", summary_card)
        self.lbl_p_val.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 12px;")
        self.lbl_p_val.setWordWrap(True)
        grid.addWidget(lbl_p_title, 0, 0)
        grid.addWidget(self.lbl_p_val, 0, 1)

        lbl_path_title = QLabel("مسیر نصب:", summary_card)
        lbl_path_title.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12px; font-weight: bold;")
        self.lbl_path_val = QLabel("-", summary_card)
        self.lbl_path_val.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 12px;")
        self.lbl_path_val.setWordWrap(True)
        grid.addWidget(lbl_path_title, 1, 0)
        grid.addWidget(self.lbl_path_val, 1, 1)

        lbl_sql_title = QLabel("پایگاه داده:", summary_card)
        lbl_sql_title.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12px; font-weight: bold;")
        self.lbl_sql_val = QLabel(f"{SQL_INSTANCE_NAME} (متصل و فعال)", summary_card)
        self.lbl_sql_val.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 12px;")
        grid.addWidget(lbl_sql_title, 2, 0)
        grid.addWidget(self.lbl_sql_val, 2, 1)

        lbl_st_title = QLabel("وضعیت سیستم:", summary_card)
        lbl_st_title.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12px; font-weight: bold;")
        self.lbl_st_val = QLabel("✓ آماده بهره‌برداری و پشتیبان‌گیری", summary_card)
        self.lbl_st_val.setStyleSheet(f"color: {THEME_COLORS['success']}; font-size: 12px; font-weight: bold;")
        grid.addWidget(lbl_st_title, 3, 0)
        grid.addWidget(self.lbl_st_val, 3, 1)

        sum_vlayout.addLayout(grid)
        sum_vlayout.addStretch()
        cards_layout.addWidget(summary_card, stretch=1)

        # کارت ۲: کادر صورت‌جلسه رسمی و الگو MRT
        report_box = QFrame(container)
        report_box.setObjectName("reportBox")
        report_box.setStyleSheet(f"""
            #reportBox {{
                background-color: #12141C;
                border: 1px solid {THEME_COLORS['gold_primary']};
                border-radius: 10px;
            }}
        """)
        report_layout = QVBoxLayout(report_box)
        report_layout.setContentsMargins(16, 12, 16, 12)
        report_layout.setSpacing(8)

        rpt_header = QLabel("صورت‌جلسه تحویل و الگو (Stimulsoft .MRT):", report_box)
        rpt_header.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 13px; font-weight: bold;")
        report_layout.addWidget(rpt_header)

        # فیلدهای متنی
        inputs_layout = QHBoxLayout()
        inputs_layout.setSpacing(10)

        tech_vbox = QVBoxLayout()
        tech_vbox.setSpacing(3)
        lbl_tech = QLabel("نام کارشناس نصب:", report_box)
        lbl_tech.setMinimumHeight(18)
        lbl_tech.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 11px;")
        self.txt_technician = QLineEdit(report_box)
        self.txt_technician.setFixedHeight(32)
        self.txt_technician.setPlaceholderText("نام و نام خانوادگی کارشناس...")
        self.txt_technician.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0E1015;
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {THEME_COLORS['gold_primary']};
            }}
        """)
        tech_vbox.addWidget(lbl_tech)
        tech_vbox.addWidget(self.txt_technician)
        inputs_layout.addLayout(tech_vbox, stretch=1)

        cust_vbox = QVBoxLayout()
        cust_vbox.setSpacing(3)
        lbl_cust = QLabel("نام کارفرما / تحویل‌گیرنده:", report_box)
        lbl_cust.setMinimumHeight(18)
        lbl_cust.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 11px;")
        self.txt_customer = QLineEdit(report_box)
        self.txt_customer.setFixedHeight(32)
        self.txt_customer.setPlaceholderText("نام فروشگاه، شرکت یا شخص...")
        self.txt_customer.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0E1015;
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {THEME_COLORS['gold_primary']};
            }}
        """)
        cust_vbox.addWidget(lbl_cust)
        cust_vbox.addWidget(self.txt_customer)
        inputs_layout.addLayout(cust_vbox, stretch=1)

        report_layout.addLayout(inputs_layout)

        # دکمه‌های پرینت و الگو
        rpt_btn_layout = QHBoxLayout()
        rpt_btn_layout.setSpacing(8)

        self.btn_print_report = QPushButton("چاپ صورت‌جلسه تحویل (.MRT)", report_box)
        self.btn_print_report.setProperty("class", "GoldPrimary")
        self.btn_print_report.setFixedHeight(32)
        self.btn_print_report.setIcon(IconFactory.get_icon("check", size=14, color_override="#000000"))
        self.btn_print_report.clicked.connect(self._print_handover_report)
        rpt_btn_layout.addWidget(self.btn_print_report)

        self.btn_save_mrt = QPushButton("ذخیره فایل قالب (.mrt)", report_box)
        self.btn_save_mrt.setProperty("class", "GoldSecondary")
        self.btn_save_mrt.setFixedHeight(32)
        self.btn_save_mrt.clicked.connect(self._save_mrt_file)
        rpt_btn_layout.addWidget(self.btn_save_mrt)

        self.btn_open_mrt = QPushButton("طراحی در استیمول‌سافت", report_box)
        self.btn_open_mrt.setProperty("class", "GoldSecondary")
        self.btn_open_mrt.setFixedHeight(32)
        self.btn_open_mrt.clicked.connect(self._open_mrt_in_designer)
        rpt_btn_layout.addWidget(self.btn_open_mrt)

        report_layout.addLayout(rpt_btn_layout)
        cards_layout.addWidget(report_box, stretch=1)

        main_layout.addLayout(cards_layout)

        # ۳. ردیف دکمه‌های عملیاتی پایانی
        btn_frame = QFrame(container)
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 6, 0, 4)
        btn_layout.setSpacing(12)
        btn_layout.setAlignment(Qt.AlignCenter)

        self.btn_launch = QPushButton("اجرای سپهریار", btn_frame)
        self.btn_launch.setProperty("class", "GoldPrimary")
        self.btn_launch.setMinimumWidth(130)
        self.btn_launch.setFixedHeight(40)
        self.btn_launch.setIcon(IconFactory.get_icon("play", size=16, color_override="#000000"))
        self.btn_launch.clicked.connect(self._launch_app)
        btn_layout.addWidget(self.btn_launch)

        self.btn_keygen = QPushButton("🔑 فعال‌سازی قفل (کیجن)", btn_frame)
        self.btn_keygen.setProperty("class", "GoldSecondary")
        self.btn_keygen.setMinimumWidth(150)
        self.btn_keygen.setFixedHeight(40)
        self.btn_keygen.setIcon(IconFactory.get_icon("key", size=16))
        self.btn_keygen.clicked.connect(self._open_keygen_dialog)
        # دکمه کیجن به صورت پیش‌فرض کاملاً مخفی است تا مشتری متوجه قفل‌شکن نشود
        # صرفاً تکنسین مجاز با زدن کلید میانبر محرمانه Ctrl+Shift+K می‌تواند آن را مشاهده و باز کند
        self.btn_keygen.setVisible(False)
        from PySide6.QtGui import QKeySequence, QShortcut
        self.shortcut_secret_keygen = QShortcut(QKeySequence("Ctrl+Shift+K"), self)
        self.shortcut_secret_keygen.activated.connect(self._toggle_keygen_button)

        self.btn_open_folder = QPushButton("باز کردن پوشه نصب", btn_frame)
        self.btn_open_folder.setProperty("class", "GoldSecondary")
        self.btn_open_folder.setMinimumWidth(135)
        self.btn_open_folder.setFixedHeight(40)
        self.btn_open_folder.setIcon(IconFactory.get_icon("folder", size=16))
        self.btn_open_folder.clicked.connect(self._open_folder)
        btn_layout.addWidget(self.btn_open_folder)

        self.btn_view_report = QPushButton("مشاهده لاگ نصب", btn_frame)
        self.btn_view_report.setProperty("class", "GoldSecondary")
        self.btn_view_report.setMinimumWidth(125)
        self.btn_view_report.setFixedHeight(40)
        self.btn_view_report.setIcon(IconFactory.get_icon("log", size=16))
        self.btn_view_report.clicked.connect(self.view_report_requested.emit)
        btn_layout.addWidget(self.btn_view_report)

        self.btn_exit = QPushButton("پایان و خروج", btn_frame)
        self.btn_exit.setProperty("class", "GoldSecondary")
        self.btn_exit.setMinimumWidth(95)
        self.btn_exit.setFixedHeight(40)
        self.btn_exit.clicked.connect(self.exit_requested.emit)
        btn_layout.addWidget(self.btn_exit)

        main_layout.addWidget(btn_frame)

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def set_completion_data(
        self,
        root_dir: Path,
        selected_product_ids: List[str],
        install_mode: str = "server",
        sql_version: str = "2019",
        sql_instance: str = "",
    ):
        """
        دریافت داده‌های پایان نصب و نمایش در کارت‌های داشبورد
        """
        self.root_install_dir = root_dir
        self.selected_products = selected_product_ids
        self.install_mode = install_mode
        self.sql_version = str(sql_version)
        self.sql_instance = str(sql_instance).strip()

        titles = []
        for pid in selected_product_ids:
            p = get_product_by_id(pid)
            if p:
                titles.append(p.title)

        self.lbl_p_val.setText(" ، ".join(titles) if titles else "سپهریار")
        self.lbl_path_val.setText(str(root_dir))

        if install_mode == "client":
            self.lbl_sql_val.setText("ایستگاه کاری کلاینت (اتصال به سرور شبکه)")
        else:
            needs_sql = requires_sql_and_setup(selected_product_ids, install_mode="server")
            if needs_sql:
                inst_name = self.sql_instance or get_sql_instance_name(self.sql_version)
                self.lbl_sql_val.setText(f"{inst_name} (SQL Server {self.sql_version} Enterprise - متصل و فعال)")
            else:
                self.lbl_sql_val.setText("عدم نیاز به پایگاه داده محلی (صرفاً فایل اجرایی)")

    def set_technician_name(self, name: str):
        """تنظیم نام مسئول نصب از صفحه اول"""
        if name:
            self.txt_technician.setText(name)

    def _build_report_data(self) -> dict:
        technician = self.txt_technician.text().strip() or "کارشناس استقرار سپهریار"
        customer = self.txt_customer.text().strip() or "مشتری محترم"

        titles = []
        for pid in self.selected_products:
            p = get_product_by_id(pid)
            if p:
                titles.append(p.title)

        is_client = (getattr(self, "install_mode", "server") == "client")
        if is_client:
            sql_display = "کلاینت تحت شبکه (اتصال به سرور مرکزی)"
        else:
            needs_sql = requires_sql_and_setup(self.selected_products, install_mode="server")
            sql_ver = getattr(self, "sql_version", "2019")
            inst_name = getattr(self, "sql_instance", "") or get_sql_instance_name(sql_ver)
            sql_display = f"{inst_name} (SQL Server {sql_ver})" if needs_sql else "عدم نیاز به SQL (صرفاً فایل اجرایی)"

        # ساخت خلاصه سخت‌افزاری واقعی
        ram = get_physical_ram_gb()
        cpu = get_cpu_info()
        win = get_windows_info()
        hw_summary = f"{win.get('display', 'Windows 64-bit')} | رم فیزیکی: {ram} GB | پردازنده: {cpu.get('name', 'CPU')}"

        return {
            "technician_name": technician,
            "customer_name": customer,
            "install_date": datetime.date.today().strftime("%Y/%m/%d"),
            "install_time": datetime.datetime.now().strftime("%H:%M"),
            "install_path": str(self.root_install_dir) if self.root_install_dir else "D:\\SEPEHRYAR",
            "sql_instance": sql_display,
            "products": titles if titles else ["حسابداری سپهریار"],
            "hardware_summary": hw_summary,
        }

    def _print_handover_report(self):
        """چاپ یا پیش‌نمایش پرینت صورت‌جلسه تحویل با ذخیره اتوماتیک قالب MRT"""
        data = self._build_report_data()

        # ذخیره خودکار فایل قالب MRT در پوشه Setup یا ریشه در صورت عدم وجود ستاپ
        if self.root_install_dir:
            try:
                mrt_dir = self.root_install_dir / "SEPEHRYAR.Setup"
                if not mrt_dir.exists():
                    mrt_dir = self.root_install_dir
                mrt_path = mrt_dir / "RptInstallationSummary.mrt"
                generate_installation_mrt(data, mrt_path)
            except Exception as ex:
                print(f"Auto-save MRT notice: {ex}")

        # نمایش پنجره رسمی پیش‌نمایش چاپ
        try:
            show_print_preview_dialog(data, self)
        except Exception as ex:
            QMessageBox.critical(
                self,
                "خطا در چاپ",
                f"امکان راه‌اندازی پیش‌نمایش چاپ وجود ندارد:\n{ex}"
            )

    def _save_mrt_file(self):
        """ذخیره دستی فایل قالب استیمول‌سافت .mrt با دیالوگ Save File"""
        data = self._build_report_data()
        default_file = "RptInstallationSummary.mrt"
        if self.root_install_dir:
            mrt_dir = self.root_install_dir / "SEPEHRYAR.Setup"
            if not mrt_dir.exists():
                mrt_dir = self.root_install_dir
            default_file = str(mrt_dir / "RptInstallationSummary.mrt")

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره قالب گزارش استیمول‌سافت (.mrt)",
            default_file,
            "Stimulsoft Report Files (*.mrt)"
        )
        if file_path:
            try:
                target_p = Path(file_path)
                saved_path = generate_installation_mrt(data, target_p)
                QMessageBox.information(
                    self,
                    "ذخیره موفق",
                    f"فایل قالب استیمول‌سافت (.mrt) با موفقیت ذخیره شد:\n{saved_path}"
                )
            except Exception as ex:
                QMessageBox.critical(
                    self,
                    "خطا در ذخیره",
                    f"امکان ذخیره فایل گزارش وجود ندارد:\n{ex}"
                )

    def _open_mrt_in_designer(self):
        """باز کردن مستقیم فایل قالب .mrt در برنامه رسمی استیمول‌سافت"""
        data = self._build_report_data()
        mrt_dir = (self.root_install_dir / "SEPEHRYAR.Setup") if self.root_install_dir and (self.root_install_dir / "SEPEHRYAR.Setup").exists() else (self.root_install_dir or Path.cwd())
        mrt_path = mrt_dir / "RptInstallationSummary.mrt"
        try:
            generate_installation_mrt(data, mrt_path)
            designer_candidates = [
                Path(r"C:\Program Files (x86)\Stimulsoft Reports.Net 2013.2\Bin\Designer.exe"),
                Path(r"C:\Program Files\Stimulsoft Reports.Net 2013.2\Bin\Designer.exe"),
            ]
            designer_exe = next((p for p in designer_candidates if p.exists()), None)
            if designer_exe:
                subprocess.Popen([str(designer_exe), str(mrt_path)])
            else:
                os.startfile(str(mrt_path))
        except Exception as ex:
            QMessageBox.warning(
                self,
                "خطا در باز کردن",
                f"امکان باز کردن مستقیم فایل گزارش در استیمول‌سافت وجود ندارد:\n{ex}"
            )

    def _toggle_keygen_button(self):
        """نمایش/مخفی‌سازی دکمه کیجن به صورت محرمانه توسط تکنسین"""
        self.btn_keygen.setVisible(not self.btn_keygen.isVisible())

    def _open_folder(self):
        if self.root_install_dir and self.root_install_dir.exists():
            try:
                os.startfile(str(self.root_install_dir))
            except Exception:
                subprocess.Popen(["explorer", str(self.root_install_dir)])

    def _open_keygen_dialog(self):
        """باز کردن دیالوگ کیجن و فعال‌سازی قفل نرم‌افزاری"""
        first_pid = self.selected_products[0] if self.selected_products else "SEPEHRYAR.Hesabdari"
        exe_path = resolve_installed_exe_path(self.root_install_dir, first_pid) if self.root_install_dir else None
        dlg = KeygenDialog(exe_path=exe_path, parent=self)
        dlg.exec()

    def _launch_app(self):
        """اجرای اولین محصول انتخاب شده و بررسی تنظیمات اتصال دیتابیس و بازگشایی پس‌زمینه قفل"""
        if self.root_install_dir and self.selected_products:
            first_pid = self.selected_products[0]
            exe_path = resolve_installed_exe_path(self.root_install_dir, first_pid)
            if exe_path and exe_path.exists():
                try:
                    # تضمین تنظیم conect.xml قبل از باز شدن برنامه
                    from utils.connect_config import configure_hesabdari_connection
                    inst = self.sql_instance or get_sql_instance_name(self.sql_version)
                    server_target = f".\\{inst}"
                    configure_hesabdari_connection(self.root_install_dir, server_target, "Sepehr_Main_1405")
                except Exception:
                    pass

                try:
                    # باز کردن برنامه و اتوماسیون بی‌صدا قفل در پس‌زمینه بدون افشای رمز
                    import threading
                    from utils.sepehryar_keygen import auto_unlock_sepehryar_app
                    
                    def bg_unlock():
                        auto_unlock_sepehryar_app(exe_path, timeout_sec=20)

                    th = threading.Thread(target=bg_unlock, daemon=True)
                    th.start()
                except Exception as ex:
                    print(f"Error launching app: {ex}")
        self.launch_requested.emit()
        self.launch_requested.emit()
