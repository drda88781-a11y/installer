# ui/pages/page_progress.py
"""
صفحه ۴: داشبورد پیشرفته و مانیتورینگ زنده فرایند نصب سپهریار
Page 4: Real-time Installation Dashboard and Progress Monitor
"""

from typing import Dict, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from config.settings import THEME_COLORS
from core.orchestrator import InstallStage, get_install_stages_for_products, get_default_install_stages
from ui.components.animated_progress import LuxuryProgressBar
from utils.icon_factory import IconFactory


class ProgressStageItem(QFrame):
    """
    ردیف نمایش هر یک از مراحل داخلی پایپ‌لاین در داشبورد
    """
    def __init__(self, stage_id: str, title: str, parent=None):
        super().__init__(parent)
        self.stage_id = stage_id
        self.title = title
        self._init_ui()
        self.set_state("pending", "")

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        # نشانگر وضعیت (چک مارک، دایره در حال کار یا خاکستری)
        self.icon_lbl = QLabel(self)
        self.icon_lbl.setFixedSize(20, 20)
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_lbl)

        # عنوان مرحله
        self.title_lbl = QLabel(self.title, self)
        self.title_lbl.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.title_lbl, stretch=1)

        # جزئیات وضعیت جاری
        self.detail_lbl = QLabel("", self)
        self.detail_lbl.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(self.detail_lbl)

    def set_state(self, state: str, details: str = ""):
        c = THEME_COLORS
        if details:
            self.detail_lbl.setText(details)

        if state == "completed":
            pix = IconFactory.get_icon("check", size=16, color_override=c["gold_primary"]).pixmap(16, 16)
            self.icon_lbl.setPixmap(pix)
            self.title_lbl.setStyleSheet(f"color: {c['gold_hover']}; font-size: 14px; font-weight: 600;")
            self.setStyleSheet("QFrame { background-color: #12151C; border-radius: 6px; }")

        elif state == "active":
            # دایره فعال طلایی
            pix = IconFactory.get_icon("refresh", size=16, color_override=c["gold_primary"]).pixmap(16, 16)
            self.icon_lbl.setPixmap(pix)
            self.title_lbl.setStyleSheet(f"color: #FFFFFF; font-size: 14px; font-weight: bold;")
            self.setStyleSheet(f"QFrame {{ background-color: #191D26; border: 1px solid {c['gold_primary']}; border-radius: 6px; }}")

        elif state == "failed":
            pix = IconFactory.get_icon("cross", size=16, color_override=c["error"]).pixmap(16, 16)
            self.icon_lbl.setPixmap(pix)
            self.title_lbl.setStyleSheet(f"color: {c['error']}; font-size: 14px; font-weight: bold;")
            self.setStyleSheet(f"QFrame {{ background-color: #1E1214; border: 1px solid {c['error']}; border-radius: 6px; }}")

        elif state in ("skipped", "warning"):
            pix = IconFactory.get_icon("warning", size=16, color_override=c.get("warning", "#F59E0B")).pixmap(16, 16)
            self.icon_lbl.setPixmap(pix)
            self.title_lbl.setStyleSheet("color: #FBBF24; font-size: 14px; font-weight: bold;")
            self.setStyleSheet("QFrame { background-color: #241C12; border: 1px solid #B45309; border-radius: 6px; }")

        else:  # pending
            pix = IconFactory.get_icon("circle", size=12, color_override=c["text_muted"]).pixmap(12, 12)
            self.icon_lbl.setPixmap(pix)
            self.title_lbl.setStyleSheet(f"color: {c['text_muted']}; font-size: 14px;")
            self.setStyleSheet("QFrame { background: transparent; }")


class ProgressDashboardPage(QWidget):
    """
    داشبورد اصلی مانیتورینگ زنده مراحل نصب سپهریار
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stage_widgets: Dict[str, ProgressStageItem] = {}
        self.current_stages: List[InstallStage] = []
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 20)
        main_layout.setSpacing(16)

        # سربرگ داشبورد
        header_lbl = QLabel("در حال نصب نرم‌افزار سپهریار", self)
        header_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 24px; font-weight: bold;")
        main_layout.addWidget(header_lbl)

        # نوار پروگرس لوکس
        self.progress_bar = LuxuryProgressBar(self)
        main_layout.addWidget(self.progress_bar)

        # چک‌لیست مراحل در کادر اسکرول
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.stages_container = QWidget()
        self.stages_container.setStyleSheet("background: transparent;")
        self.stages_layout = QVBoxLayout(self.stages_container)
        self.stages_layout.setContentsMargins(0, 4, 0, 4)
        self.stages_layout.setSpacing(8)

        # مقداردهی اولیه مراحل (پیکربندی کامل هنگام شروع نصب انجام می‌شود)
        self.configure_stages([])

        scroll.setWidget(self.stages_container)
        main_layout.addWidget(scroll, stretch=1)

        # پیش‌نمایش زنده لاگ (مینی کنسول)
        log_frame = QFrame(self)
        log_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #0E1015;
                border: 1px solid {THEME_COLORS['border_subtle']};
                border-radius: 8px;
            }}
        """)
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(10, 8, 10, 8)
        log_layout.setSpacing(4)

        log_title = QLabel("آخرین رویدادهای سیستمی:", log_frame)
        log_title.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 11px; font-weight: bold;")
        log_layout.addWidget(log_title)

        self.mini_log = QPlainTextEdit(log_frame)
        self.mini_log.setReadOnly(True)
        self.mini_log.setFixedHeight(75)
        self.mini_log.setStyleSheet("border: none; background: transparent; font-size: 11px; padding: 0px;")
        log_layout.addWidget(self.mini_log)

        main_layout.addWidget(log_frame)

    def configure_stages(self, selected_product_ids: List[str], install_mode: str = "server", sql_version: str = "2019", has_update: bool = False):
        """تنظیم داینامیک ویجت‌های مراحل بر مبنای نوع نصب (سرور یا کلاینت)، پکیج‌ها، نسخه SQL و وضعیت آپدیت"""
        while self.stages_layout.count():
            item = self.stages_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.stage_widgets.clear()
        self.current_stages = get_install_stages_for_products(
            selected_product_ids,
            install_mode=install_mode,
            sql_version=str(sql_version),
            has_update=has_update,
        )

        for st in self.current_stages:
            item = ProgressStageItem(st.id, st.title_fa, self.stages_container)
            self.stage_widgets[st.id] = item
            self.stages_layout.addWidget(item)

        self.stages_layout.addStretch()

    def update_progress(self, overall_percent: int, stage_percent: int, operation_text: str):
        self.progress_bar.set_progress(overall_percent, operation_text, f"پیشرفت مرحله جاری: {stage_percent}%")

    def set_stage_active(self, stage_idx: int, stage_title: str):
        if 0 <= stage_idx < len(self.current_stages):
            st_id = self.current_stages[stage_idx].id
            if st_id in self.stage_widgets:
                self.stage_widgets[st_id].set_state("active", "در حال اجرا...")

    def set_stage_completed(self, stage_idx: int, details: str = ""):
        if 0 <= stage_idx < len(self.current_stages):
            st_id = self.current_stages[stage_idx].id
            if st_id in self.stage_widgets:
                self.stage_widgets[st_id].set_state("completed", details or "تکمیل شد ✓")

    def set_stage_failed(self, stage_idx: int, error_details: str = ""):
        if 0 <= stage_idx < len(self.current_stages):
            st_id = self.current_stages[stage_idx].id
            if st_id in self.stage_widgets:
                self.stage_widgets[st_id].set_state("failed", error_details or "خطا در اجرا ✕")

    def set_stage_skipped(self, stage_idx: int, details: str = ""):
        if 0 <= stage_idx < len(self.current_stages):
            st_id = self.current_stages[stage_idx].id
            if st_id in self.stage_widgets:
                self.stage_widgets[st_id].set_state("skipped", details or "صرف‌نظر شد ⏭")

    def append_log_snippet(self, text: str):
        self.mini_log.appendPlainText(text)
        self.mini_log.verticalScrollBar().setValue(self.mini_log.verticalScrollBar().maximum())

    def reset(self):
        self.progress_bar.set_progress(0, "آماده‌سازی...", "")
        self.mini_log.clear()
        for w in self.stage_widgets.values():
            w.set_state("pending", "")
