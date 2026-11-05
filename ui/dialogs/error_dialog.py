# ui/dialogs/error_dialog.py
"""
دیالوگ خطای عملیاتی پیشرفته مجهز به موتور پلن حل مشکل و عیب‌یابی خودکار
Advanced operational error dialog with Actionable Troubleshooting Plan & Auto-Remediation
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from ai.troubleshooting_plan import TroubleshootingPlan, TroubleshootingPlanEngine
from config.settings import THEME_COLORS
from utils.icon_factory import IconFactory


class ErrorDialog(QDialog):
    """
    نمایش خطای مرحله همراه با پلن تخصصی و گام‌به‌گام رفع عیب برای تکنسین
    """
    retry_requested = Signal()
    skip_requested = Signal()
    view_log_requested = Signal()

    def __init__(
        self,
        stage_title: str,
        error_details: str,
        can_retry: bool = True,
        can_skip: bool = True,
        context: dict = None,
        parent=None,
    ):
        super().__init__(parent)
        self.stage_title = stage_title
        self.error_details = error_details
        self.can_retry = can_retry
        self.can_skip = can_skip
        self.context = context or {}
        self.plan: TroubleshootingPlan = TroubleshootingPlanEngine.generate_plan(
            stage_id=stage_title,
            error_details=error_details,
            context=self.context,
        )

        self.setWindowTitle("خطای عملیاتی نصب و پلن حل مشکل")
        self.resize(720, 520)
        self.setMinimumSize(640, 440)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # سربرگ خطا
        top_layout = QHBoxLayout()
        top_layout.setSpacing(14)

        icon_lbl = QLabel(self)
        icon_pix = IconFactory.get_icon("cross", size=32).pixmap(32, 32)
        icon_lbl.setPixmap(icon_pix)
        top_layout.addWidget(icon_lbl)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        main_title = QLabel("توقف عملیات نصب - پلن حل مشکل آماده است", self)
        main_title.setStyleSheet(f"color: {THEME_COLORS['error']}; font-size: 17px; font-weight: bold;")
        title_layout.addWidget(main_title)

        stage_lbl = QLabel(f"مرحله: <b style='color:#FFFFFF'>{self.stage_title}</b> | موضوع: <span style='color:{THEME_COLORS['gold_hover']}'>{self.plan.error_summary}</span>", self)
        stage_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 13px;")
        title_layout.addWidget(stage_lbl)

        top_layout.addLayout(title_layout, stretch=1)
        main_layout.addLayout(top_layout)

        # تب‌های نمایش: تب ۱ پلن حل مشکل - تب ۲ متن خام لاگ/خطا
        tabs = QTabWidget(self)
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 8px;
                background-color: {THEME_COLORS['card_bg']};
            }}
            QTabBar::tab {{
                background-color: #12141A;
                color: {THEME_COLORS['text_secondary']};
                padding: 8px 18px;
                margin-left: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                background-color: {THEME_COLORS['card_bg']};
                color: {THEME_COLORS['gold_hover']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-bottom: none;
            }}
        """)

        # ─── تب ۱: پلن حل مشکل ───
        plan_tab = QWidget()
        plan_vbox = QVBoxLayout(plan_tab)
        plan_vbox.setContentsMargins(16, 14, 16, 14)
        plan_vbox.setSpacing(12)

        # کارت علت ریشه‌ای
        cause_card = QFrame(plan_tab)
        cause_card.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(239, 68, 68, 0.08);
                border-left: 3px solid {THEME_COLORS['error']};
                border-radius: 6px;
                padding: 4px;
            }}
        """)
        cause_layout = QVBoxLayout(cause_card)
        cause_layout.setContentsMargins(10, 8, 10, 8)
        lbl_cause_h = QLabel("🔍 تحلیل علت ریشه‌ای خطا:", cause_card)
        lbl_cause_h.setStyleSheet(f"color: {THEME_COLORS['error']}; font-size: 12.5px; font-weight: bold;")
        lbl_cause_b = QLabel(self.plan.root_cause_fa, cause_card)
        lbl_cause_b.setWordWrap(True)
        lbl_cause_b.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 12px; line-height: 1.5;")
        cause_layout.addWidget(lbl_cause_h)
        cause_layout.addWidget(lbl_cause_b)
        plan_vbox.addWidget(cause_card)

        # مراحل اقدام تکنسین
        lbl_steps_h = QLabel("📋 پلن اقدام و مراحل حل گام‌به‌گام:", plan_tab)
        lbl_steps_h.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 12.5px; font-weight: bold;")
        plan_vbox.addWidget(lbl_steps_h)

        steps_card = QFrame(plan_tab)
        steps_card.setStyleSheet(f"""
            QFrame {{
                background-color: #101218;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
            }}
        """)
        steps_layout = QVBoxLayout(steps_card)
        steps_layout.setContentsMargins(12, 10, 12, 10)
        steps_layout.setSpacing(6)
        for s in self.plan.action_steps:
            st_lbl = QLabel(s, steps_card)
            st_lbl.setWordWrap(True)
            st_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12px; line-height: 1.4;")
            steps_layout.addWidget(st_lbl)
        plan_vbox.addWidget(steps_card)

        # دستورات آماده خط فرمان
        if self.plan.powershell_commands:
            lbl_cmd_h = QLabel("⚡ دستور خط فرمان جهت رفع سریع (PowerShell):", plan_tab)
            lbl_cmd_h.setStyleSheet(f"color: #38BDF8; font-size: 12px; font-weight: bold;")
            plan_vbox.addWidget(lbl_cmd_h)

            cmd_box = QHBoxLayout()
            cmd_box.setSpacing(8)

            cmd_str = "; ".join(self.plan.powershell_commands)
            self.txt_cmd = QTextEdit(plan_tab)
            self.txt_cmd.setReadOnly(True)
            self.txt_cmd.setFixedHeight(48)
            self.txt_cmd.setPlainText(cmd_str)
            self.txt_cmd.setStyleSheet("""
                QTextEdit {
                    background-color: #0A0C10;
                    color: #38BDF8;
                    border: 1px solid #1E293B;
                    border-radius: 6px;
                    padding: 6px;
                    font-family: Consolas, monospace;
                    font-size: 11.5px;
                }
            """)
            cmd_box.addWidget(self.txt_cmd, stretch=1)

            btn_copy_cmd = QPushButton("کپی دستور", plan_tab)
            btn_copy_cmd.setProperty("class", "GoldSecondary")
            btn_copy_cmd.setFixedHeight(48)
            btn_copy_cmd.setIcon(IconFactory.get_icon("copy", size=14))
            btn_copy_cmd.clicked.connect(self._copy_command)
            cmd_box.addWidget(btn_copy_cmd)
            plan_vbox.addLayout(cmd_box)

        tabs.addTab(plan_tab, "پلن حل مشکل و راهنمای تکنسین")

        # ─── تب ۲: جزئیات خام خطا ───
        raw_tab = QWidget()
        raw_vbox = QVBoxLayout(raw_tab)
        raw_vbox.setContentsMargins(14, 12, 14, 12)
        err_box = QTextEdit(raw_tab)
        err_box.setReadOnly(True)
        err_box.setPlainText(self.error_details)
        err_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0E1015;
                color: #F87171;
                border: 1px solid {THEME_COLORS['error']};
                border-radius: 6px;
                padding: 10px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }}
        """)
        raw_vbox.addWidget(err_box)
        tabs.addTab(raw_tab, "جزئیات فنی خطا (Stack Trace)")

        main_layout.addWidget(tabs, stretch=1)

        # نوار دکمه‌های پایین
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_log = QPushButton("مشاهده لاگ کامل", self)
        btn_log.setProperty("class", "GoldSecondary")
        btn_log.setIcon(IconFactory.get_icon("log", size=16))
        btn_log.clicked.connect(self._on_view_log)
        btn_layout.addWidget(btn_log)

        btn_panel = QPushButton("مرکز جامع عیب‌یابی...", self)
        btn_panel.setProperty("class", "GoldSecondary")
        btn_panel.setIcon(IconFactory.get_icon("gear", size=15))
        btn_panel.clicked.connect(self._open_troubleshooting_panel)
        btn_layout.addWidget(btn_panel)

        btn_layout.addStretch()

        # دکمه رفع خودکار
        if self.plan.can_auto_repair:
            self.btn_auto_repair = QPushButton(self.plan.repair_action_title, self)
            self.btn_auto_repair.setProperty("class", "GoldSecondary")
            self.btn_auto_repair.setIcon(IconFactory.get_icon("gear", size=15))
            self.btn_auto_repair.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(216, 168, 78, 0.15);
                    color: {THEME_COLORS['gold_hover']};
                    border: 1px solid {THEME_COLORS['gold_primary']};
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 12.5px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: rgba(216, 168, 78, 0.28);
                }}
            """)
            self.btn_auto_repair.clicked.connect(self._on_auto_repair)
            btn_layout.addWidget(self.btn_auto_repair)

        if self.can_retry:
            btn_retry = QPushButton("تلاش مجدد", self)
            btn_retry.setProperty("class", "GoldPrimary")
            btn_retry.setIcon(IconFactory.get_icon("refresh", size=16, color_override="#000000"))
            btn_retry.clicked.connect(self._on_retry)
            btn_layout.addWidget(btn_retry)

        if self.can_skip:
            btn_skip = QPushButton("صرف‌نظر و ادامه نصب ⏭", self)
            btn_skip.setProperty("class", "GoldSecondary")
            btn_skip.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(245, 158, 11, 0.15);
                    color: #FBBF24;
                    border: 1px solid #F59E0B;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 12.5px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: rgba(245, 158, 11, 0.32);
                    color: #FDE68A;
                }}
            """)
            btn_skip.clicked.connect(self._on_skip)
            btn_layout.addWidget(btn_skip)

        btn_cancel = QPushButton("بستن", self)
        btn_cancel.setProperty("class", "GoldSecondary")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        main_layout.addLayout(btn_layout)

    def _copy_command(self):
        cmd = self.txt_cmd.toPlainText().strip()
        if cmd:
            clipboard = QApplication.clipboard()
            clipboard.setText(cmd)
            QMessageBox.information(self, "کپی دستور", "دستور خط فرمان در کلیپ‌بورد کپی شد. می‌توانید در PowerShell اجرا فرمایید.")

    def _on_auto_repair(self):
        self.btn_auto_repair.setEnabled(False)
        self.btn_auto_repair.setText("در حال رفع مشکل...")
        ok, msg = TroubleshootingPlanEngine.execute_auto_repair(self.plan, self.context)
        if ok:
            QMessageBox.information(self, "عملیات رفع عیب خودکار", f"{msg}\n\nاکنون برای ادامه، کلید «تلاش مجدد» را بزنید.")
            self.btn_auto_repair.setText("رفع عیب انجام شد ✓")
        else:
            QMessageBox.warning(self, "رفع عیب خودکار", msg)
            self.btn_auto_repair.setText(self.plan.repair_action_title)
            self.btn_auto_repair.setEnabled(True)

    def _on_retry(self):
        self.retry_requested.emit()
        self.accept()

    def _on_skip(self):
        self.skip_requested.emit()
        self.accept()

    def _on_view_log(self):
        self.view_log_requested.emit()

    def _open_troubleshooting_panel(self):
        from ui.dialogs.troubleshooting_panel import TroubleshootingPanelDialog
        data_dir = self.context.get("data_dir")
        dlg = TroubleshootingPanelDialog(data_dir=data_dir, parent=self)
        dlg.exec()
