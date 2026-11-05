# ui/main_window.py
"""
پنجره اصلی اینستالر سپهریار هماهنگ‌کننده سایدبار، صفحات، تب‌های حالت نصب و نوار اقدامات
Main Window assembling Sidebar, QStackedWidget Pages, Mode Tabs, and Action Bar
"""

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from config.settings import (
    APP_NAME_FA,
    APP_VERSION,
    APP_ICON_PNG,
    APP_ICON_ICO,
    THEME_COLORS,
)
from core.worker import InstallWorker
from app_logging.app_logger import logger
from ui.action_bar import ActionBar
from ui.dialogs.error_dialog import ErrorDialog
from ui.dialogs.log_dialog import LogViewerDialog
from ui.dialogs.troubleshooting_panel import TroubleshootingPanelDialog
from ui.pages import (
    ClientInstallPage,
    DriveSelectPage,
    FinalPage,
    ProductSelectPage,
    ProgressDashboardPage,
    SystemCheckPage,
    UpdatePackagePage,
)
from ui.sidebar import InstallerSidebar
from utils.icon_factory import IconFactory


class MainWindow(QMainWindow):
    """
    پنجره اصلی اینستالر با پشتیبانی کامل از RTL، تب‌بار دوگانه (سرور/کلاینت) و معماری واکنش‌گرا
    """
    sig_log_received = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME_FA} - نسخه {APP_VERSION}")
        self.setMinimumSize(1100, 680)
        self.resize(1220, 750)
        if APP_ICON_PNG.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PNG)))
        elif APP_ICON_ICO.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_ICO)))
        else:
            self.setWindowIcon(IconFactory.get_icon("database", size=32))

        self.worker: InstallWorker = None
        self._pending_install_error = None
        self._install_result = None
        self._close_when_finished = False
        self._review_plan = None
        self._resume_installation = True
        self._last_server_page_idx = 0
        self.current_mode = "server"

        self._init_ui()
        self._connect_signals()

        # اتصال امن و Thread-Safe سیگنال به لاگر داشبورد جهت جلوگیری از کراش
        self.sig_log_received.connect(self.page_progress.append_log_snippet)

        # اجرای بررسی اولیه سیستم در صفحه ۱
        self.page_system_check.run_check()

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_v_layout = QVBoxLayout(central_widget)
        root_v_layout.setContentsMargins(0, 0, 0, 0)
        root_v_layout.setSpacing(0)

        # =====================================================================
        # نوار بالای پنجره: تب‌های سوئیچ بین حالت «سرور مرکزی» و «نصب کلاینت»
        # =====================================================================
        self.top_tab_bar = QFrame(central_widget)
        self.top_tab_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['bg_secondary']};
                border-bottom: 1px solid {THEME_COLORS['border_medium']};
            }}
        """)
        tab_h_layout = QHBoxLayout(self.top_tab_bar)
        tab_h_layout.setContentsMargins(18, 8, 18, 8)
        tab_h_layout.setSpacing(14)

        # آیکون و برند سپهریار
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(8)
        icon_brand = QLabel(self.top_tab_bar)
        icon_brand.setPixmap(IconFactory.get_icon("database", size=22, color_override=THEME_COLORS["gold_primary"]).pixmap(22, 22))
        brand_layout.addWidget(icon_brand)

        lbl_brand = QLabel(f"{APP_NAME_FA} - نسخه {APP_VERSION}", self.top_tab_bar)
        lbl_brand.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-weight: bold; font-size: 13.5px;")
        brand_layout.addWidget(lbl_brand)
        tab_h_layout.addLayout(brand_layout)

        tab_h_layout.addStretch(1)

        # دکمه‌های ناوبری تب‌ها
        self.btn_tab_server = QPushButton("🏢 نصب سرور مرکزی (پایگاه داده و استقرار)", self.top_tab_bar)
        self.btn_tab_server.setCursor(Qt.PointingHandCursor)
        self.btn_tab_server.clicked.connect(self.switch_to_server_mode)
        tab_h_layout.addWidget(self.btn_tab_server)

        self.btn_tab_client = QPushButton("💻 نصب کلاینت (پیش‌نیازها و نسخه‌های اجرایی)", self.top_tab_bar)
        self.btn_tab_client.setCursor(Qt.PointingHandCursor)
        self.btn_tab_client.clicked.connect(self.switch_to_client_mode)
        tab_h_layout.addWidget(self.btn_tab_client)

        root_v_layout.addWidget(self.top_tab_bar)

        # =====================================================================
        # بدنه اصلی: سایدبار در یک سو و محتوا در سوی دیگر
        # =====================================================================
        self.body_container = QWidget(central_widget)
        main_h_layout = QHBoxLayout(self.body_container)
        main_h_layout.setContentsMargins(0, 0, 0, 0)
        main_h_layout.setSpacing(0)

        # ۱. سایدبار مراحل سرور
        self.sidebar = InstallerSidebar(self.body_container)
        main_h_layout.addWidget(self.sidebar)

        # ۲. ناحیه سمت محتوا (محتوای صفحات + اکشن‌بار)
        content_v_widget = QWidget(self.body_container)
        content_v_layout = QVBoxLayout(content_v_widget)
        content_v_layout.setContentsMargins(0, 0, 0, 0)
        content_v_layout.setSpacing(0)

        # استک صفحات
        self.stack = QStackedWidget(content_v_widget)

        self.page_system_check = SystemCheckPage(self.stack)
        self.page_drive_select = DriveSelectPage(self.stack)
        self.page_product_select = ProductSelectPage(self.stack)
        self.page_update = UpdatePackagePage(self.stack)
        self.page_progress = ProgressDashboardPage(self.stack)
        self.page_final = FinalPage(self.stack)
        self.page_client_install = ClientInstallPage(self.stack)

        self.stack.addWidget(self.page_system_check)    # Index 0
        self.stack.addWidget(self.page_drive_select)    # Index 1
        self.stack.addWidget(self.page_product_select)  # Index 2
        self.stack.addWidget(self.page_update)          # Index 3
        self.stack.addWidget(self.page_progress)        # Index 4
        self.stack.addWidget(self.page_final)           # Index 5
        self.stack.addWidget(self.page_client_install)  # Index 6

        content_v_layout.addWidget(self.stack, stretch=1)

        # نوار پایین اقدامات (Action Bar)
        self.action_bar = ActionBar(content_v_widget)
        content_v_layout.addWidget(self.action_bar)

        main_h_layout.addWidget(content_v_widget, stretch=1)
        root_v_layout.addWidget(self.body_container, stretch=1)

        # تنظیم وضعیت اولیه دکمه‌ها و تب فعال
        self._update_tab_buttons("server")
        self._update_navigation_state(0)

    def _update_tab_buttons(self, active_tab: str):
        """تنظیم استایل تب‌های بالا بر اساس حالت فعال"""
        c = THEME_COLORS
        active_style = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['gold_primary']}, stop:1 {c['gold_dark']});
                color: #0E1015;
                font-weight: bold;
                font-size: 12.5px;
                padding: 6px 18px;
                border: none;
                border-radius: 6px;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background-color: {c['card_bg']};
                color: {c['text_secondary']};
                font-size: 12.5px;
                padding: 6px 18px;
                border: 1px solid {c['card_border']};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border-color: {c['gold_primary']};
                color: {c['text_primary']};
                background-color: {c['card_hover']};
            }}
        """
        if active_tab == "server":
            self.btn_tab_server.setStyleSheet(active_style)
            self.btn_tab_client.setStyleSheet(inactive_style)
        else:
            self.btn_tab_server.setStyleSheet(inactive_style)
            self.btn_tab_client.setStyleSheet(active_style)

    def switch_to_server_mode(self):
        """سوئیچ به حالت ویزارد سرور مرکزی"""
        self.current_mode = "server"
        self._update_tab_buttons("server")
        self.sidebar.setVisible(True)
        self.action_bar.setVisible(self._last_server_page_idx != 5)
        self.stack.setCurrentIndex(self._last_server_page_idx)
        self._update_navigation_state(self._last_server_page_idx)

    def switch_to_client_mode(self):
        """سوئیچ به صفحه مستقل و سریع نصب کلاینت"""
        self.current_mode = "client"
        self._update_tab_buttons("client")
        self.sidebar.setVisible(False)
        self.action_bar.setVisible(False)
        self.stack.setCurrentWidget(self.page_client_install)

    def _connect_signals(self):
        # دکمه‌های اکشن‌بار
        self.action_bar.next_clicked.connect(self._go_next)
        self.action_bar.prev_clicked.connect(self._go_prev)
        self.action_bar.cancel_clicked.connect(self.close)
        self.action_bar.log_clicked.connect(self._show_log_dialog)
        self.action_bar.troubleshoot_clicked.connect(self._show_troubleshooting_panel)

        # کلید میانبر F12 جهت فراخوانی سریع پنل عیب‌یابی در هر مرحله
        self.shortcut_f12 = QShortcut(QKeySequence("F12"), self)
        self.shortcut_f12.activated.connect(self._show_troubleshooting_panel)

        # سیگنال‌های صفحات
        self.page_system_check.check_completed.connect(self._on_system_check_completed)
        self.page_system_check.install_mode_changed.connect(self._on_system_mode_changed)
        self.page_drive_select.drive_selected.connect(self._on_drive_selected)
        self.page_product_select.selection_changed.connect(self._on_product_selection_changed)
        self.page_update.selection_changed.connect(self._on_update_selection_changed)

        # سیگنال‌های صفحه پایانی
        self.page_final.view_report_requested.connect(self._show_log_dialog)
        self.page_final.exit_requested.connect(self.close)

    def _on_system_mode_changed(self, mode: str):
        """هدایت هوشمند به تب کلاینت در صورت کلیک روی کارت کلاینت در صفحه اول"""
        if mode == "client":
            self.switch_to_client_mode()

    def _update_navigation_state(self, page_idx: int):
        self._last_server_page_idx = page_idx
        self.sidebar.set_current_step(page_idx)

        if page_idx == 0:
            self.action_bar.setVisible(True)
            self.action_bar.set_prev_visible(False)
            self.action_bar.set_next_text("انتخاب درایو نصب >")
            can_proceed = (
                self.page_system_check.last_result.can_proceed
                if self.page_system_check.last_result
                else False
            )
            self.action_bar.set_next_enabled(can_proceed)

        elif page_idx == 1:
            self.action_bar.setVisible(True)
            self.action_bar.set_prev_visible(True)
            self.action_bar.set_next_text("انتخاب محصول >")
            has_drive = bool(self.page_drive_select.get_selected_drive())
            self.action_bar.set_next_enabled(has_drive)

        elif page_idx == 2:
            self.action_bar.setVisible(True)
            self.action_bar.set_prev_visible(True)
            self.action_bar.set_next_text("مسیر بسته به‌روزرسانی >")
            has_products = len(self.page_product_select.get_selected_products()) > 0
            self.action_bar.set_next_enabled(has_products)

        elif page_idx == 3:
            # در صفحه اختصاصی مسیر و پکیج آپدیت
            self.action_bar.setVisible(True)
            self.action_bar.set_prev_visible(True)
            self.action_bar.set_next_text("شروع نصب سپهریار")
            can_proceed = self.page_update.is_skipped() or (self.page_update.get_archive_path() is not None) or (not self.page_update.txt_path.text().strip())
            self.action_bar.set_next_enabled(can_proceed)

        elif page_idx == 4:
            # در صفحه داشبورد و در حال نصب
            self.action_bar.setVisible(True)
            self.action_bar.set_prev_visible(False)
            self.action_bar.set_next_enabled(False)
            self.action_bar.set_next_text("در حال نصب...")

        elif page_idx == 5:
            # در صفحه پایان
            self.action_bar.setVisible(False)

    def _go_next(self):
        cur = self.stack.currentIndex()
        if cur == 0:
            tech_name = self.page_system_check.get_technician_name()
            install_mode = self.page_system_check.get_install_mode()
            sql_version = self.page_system_check.get_sql_version()
            sql_instance = self.page_system_check.get_sql_instance_name()
            force_new_sql = self.page_system_check.is_force_new_sql_instance()
            if tech_name:
                self.page_final.set_technician_name(tech_name)
                logger.log("INSTALLER", "TECHNICIAN", "INFO", f"کارشناس استقرار سپهریار: {tech_name} | حالت نصب: {install_mode} | نسخه SQL: {sql_version} | اینستنس: {sql_instance} (force_new={force_new_sql})")
            self.page_product_select.set_install_mode(install_mode)
            self.page_product_select.set_sql_version(sql_version)
            self.page_product_select.set_sql_instance_name(sql_instance, force_new=force_new_sql)
            self.stack.setCurrentIndex(1)
            self.page_drive_select.scan()
            self._update_navigation_state(1)
        elif cur == 1:
            install_mode = self.page_system_check.get_install_mode()
            sql_version = self.page_system_check.get_sql_version()
            sql_instance = self.page_system_check.get_sql_instance_name()
            force_new_sql = self.page_system_check.is_force_new_sql_instance()
            self.page_product_select.set_install_mode(install_mode)
            self.page_product_select.set_sql_version(sql_version)
            self.page_product_select.set_sql_instance_name(sql_instance, force_new=force_new_sql)
            self.stack.setCurrentIndex(2)
            self.page_product_select.load_products()
            self._update_navigation_state(2)
        elif cur == 2:
            # هدایت به صفحه ۳ (مسیر پکیج آپدیت)
            drive = self.page_drive_select.get_selected_drive()
            products = self.page_product_select.get_selected_products()
            install_mode = self.page_system_check.get_install_mode()
            sql_version = self.page_product_select.get_selected_sql_version()
            sql_instance = self.page_product_select.get_selected_sql_instance_name() or self.page_system_check.get_sql_instance_name()
            server_target = self.page_system_check.get_server_target()
            root_dir = Path(f"{drive}\\SEPEHRYAR") if drive else None

            self.page_update.set_context(
                root_dir=root_dir,
                selected_product_ids=products,
                install_mode=install_mode,
                sql_version=sql_version,
                server_target=server_target,
                sql_instance=sql_instance,
            )
            self.stack.setCurrentIndex(3)
            self._update_navigation_state(3)
        elif cur == 3:
            from core.install_plan import create_install_plan
            from ui.dialogs.install_review import InstallReviewDialog
            sql_instance = self.page_product_select.get_selected_sql_instance_name() or self.page_system_check.get_sql_instance_name()
            self._review_plan = create_install_plan(
                self.page_drive_select.get_selected_drive(), self.page_product_select.get_selected_products(),
                self.page_system_check.get_install_mode(), self.page_product_select.get_selected_sql_version(),
                self.page_system_check.get_server_target(), self.page_update.get_archive_path(),
                sql_instance=sql_instance,
            )
            review = InstallReviewDialog(self._review_plan, self)
            if not review.exec():
                return
            self._resume_installation = review.resume.isChecked()
            # شروع نصب در صفحه ۴
            self.stack.setCurrentIndex(4)
            self._update_navigation_state(4)
            self._start_installation()

    def _go_prev(self):
        cur = self.stack.currentIndex()
        if cur in [1, 2, 3]:
            self.stack.setCurrentIndex(cur - 1)
            self._update_navigation_state(cur - 1)

    def _on_system_check_completed(self, can_proceed: bool):
        if self.stack.currentIndex() == 0 and self.current_mode == "server":
            self.action_bar.set_next_enabled(can_proceed)

    def _on_drive_selected(self, drive_letter: str, is_valid: bool):
        if self.stack.currentIndex() == 1 and self.current_mode == "server":
            self.action_bar.set_next_enabled(is_valid)

    def _on_product_selection_changed(self, selected_ids: list, is_valid: bool):
        if self.stack.currentIndex() == 2 and self.current_mode == "server":
            self.action_bar.set_next_enabled(is_valid)

    def _on_update_selection_changed(self, is_valid: bool):
        if self.stack.currentIndex() == 3 and self.current_mode == "server":
            self.action_bar.set_next_enabled(is_valid)

    def _start_installation(self):
        self._pending_install_error = None
        self._install_result = None
        self._close_when_finished = False
        drive = self.page_drive_select.get_selected_drive()
        products = self.page_product_select.get_selected_products()
        install_mode = self.page_system_check.get_install_mode()
        sql_version = self.page_product_select.get_selected_sql_version()
        sql_instance = self.page_product_select.get_selected_sql_instance_name() or self.page_system_check.get_sql_instance_name()
        force_new_sql = self.page_product_select.is_force_new_sql_instance() or self.page_system_check.is_force_new_sql_instance()
        server_target = self.page_system_check.get_server_target()
        update_archive = self.page_update.get_archive_path()
        has_update = bool(update_archive and update_archive.exists())

        # پیکربندی داینامیک مراحل با توجه به پکیج‌های انتخابی، حالت نصب، نسخه SQL و وضعیت آپدیت
        self.page_progress.configure_stages(
            products,
            install_mode=install_mode,
            sql_version=sql_version,
            has_update=has_update,
        )
        self.page_progress.reset()

        self.worker = InstallWorker(
            selected_drive=drive,
            selected_product_ids=products,
            install_mode=install_mode,
            sql_version=sql_version,
            sql_instance_name=sql_instance,
            server_target=server_target,
            update_archive_path=update_archive,
            parent=self,
            checkpoint_path=self._review_plan.checkpoint_path if self._review_plan else None,
            resume_installation=self._resume_installation,
            force_new_sql_instance=force_new_sql,
        )
        self.worker.sig_stage_started.connect(self._on_worker_stage_started)
        self.worker.sig_stage_finished.connect(self._on_worker_stage_finished)
        self.worker.sig_progress.connect(self._on_worker_progress)
        self.worker.sig_error.connect(self._on_worker_error)
        self.worker.sig_finished.connect(self._on_worker_finished)
        self.worker.finished.connect(self._on_worker_thread_finished)

        # اضافه کردن لاگر زنده به مینی لاگ (ارسال امن بین تردها)
        logger.add_listener(self._on_new_log_entry)

        self.worker.start()

    def _on_worker_stage_started(self, stage_idx: int, stage_title: str):
        self.page_progress.set_stage_active(stage_idx, stage_title)

    def _on_worker_stage_finished(self, stage_idx: int, success: bool, details: str):
        if success:
            self.page_progress.set_stage_completed(stage_idx, details)
        else:
            self.page_progress.set_stage_failed(stage_idx, details)

    def _on_worker_progress(self, overall_pct: int, stage_pct: int, op_text: str):
        self.page_progress.update_progress(overall_pct, stage_pct, op_text)

    def _on_new_log_entry(self, entry):
        try:
            snippet = f"[{entry.timestamp}] [{entry.stage}] {entry.status} - {entry.message}"
            self.sig_log_received.emit(snippet)
        except Exception:
            pass

    def _on_worker_error(self, stage_id: str, error_details: str, can_retry: bool):
        # دیالوگ و Retry فقط پس از خروج واقعی ترد از run نمایش داده می‌شوند.
        self._pending_install_error = (stage_id, error_details, can_retry)

    def _show_installation_error(self, stage_id: str, error_details: str, can_retry: bool):
        context = {
            "sql_version": self.worker.sql_version if self.worker else "2019",
            "install_mode": self.page_system_check.get_install_mode() if hasattr(self, "page_system_check") else "server",
            "selected_drive": self.page_drive_select.get_selected_drive() if hasattr(self, "page_drive_select") else "",
        }
        err_dialog = ErrorDialog(stage_id, error_details, can_retry=can_retry, can_skip=True, context=context, parent=self)
        err_dialog.retry_requested.connect(self._retry_current_stage)
        err_dialog.skip_requested.connect(self._skip_current_stage)
        err_dialog.view_log_requested.connect(self._show_log_dialog)
        err_dialog.exec()

    def _retry_current_stage(self):
        if not self.worker or self.worker.isRunning() or self.worker.is_cancelled:
            return
        if self.worker.retry_from_stage_idx is None:
            if self.worker.checkpoint_path is None:
                return
        self._pending_install_error = None
        self._install_result = None
        logger.add_listener(self._on_new_log_entry)
        self.worker.start()

    def _skip_current_stage(self):
        if not self.worker or self.worker.isRunning() or self.worker.is_cancelled:
            return
        failed_idx = self.worker.retry_from_stage_idx
        if failed_idx is None:
            return

        self.page_progress.set_stage_skipped(failed_idx, "توسط کاربر صرف‌نظر شد ⏭")
        self.worker.skip_current_stage(failed_idx)

        self._pending_install_error = None
        self._install_result = None
        logger.add_listener(self._on_new_log_entry)
        self.worker.start()

    def _on_worker_finished(self, success: bool, summary):
        self._install_result = (success, summary)

    def _on_worker_thread_finished(self):
        self.worker.wait()
        logger.remove_listener(self._on_new_log_entry)
        if self._close_when_finished:
            self.close()
            return
        if self._pending_install_error:
            error = self._pending_install_error
            self._pending_install_error = None
            self._show_installation_error(*error)
        elif self._install_result and self._install_result[0]:
            self._go_to_final_page()

    def _go_to_final_page(self):
        drive = self.page_drive_select.get_selected_drive()
        products = self.page_product_select.get_selected_products()
        install_mode = self.page_system_check.get_install_mode()
        sql_version = self.worker.sql_version if self.worker else self.page_product_select.get_selected_sql_version()
        sql_instance = self.worker.sql_instance_name if self.worker else (self.page_product_select.get_selected_sql_instance_name() or self.page_system_check.get_sql_instance_name())
        root_dir = Path(f"{drive}\\SEPEHRYAR")

        self.page_final.set_completion_data(
            root_dir,
            products,
            install_mode=install_mode,
            sql_version=sql_version,
            sql_instance=sql_instance,
        )
        tech_name = self.page_system_check.get_technician_name()
        if tech_name:
            self.page_final.set_technician_name(tech_name)
        self.stack.setCurrentIndex(5)
        self._update_navigation_state(5)

    def _show_log_dialog(self):
        dialog = LogViewerDialog(self)
        dialog.exec()

    def _show_troubleshooting_panel(self):
        drive = self.page_drive_select.get_selected_drive() if hasattr(self, "page_drive_select") else ""
        data_dir = Path(f"{drive}\\SEPEHRYAR\\SEPEHRYAR.Data") if drive else None
        dialog = TroubleshootingPanelDialog(data_dir=data_dir, parent=self)
        dialog.exec()
        # بروزرسانی خودکار نتایج پس از انجام اقدامات اصلاحی
        if self.stack.currentIndex() == 0 and self.current_mode == "server":
            self.page_system_check.run_check()

    def closeEvent(self, event):
        cur = self.stack.currentIndex()
        if cur == 4 and self.worker and self.worker.isRunning():
            if self._close_when_finished:
                event.ignore()
                return
            reply = QMessageBox.question(
                self,
                "تأیید خروج",
                "عملیات نصب در حال اجرا است. آیا مطمئن به لغو فرایند و خروج هستید؟",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._close_when_finished = True
                self.action_bar.setEnabled(False)
                self.worker.cancel()
                # مالک QThread تا پایان عملیات جاری زنده می‌ماند.
                event.ignore()
            else:
                event.ignore()
        else:
            event.accept()
