"""Review the exact destination, products and database changes before installation."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout

from config.settings import PRODUCTS_CONFIG
from utils.win_helpers import format_bytes


class InstallReviewDialog(QDialog):
    def __init__(self, plan, parent=None):
        super().__init__(parent)
        self.setWindowTitle("بررسی نهایی عملیات نصب")
        self.resize(740, 550)
        layout = QVBoxLayout(self)
        title = QLabel("خلاصه نصب و تغییرات", self)
        layout.addWidget(title)
        lines = [f"مسیر نصب: {plan.root}",
                 "محصولات: " + "، ".join(PRODUCTS_CONFIG[p]["title"] for p in plan.products),
                 f"نوع نصب: {'سرور' if plan.mode == 'server' else 'کلاینت'}",
                 f"پایگاه داده / سرور: {plan.sql_description}",
                 f"حداقل فضای فایل‌ها و بک‌آپ برنامه: {format_bytes(plan.minimum_bytes)}",
                 f"فضای آزاد درایو: {format_bytes(plan.available_bytes)}",
                 f"بسته آپدیت: {plan.update_version or 'بدون آپدیت؛ نصب نسخه پایه'}",
                 "دیتابیس‌های هدف آپدیت: " + ("، ".join(plan.database_names) or "ندارد"),
                 "", "برنامه‌های انتخاب‌شده پیش از جایگزینی فایل‌ها بسته می‌شوند.",
                 "پیش از تغییر فایل‌های موجود و پچ دیتابیس، بک‌آپ تأییدشده ساخته می‌شود.",
                 "تنظیمات و فایل‌های مجوز موجود حفظ می‌شوند.",
                 "فضای دانلود SQL و بک‌آپ دیتابیس به حجم واقعی آن‌ها بستگی دارد."]
        if plan.errors:
            lines += ["", "مواردی که باید رفع شوند:"] + plan.errors
        text = QPlainTextEdit(self)
        text.setReadOnly(True)
        text.setPlainText("\n".join(lines))
        layout.addWidget(text)
        self.resume = QCheckBox("ادامه نصب قبلی پس از بررسی سلامت مراحل انجام‌شده", self)
        self.resume.setVisible(plan.resume_available)
        self.resume.setChecked(plan.resume_available)
        layout.addWidget(self.resume)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.button(QDialogButtonBox.Ok).setText("شروع نصب")
        buttons.button(QDialogButtonBox.Ok).setEnabled(not plan.errors)
        buttons.button(QDialogButtonBox.Cancel).setText("بازگشت")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayoutDirection(Qt.RightToLeft)
