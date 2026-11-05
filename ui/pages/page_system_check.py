# ui/pages/page_system_check.py
"""
صفحه ۱: بررسی آمادگی سیستم، اطلاعات استقرار و تشخیص هوشمند اینستنس‌های SQL Server
Page 1: System Readiness, Deployment Setup & Smart SQL Server Instance Detection
"""

from typing import Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from config.settings import THEME_COLORS, get_sql_instance_name
from app_logging.app_logger import logger
from sql.sql_auditor import SQLInstanceAuditor, InstanceAuditInfo
from sql.sql_detector import get_all_installed_sql_instances
from system_check.hardware_checker import check_all_system_requirements, SystemCheckResult
from ui.components.gold_card import HardwareCheckCard, ModeSelectionCard
from ui.dialogs.sql_version_dialog import SQLVersionDialog
from ui.dialogs.sql_instance_dialog import SQLInstancePromptDialog
from ui.dialogs.client_connect_dialog import ClientConnectDialog
from utils.icon_factory import IconFactory


class SystemCheckPage(QWidget):
    """
    صفحه بررسی شرایط سیستم جهت نصب سپهریار، ثبت اطلاعات تکنسین،
    تشخیص هوشمند اینستنس‌های موجود SEPEHRYAR2019 / SEPEHRYAR2014 و انتخاب نوع استقرار
    """
    check_completed = Signal(bool)  # can_proceed
    install_mode_changed = Signal(str)  # "server" or "client"
    sql_version_changed = Signal(str)  # "2014" or "2019"
    sql_instance_changed = Signal(str)  # SQL instance name
    server_target_changed = Signal(str)  # Server IP / Name for CONNECT file

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_result: Optional[SystemCheckResult] = None
        self.install_mode: str = "server"
        self.sql_version: str = "2019"
        self.sql_instance_name: str = ""
        self.has_prompted_instance: bool = False
        self.detected_instances: list = []
        self.client_server_target: str = ""
        self.sql_audits: Dict[str, InstanceAuditInfo] = {}
        self.detected_sql_instance: Optional[str] = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 16, 32, 14)
        main_layout.setSpacing(10)

        # عنوان و زیرعنوان
        title_lbl = QLabel("بررسی آمادگی سیستم و اطلاعات استقرار", self)
        title_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 22px; font-weight: bold;")
        main_layout.addWidget(title_lbl)

        sub_lbl = QLabel("ثبت مشخصات کارشناس استقرار، تعیین نوع نصب (سرور یا کلاینت)، ممیزی خودکار دیتابیس و ارزیابی سیستم", self)
        sub_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12.5px;")
        main_layout.addWidget(sub_lbl)

        # کادر دریافت نام کارشناس نصب (مسئول استقرار)
        tech_card = QFrame(self)
        tech_card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 10px;
                padding: 3px;
            }}
        """)
        tech_layout = QHBoxLayout(tech_card)
        tech_layout.setContentsMargins(14, 6, 14, 6)
        tech_layout.setSpacing(12)

        icon_tech = QLabel(tech_card)
        icon_pix = IconFactory.get_icon("technician", size=22, color_override=THEME_COLORS["gold_primary"]).pixmap(22, 22)
        icon_tech.setPixmap(icon_pix)
        tech_layout.addWidget(icon_tech)

        lbl_tech_name = QLabel("نام کارشناس استقرار (مسئول نصب):", tech_card)
        lbl_tech_name.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 12.5px; font-weight: bold;")
        tech_layout.addWidget(lbl_tech_name)

        self.txt_technician = QLineEdit(tech_card)
        self.txt_technician.setPlaceholderText("نام و نام خانوادگی کارشناس نصب را وارد نمایید...")
        self.txt_technician.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0E1015;
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12.5px;
            }}
            QLineEdit:focus {{
                border-color: {THEME_COLORS['gold_primary']};
            }}
        """)
        tech_layout.addWidget(self.txt_technician, stretch=1)
        main_layout.addWidget(tech_card)

        # بخش انتخاب نوع نصب و استقرار (سرور اصلی یا کلاینت)
        mode_header = QLabel("نوع استقرار سیستم سپهریار:", self)
        mode_header.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 12.5px; font-weight: bold;")
        main_layout.addWidget(mode_header)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(12)

        # کارت ۱: سرور مرکزی
        self.card_server = ModeSelectionCard(
            mode="server",
            title="🖥️ نصب سرور مرکزی (Server)",
            subtitle="پایگاه داده اصلی، حسابداری، صنعتی و سرویس‌ها",
            desc="نصب سرور؛ در صورت وجود اینستنس SEPEHRYAR2019/2014 به طور خودکار شناسایی و استفاده خواهد شد",
            icon_name="server",
            is_active=(self.install_mode == "server"),
            parent=self
        )
        self.card_server.clicked.connect(self._on_mode_clicked)
        mode_layout.addWidget(self.card_server)

        # کارت ۲: کلاینت / فروش
        self.card_client = ModeSelectionCard(
            mode="client",
            title="💻 نصب کلاینت / فروش (Client)",
            subtitle="ایستگاه کاری متصل به سرور و نرم‌افزار فروش",
            desc="نصب ایستگاه فروش؛ انتقال کلیه فایل‌ها و پیش‌نیازهای Setup بدون نیاز به SQL Server",
            icon_name="client",
            is_active=(self.install_mode == "client"),
            parent=self
        )
        self.card_client.clicked.connect(self._on_mode_clicked)
        mode_layout.addWidget(self.card_client)

        main_layout.addLayout(mode_layout)

        # =========================================================================
        # نوار نمایش نسخه SQL Server و وضعیت تشخیص هوشمند
        # =========================================================================
        self.sql_info_bar = QFrame(self)
        self.sql_info_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 8px;
            }}
        """)
        sql_bar_layout = QHBoxLayout(self.sql_info_bar)
        sql_bar_layout.setContentsMargins(14, 8, 14, 8)
        sql_bar_layout.setSpacing(12)

        self.sql_info_icon = QLabel(self.sql_info_bar)
        self.sql_info_icon.setPixmap(IconFactory.get_icon("database", size=24, color_override=THEME_COLORS["gold_primary"]).pixmap(24, 24))
        sql_bar_layout.addWidget(self.sql_info_icon)

        self.lbl_sql_summary = QLabel(self.sql_info_bar)
        self.lbl_sql_summary.setWordWrap(True)
        self.lbl_sql_summary.setStyleSheet("font-size: 12.5px; color: #FFFFFF;")
        sql_bar_layout.addWidget(self.lbl_sql_summary, stretch=1)

        self.btn_change_instance = QPushButton("تنظیم اینستنس", self.sql_info_bar)
        self.btn_change_instance.setProperty("class", "GoldPrimary")
        self.btn_change_instance.setIcon(IconFactory.get_icon("database", size=15, color_override="#000000"))
        self.btn_change_instance.setStyleSheet("padding: 5px 12px; font-size: 12px; font-weight: bold;")
        self.btn_change_instance.clicked.connect(self.show_sql_instance_dialog)
        sql_bar_layout.addWidget(self.btn_change_instance)

        self.btn_change_sql = QPushButton("تغییر نسخه SQL", self.sql_info_bar)
        self.btn_change_sql.setProperty("class", "GoldSecondary")
        self.btn_change_sql.setIcon(IconFactory.get_icon("database", size=15))
        self.btn_change_sql.setStyleSheet("padding: 5px 12px; font-size: 12px;")
        self.btn_change_sql.clicked.connect(self.show_sql_selection_dialog)
        sql_bar_layout.addWidget(self.btn_change_sql)

        self.btn_troubleshoot = QPushButton("عیب‌یابی و تأمین کسری‌ها", self.sql_info_bar)
        self.btn_troubleshoot.setProperty("class", "GoldSecondary")
        self.btn_troubleshoot.setIcon(IconFactory.get_icon("gear", size=15))
        self.btn_troubleshoot.setStyleSheet("padding: 5px 12px; font-size: 12px;")
        self.btn_troubleshoot.clicked.connect(self._open_troubleshooting_panel)
        sql_bar_layout.addWidget(self.btn_troubleshoot)

        main_layout.addWidget(self.sql_info_bar)
        self.sql_info_bar.setVisible(self.install_mode == "server")

        # =========================================================================
        # نوار نمایش اتصال کلاینت به سرور مرکزی (فایل CONNECT)
        # =========================================================================
        self.client_info_bar = QFrame(self)
        self.client_info_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 8px;
            }}
        """)
        client_bar_layout = QHBoxLayout(self.client_info_bar)
        client_bar_layout.setContentsMargins(14, 6, 14, 6)
        client_bar_layout.setSpacing(12)

        self.client_info_icon = QLabel(self.client_info_bar)
        self.client_info_icon.setPixmap(IconFactory.get_icon("server", size=22, color_override=THEME_COLORS["gold_primary"]).pixmap(22, 22))
        client_bar_layout.addWidget(self.client_info_icon)

        self.lbl_client_summary = QLabel("🌐 اتصال به سرور: <i>هنوز مشخص نشده (جهت تنظیم کلیک کنید)</i>", self.client_info_bar)
        self.lbl_client_summary.setStyleSheet("font-size: 12.5px; color: #FFFFFF;")
        client_bar_layout.addWidget(self.lbl_client_summary, stretch=1)

        self.btn_change_client = QPushButton("تنظیم سرور (فایل CONNECT)", self.client_info_bar)
        self.btn_change_client.setProperty("class", "GoldSecondary")
        self.btn_change_client.setIcon(IconFactory.get_icon("server", size=15))
        self.btn_change_client.setStyleSheet("padding: 5px 12px; font-size: 12px;")
        self.btn_change_client.clicked.connect(self.show_client_connect_dialog)
        client_bar_layout.addWidget(self.btn_change_client)

        main_layout.addWidget(self.client_info_bar)
        self.client_info_bar.setVisible(self.install_mode == "client")

        # ناحیه اسکرول برای کارت‌های بررسی سخت‌افزار
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 4, 0, 4)
        self.cards_layout.setSpacing(10)

        scroll.setWidget(self.cards_container)
        main_layout.addWidget(scroll, stretch=1)

        # نوار پایین بررسی با دکمه اسکن مجدد
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        self.status_summary_lbl = QLabel("در حال بررسی...", self)
        self.status_summary_lbl.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 14px;")
        bottom_bar.addWidget(self.status_summary_lbl, stretch=1)

        self.btn_rescan = QPushButton("بررسی مجدد", self)
        self.btn_rescan.setProperty("class", "GoldSecondary")
        self.btn_rescan.setIcon(IconFactory.get_icon("refresh", size=16))
        self.btn_rescan.clicked.connect(self.run_check)
        bottom_bar.addWidget(self.btn_rescan)

        main_layout.addLayout(bottom_bar)

    def _on_mode_clicked(self, mode: str):
        self.set_install_mode(mode)
        if mode == "server":
            self.show_sql_selection_dialog()
        elif mode == "client":
            self.show_client_connect_dialog()

    def show_sql_selection_dialog(self):
        """نمایش فرم انتخاب نسخه با مشخص‌سازی اینستنس‌های نصب‌شده"""
        installed_dict = {
            "2014": self.sql_audits.get("2014", InstanceAuditInfo("", "")).is_installed,
            "2019": self.sql_audits.get("2019", InstanceAuditInfo("", "")).is_installed,
        }
        dlg = SQLVersionDialog(
            current_version=self.sql_version,
            installed_versions=installed_dict,
            parent=self.window(),
        )
        if dlg.exec():
            self.set_sql_version(dlg.get_selected_version())

    def show_client_connect_dialog(self):
        dlg = ClientConnectDialog(current_target=self.client_server_target, parent=self.window())
        if dlg.exec():
            self.set_server_target(dlg.get_server_target())

    def set_server_target(self, target: str):
        self.client_server_target = target.strip()
        if self.client_server_target:
            self.lbl_client_summary.setText(f"🌐 اتصال به سرور مرکزی: <b style='color:#38BDF8'>{self.client_server_target}</b> (تنظیم خودکار فایل‌های CONNECT)")
        else:
            self.lbl_client_summary.setText("🌐 اتصال به سرور مرکزی: <i>هنوز تنظیم نشده است (جهت تنظیم کلیک کنید)</i>")
        self.server_target_changed.emit(self.client_server_target)

    def get_server_target(self) -> str:
        return self.client_server_target

    def set_sql_version(self, version: str):
        self.sql_version = str(version)
        self._update_sql_banner_text()
        self.sql_version_changed.emit(self.sql_version)
        logger.log("SYSTEM_CHECK", "SQL_VERSION", "INFO", f"نسخه پایگاه داده تنظیم شد: {self.sql_version}")

    def show_sql_instance_dialog(self):
        """نمایش دیالوگ دریافت و انتخاب اینستنس از کاربر"""
        dlg = SQLInstancePromptDialog(
            current_instance=self.get_sql_instance_name(),
            detected_instances=self.detected_instances,
            sql_version=self.sql_version,
            parent=self.window(),
        )
        if dlg.exec():
            selected_inst = dlg.get_selected_instance()
            use_existing = dlg.is_use_existing_instance()
            self.set_sql_instance_name(selected_inst, force_new=not use_existing)

    def set_sql_instance_name(self, inst_name: str, force_new: bool = False):
        self.sql_instance_name = inst_name.strip()
        self.force_new_sql_instance = force_new
        self.detected_sql_instance = self.sql_instance_name
        if "2014" in self.sql_instance_name:
            self.sql_version = "2014"
        elif "2019" in self.sql_instance_name:
            self.sql_version = "2019"
        self._update_sql_banner_text()
        self.sql_instance_changed.emit(self.sql_instance_name)
        logger.log("SYSTEM_CHECK", "SQL_INSTANCE", "INFO", f"نام اینستنس انتخاب شد: {self.sql_instance_name} (force_new={force_new})")

    def get_sql_instance_name(self) -> str:
        if self.sql_instance_name:
            return self.sql_instance_name
        if self.detected_sql_instance:
            return self.detected_sql_instance
        return get_sql_instance_name(self.sql_version)

    def is_force_new_sql_instance(self) -> bool:
        return getattr(self, "force_new_sql_instance", False)

    def _update_sql_banner_text(self):
        inst_name = self.get_sql_instance_name()
        force_new = getattr(self, "force_new_sql_instance", False)
        audit = self.sql_audits.get(inst_name)
        if not force_new and audit and audit.is_installed:
            db_count = len(audit.databases)
            dbs_text = f" | {db_count} دیتابیس فعال" if db_count > 0 else ""
            status_text = "در حال اجرا" if audit.service_status == "running" else "آماده استارت"
            text = (
                f"✓ <b style='color:{THEME_COLORS['success']}'>اینستنس {inst_name} شناسایی شد</b> "
                f"(وضعیت: <b style='color:#38BDF8'>{status_text}</b>{dbs_text}) — <b>بدون نیاز به نصب مجدد</b>"
            )
            self.sql_info_bar.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(16, 185, 129, 0.1);
                    border: 1px solid {THEME_COLORS['success']};
                    border-radius: 8px;
                }}
            """)
        else:
            if self.sql_version == "2014":
                ver_name = "Microsoft SQL Server 2014 Enterprise"
            else:
                ver_name = "Microsoft SQL Server 2019 Enterprise"
            text = (
                f"🚀 اینستنس پایگاه داده: <b style='color:#D8A84E'>{inst_name}</b> ({ver_name}) — "
                f"<b>نصب اینستنس جدید توسط اینستالر</b>"
            )
            self.sql_info_bar.setStyleSheet(f"""
                QFrame {{
                    background-color: {THEME_COLORS['card_bg']};
                    border: 1px solid {THEME_COLORS['card_border']};
                    border-radius: 8px;
                }}
            """)
        self.lbl_sql_summary.setText(text)

    def get_sql_version(self) -> str:
        return self.sql_version

    def set_install_mode(self, mode: str):
        if self.install_mode == mode and self.last_result is not None:
            return
        self.install_mode = mode
        self.card_server.set_active(mode == "server")
        self.card_client.set_active(mode == "client")
        self.sql_info_bar.setVisible(mode == "server")
        self.client_info_bar.setVisible(mode == "client")
        self.install_mode_changed.emit(mode)
        self.run_check()

    def get_install_mode(self) -> str:
        return self.install_mode

    def run_check(self):
        """
        اجرای بررسی واقعی سیستم و ممیزی زنده اینستنس‌های SQL Server
        """
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # ۱. ممیزی خودکار اینستنس‌های SQL Server
        auditor = SQLInstanceAuditor()
        self.sql_audits = auditor.scan_all_instances()
        self.detected_instances = get_all_installed_sql_instances()

        # اگر اینستنس یا سرویس SQL وجود داشته باشد، کادر انتخاب/تأیید نام اینستنس را باز کن
        if self.detected_instances and not self.has_prompted_instance and self.install_mode == "server":
            self.has_prompted_instance = True
            # باز کردن کادر دریافت نام اینستنس
            self.show_sql_instance_dialog()
        elif not self.sql_instance_name:
            if self.detected_instances:
                self.sql_instance_name = self.detected_instances[0]
                self.detected_sql_instance = self.sql_instance_name
            else:
                preferred = auditor.get_preferred_instance()
                if preferred and preferred.is_installed:
                    self.sql_instance_name = preferred.instance_name
                    self.detected_sql_instance = preferred.instance_name
                    if "2014" in preferred.instance_name:
                        self.sql_version = "2014"
                    elif "2019" in preferred.instance_name:
                        self.sql_version = "2019"

        self._update_sql_banner_text()

        # ۲. بررسی شرایط سخت‌افزاری
        result = check_all_system_requirements(install_mode=self.install_mode, sql_version=self.sql_version)
        self.last_result = result

        for item in result.items:
            card = HardwareCheckCard(
                title=item.title_fa,
                detected=item.detected_value,
                required=item.required_value,
                passed=item.passed,
                icon_name=item.icon_name,
                reason=item.failure_reason,
                parent=self.cards_container,
            )
            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()

        mode_name = "سرور" if self.install_mode == "server" else "کلاینت (فروش)"
        if result.can_proceed:
            self.status_summary_lbl.setText(f"✓ شرایط سیستم برای نصب {mode_name} سپهریار مناسب است.")
            self.status_summary_lbl.setStyleSheet(f"color: {THEME_COLORS['success']}; font-size: 14px; font-weight: bold;")
        else:
            self.status_summary_lbl.setText(f"✕ برخی پیش‌نیازهای ضروری سیستم برای نصب {mode_name} تأمین نشده است.")
            self.status_summary_lbl.setStyleSheet(f"color: {THEME_COLORS['error']}; font-size: 14px; font-weight: bold;")

        self.check_completed.emit(result.can_proceed)

    def get_technician_name(self) -> str:
        return self.txt_technician.text().strip()

    def _open_troubleshooting_panel(self):
        from ui.dialogs.troubleshooting_panel import TroubleshootingPanelDialog
        dlg = TroubleshootingPanelDialog(parent=self)
        dlg.exec()
        self.run_check()
