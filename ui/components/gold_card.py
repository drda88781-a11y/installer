# ui/components/gold_card.py
"""
کارت‌های تعاملی و مجلل با تم طلایی جهت نمایش مشخصات سخت‌افزار، انتخاب درایو و محصولات
Luxury Gold Cards for system hardware, drive selection, and product selection
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QCheckBox,
)
from config.settings import THEME_COLORS
from ui.components.status_badge import StatusBadge, BadgeType
from utils.icon_factory import IconFactory
from utils.win_helpers import format_bytes


class GoldCard(QFrame):
    """
    کارت پایه مشکی و زغالی لوکس با حاشیه ظریف
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "GoldCard")
        self.setStyleSheet(f"""
            QFrame.GoldCard {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 12px;
            }}
        """)


class HardwareCheckCard(GoldCard):
    """
    کارت نمایش ردیف‌های بررسی سیستم (RAM, CPU, Arch, Storage, Windows)
    """
    def __init__(self, title: str, detected: str, required: str, passed: bool, icon_name: str, reason: str = None, parent=None):
        super().__init__(parent)
        self._init_ui(title, detected, required, passed, icon_name, reason)

    def _init_ui(self, title: str, detected: str, required: str, passed: bool, icon_name: str, reason: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(16)

        # آیکون سخت‌افزار
        icon_lbl = QLabel(self)
        icon_pix = IconFactory.get_icon(icon_name, size=36).pixmap(36, 36)
        icon_lbl.setPixmap(icon_pix)
        icon_lbl.setFixedSize(40, 40)
        layout.addWidget(icon_lbl)

        # متن‌ها
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        title_lbl = QLabel(title, self)
        title_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 15px; font-weight: bold;")
        info_layout.addWidget(title_lbl)

        val_layout = QHBoxLayout()
        val_layout.setSpacing(16)

        det_lbl = QLabel(f"مقدار شناسایی‌شده: <b style='color:{THEME_COLORS['text_primary']}'>{detected}</b>", self)
        det_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 13px;")
        val_layout.addWidget(det_lbl)

        req_lbl = QLabel(f"الزام: {required}", self)
        req_lbl.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px;")
        val_layout.addWidget(req_lbl)
        val_layout.addStretch()

        info_layout.addLayout(val_layout)

        if reason and not passed:
            reason_lbl = QLabel(reason, self)
            reason_lbl.setStyleSheet(f"color: {THEME_COLORS['error']}; font-size: 12px;")
            info_layout.addWidget(reason_lbl)

        layout.addLayout(info_layout, stretch=1)

        # بج وضعیت
        b_type = BadgeType.SUCCESS if passed else BadgeType.ERROR
        status_text = "✓ مناسب" if passed else "✕ نامناسب"
        badge = StatusBadge(status_text, b_type, self)
        layout.addWidget(badge)


class SelectableDriveCard(GoldCard):
    """
    کارت تعاملی انتخاب درایو هارد دیسک
    """
    clicked = Signal(str)  # drive_letter

    def __init__(self, drive_info, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.drive_info = drive_info
        self.is_selected = is_selected
        self.setCursor(Qt.PointingHandCursor if drive_info.is_eligible else Qt.ForbiddenCursor)
        self._init_ui()
        self.update_style()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(16)

        # آیکون درایو
        icon_lbl = QLabel(self)
        icon_pix = IconFactory.get_icon("drive", size=38).pixmap(38, 38)
        icon_lbl.setPixmap(icon_pix)
        layout.addWidget(icon_lbl)

        # اطلاعات درایو
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        drive_header = QLabel(f"درایو {self.drive_info.letter} ({self.drive_info.mount_point})", self)
        drive_header.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 16px; font-weight: bold;")
        info_layout.addWidget(drive_header)

        space_str = f"فضای کل: {self.drive_info.total_gb} GB  |  مصرف‌شده: {self.drive_info.used_gb} GB  |  فضای آزاد: <b style='color:#FFFFFF'>{self.drive_info.free_gb} GB Free</b>"
        space_lbl = QLabel(space_str, self)
        space_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 13px;")
        info_layout.addWidget(space_lbl)

        if self.drive_info.status_reason:
            reason_lbl = QLabel(self.drive_info.status_reason, self)
            r_color = THEME_COLORS['text_muted'] if self.drive_info.is_eligible else THEME_COLORS['error']
            reason_lbl.setStyleSheet(f"color: {r_color}; font-size: 12px;")
            info_layout.addWidget(reason_lbl)

        layout.addLayout(info_layout, stretch=1)

        # بج وضعیت
        b_type = BadgeType.SUCCESS if self.drive_info.is_eligible else BadgeType.ERROR
        badge = StatusBadge(self.drive_info.status_text, b_type, self)
        layout.addWidget(badge)

    def mousePressEvent(self, event):
        if self.drive_info.is_eligible:
            self.clicked.emit(self.drive_info.letter)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update_style()

    def update_style(self):
        c = THEME_COLORS
        if not self.drive_info.is_eligible:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: #121419;
                    border: 1px solid #1E2129;
                    border-radius: 12px;
                    opacity: 0.6;
                }}
            """)
        elif self.is_selected:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: #1B1E26;
                    border: 2px solid {c['gold_primary']};
                    border-radius: 12px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {c['card_bg']};
                    border: 1px solid {c['card_border']};
                    border-radius: 12px;
                }}
                QFrame:hover {{
                    background-color: {c['card_hover']};
                    border-color: #4A5060;
                }}
            """)


class SelectableProductCard(GoldCard):
    """
    کارت لوکس انتخاب محصول سپهریار با حاشیه طلایی و چک‌باکس چندگانه
    """
    toggled = Signal(str, bool)  # product_id, is_checked

    def __init__(self, product_item, is_checked: bool = True, parent=None):
        super().__init__(parent)
        self.product_item = product_item
        self.is_checked = is_checked
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui()
        self.update_style()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(16)

        # چک باکس شیک
        self.checkbox = QCheckBox(self)
        self.checkbox.setChecked(self.is_checked)
        self.checkbox.setFixedSize(22, 22)
        self.checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border: 2px solid {THEME_COLORS['border_medium']};
                border-radius: 5px;
                background-color: #101217;
            }}
            QCheckBox::indicator:checked {{
                border-color: {THEME_COLORS['gold_primary']};
                background-color: {THEME_COLORS['gold_primary']};
                image: none;
            }}
        """)
        self.checkbox.toggled.connect(self._on_checkbox_toggled)
        layout.addWidget(self.checkbox)

        # ایموجی و نماد محصول
        symbol_lbl = QLabel(self.product_item.icon_symbol, self)
        symbol_lbl.setStyleSheet("font-size: 28px; border: none; background: transparent;")
        symbol_lbl.setFixedSize(40, 40)
        symbol_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(symbol_lbl)

        # مشخصات محصول
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)

        title_lbl = QLabel(self.product_item.title, self)
        title_lbl.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 16px; font-weight: bold;")
        info_layout.addWidget(title_lbl)

        desc_lbl = QLabel(self.product_item.description, self)
        desc_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 13px;")
        info_layout.addWidget(desc_lbl)

        folder_str = f"پوشه پکیج: <span style='color:{THEME_COLORS['gold_hover']}'>{self.product_item.folder_name}</span>  |  فایل اصلی: <span style='color:#CBD5E1'>{self.product_item.main_exe}</span>"
        folder_lbl = QLabel(folder_str, self)
        folder_lbl.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px;")
        info_layout.addWidget(folder_lbl)

        layout.addLayout(info_layout, stretch=1)

        # برچسب حجم پکیج
        size_text = format_bytes(self.product_item.size_bytes)
        size_lbl = QLabel(size_text, self)
        size_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 13px; font-weight: bold;")
        layout.addWidget(size_lbl)

    def mousePressEvent(self, event):
        self.checkbox.setChecked(not self.checkbox.isChecked())
        super().mousePressEvent(event)

    def _on_checkbox_toggled(self, checked: bool):
        self.is_checked = checked
        self.update_style()
        self.toggled.emit(self.product_item.id, checked)

    def update_style(self):
        c = THEME_COLORS
        if self.is_checked:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: #191C24;
                    border: 2px solid {c['gold_primary']};
                    border-radius: 12px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {c['card_bg']};
                    border: 1px solid {c['card_border']};
                    border-radius: 12px;
                }}
                QFrame:hover {{
                    background-color: {c['card_hover']};
                    border-color: #4A5060;
                }}
            """)


class ModeSelectionCard(GoldCard):
    """
    کارت تعاملی انتخاب نوع استقرار: سرور یا کلاینت
    """
    clicked = Signal(str)  # mode

    def __init__(self, mode: str, title: str, subtitle: str, desc: str, icon_name: str, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.title_text = title
        self.subtitle_text = subtitle
        self.desc_text = desc
        self.icon_name = icon_name
        self.is_active = is_active
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui()
        self.set_active(is_active)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # ردیف بالا: آیکون و عنوان
        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        self.icon_lbl = QLabel(self)
        top_layout.addWidget(self.icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        self.lbl_title = QLabel(self.title_text, self)
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        title_vbox.addWidget(self.lbl_title)

        self.lbl_sub = QLabel(self.subtitle_text, self)
        self.lbl_sub.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11px;")
        title_vbox.addWidget(self.lbl_sub)

        top_layout.addLayout(title_vbox, stretch=1)

        # نشانگر انتخاب (رادیو / تیک)
        self.badge_lbl = QLabel(self)
        self.badge_lbl.setAlignment(Qt.AlignCenter)
        self.badge_lbl.setFixedSize(22, 22)
        top_layout.addWidget(self.badge_lbl)

        layout.addLayout(top_layout)

        # توضیحات تفصیلی
        desc_lbl = QLabel(self.desc_text, self)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 11.5px; line-height: 1.4;")
        layout.addWidget(desc_lbl)

    def set_active(self, active: bool):
        self.is_active = active
        c = THEME_COLORS
        if active:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: #1A1E29;
                    border: 2px solid {c['gold_primary']};
                    border-radius: 12px;
                }}
            """)
            self.lbl_title.setStyleSheet(f"color: {c['gold_hover']}; font-size: 14px; font-weight: bold;")
            icon_pix = IconFactory.get_icon(self.icon_name, size=30, color_override=c["gold_primary"]).pixmap(30, 30)
            self.icon_lbl.setPixmap(icon_pix)
            self.badge_lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {c['gold_primary']};
                    color: #0E1015;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 11px;
                }}
            """)
            self.badge_lbl.setText("✓")
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {c['card_bg']};
                    border: 1px solid {c['card_border']};
                    border-radius: 12px;
                }}
                QFrame:hover {{
                    background-color: {c['card_hover']};
                    border-color: #4A5060;
                }}
            """)
            self.lbl_title.setStyleSheet(f"color: {c['text_primary']}; font-size: 14px; font-weight: bold;")
            icon_pix = IconFactory.get_icon(self.icon_name, size=30, color_override=c["text_muted"]).pixmap(30, 30)
            self.icon_lbl.setPixmap(icon_pix)
            self.badge_lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: #1A1D24;
                    border: 1px solid #3A4050;
                    border-radius: 11px;
                }}
            """)
            self.badge_lbl.setText("")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.mode)
        super().mousePressEvent(event)


class SQLVersionSelectionCard(GoldCard):
    """
    کارت تعاملی انتخاب نسخه SQL Server: ۲۰۱۴ یا ۲۰۱۹
    """
    clicked = Signal(str)  # "2014" or "2019"

    def __init__(
        self,
        version: str,
        title: str,
        subtitle: str,
        desc: str,
        time_badge: str,
        icon_name: str = "database",
        is_active: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.version = version
        self.title_text = title
        self.subtitle_text = subtitle
        self.desc_text = desc
        self.time_badge_text = time_badge
        self.icon_name = icon_name
        self.is_active = is_active
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui()
        self.set_active(is_active)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # ردیف بالا: آیکون، عنوان و بج زمان
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        self.icon_lbl = QLabel(self)
        top_layout.addWidget(self.icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        self.lbl_title = QLabel(self.title_text, self)
        self.lbl_title.setStyleSheet("font-size: 13.5px; font-weight: bold;")
        title_vbox.addWidget(self.lbl_title)

        self.lbl_sub = QLabel(self.subtitle_text, self)
        self.lbl_sub.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11px;")
        title_vbox.addWidget(self.lbl_sub)

        top_layout.addLayout(title_vbox, stretch=1)

        # بج زمان
        time_lbl = QLabel(self.time_badge_text, self)
        time_lbl.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(216, 168, 78, 0.12);
                color: {THEME_COLORS['gold_hover']};
                border: 1px solid rgba(216, 168, 78, 0.3);
                border-radius: 6px;
                padding: 3px 7px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        top_layout.addWidget(time_lbl)

        # نشانگر انتخاب (تیک)
        self.badge_lbl = QLabel(self)
        self.badge_lbl.setAlignment(Qt.AlignCenter)
        self.badge_lbl.setFixedSize(20, 20)
        top_layout.addWidget(self.badge_lbl)

        layout.addLayout(top_layout)

        # توضیحات تفصیلی
        desc_lbl = QLabel(self.desc_text, self)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 11.5px; line-height: 1.3;")
        layout.addWidget(desc_lbl)

    def set_active(self, active: bool):
        self.is_active = active
        c = THEME_COLORS
        if active:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: #1A1E29;
                    border: 2px solid {c['gold_primary']};
                    border-radius: 12px;
                }}
            """)
            self.lbl_title.setStyleSheet(f"color: {c['gold_hover']}; font-size: 13.5px; font-weight: bold;")
            icon_pix = IconFactory.get_icon(self.icon_name, size=26, color_override=c["gold_primary"]).pixmap(26, 26)
            self.icon_lbl.setPixmap(icon_pix)
            self.badge_lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {c['gold_primary']};
                    color: #0E1015;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 10px;
                }}
            """)
            self.badge_lbl.setText("✓")
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {c['card_bg']};
                    border: 1px solid {c['card_border']};
                    border-radius: 12px;
                }}
                QFrame:hover {{
                    background-color: {c['card_hover']};
                    border-color: #4A5060;
                }}
            """)
            self.lbl_title.setStyleSheet(f"color: {c['text_primary']}; font-size: 13.5px; font-weight: bold;")
            icon_pix = IconFactory.get_icon(self.icon_name, size=26, color_override=c["text_muted"]).pixmap(26, 26)
            self.icon_lbl.setPixmap(icon_pix)
            self.badge_lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: #1A1D24;
                    border: 1px solid #3A4050;
                    border-radius: 10px;
                }}
            """)
            self.badge_lbl.setText("")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.version)
        super().mousePressEvent(event)

