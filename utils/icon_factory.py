# utils/icon_factory.py
"""
تولیدکننده آیکون‌های برداری و باکیفیت بالا (High-DPI) بر مبنای پالت مشکی و طلایی
Vector and programmatic high-DPI icon generator with Gold & Charcoal theme
"""

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QIcon,
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QPainterPath,
)

from config.settings import THEME_COLORS


class IconFactory:
    """
    تولیدکننده مرکزی آیکون‌های مدرن با رندر وکتور و پشتیبانی از رزولوشن‌های رتینا
    """
    @staticmethod
    def get_icon(name: str, size: int = 32, color_override: str = None) -> QIcon:
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        gold_color = QColor(color_override or THEME_COLORS["gold_primary"])
        bg_card = QColor(THEME_COLORS["card_bg"])

        w = float(size)
        h = float(size)
        center = QPointF(w / 2.0, h / 2.0)

        if name == "check":
            # چک مارک طلایی / سبز
            c = QColor(color_override or THEME_COLORS["success"])
            pen = QPen(c, max(2.5, w * 0.09), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(w * 0.22, h * 0.52)
            path.lineTo(w * 0.42, h * 0.72)
            path.lineTo(w * 0.78, h * 0.28)
            painter.drawPath(path)

        elif name == "cross":
            # ضربدر قرمز / ارور
            c = QColor(color_override or THEME_COLORS["error"])
            pen = QPen(c, max(2.5, w * 0.09), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(w * 0.28, h * 0.28)
            path.lineTo(w * 0.72, h * 0.72)
            path.moveTo(w * 0.72, h * 0.28)
            path.lineTo(w * 0.28, h * 0.72)
            painter.drawPath(path)

        elif name == "warning":
            # مثلث هشدار طلایی/کهربایی
            c = QColor(color_override or THEME_COLORS["warning"])
            pen = QPen(c, max(2.0, w * 0.07), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(w * 0.5, h * 0.18)
            path.lineTo(w * 0.84, h * 0.80)
            path.lineTo(w * 0.16, h * 0.80)
            path.closeSubpath()
            painter.drawPath(path)
            # علامت تعجب
            painter.drawLine(int(w * 0.5), int(h * 0.40), int(w * 0.5), int(h * 0.60))
            painter.drawPoint(int(w * 0.5), int(h * 0.70))

        elif name == "ram":
            # تراشه حافظه RAM
            pen = QPen(gold_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            # بدنه رم
            rect = QRectF(w * 0.15, h * 0.35, w * 0.70, h * 0.30)
            painter.drawRoundedRect(rect, 3, 3)
            # پین‌های پایینی
            for i in range(5):
                x = w * (0.25 + i * 0.12)
                painter.drawLine(QPointF(x, h * 0.65), QPointF(x, h * 0.78))
            # چیپ‌های روی رم
            painter.setBrush(QBrush(gold_color))
            painter.drawRect(QRectF(w * 0.25, h * 0.42, w * 0.12, h * 0.16))
            painter.drawRect(QRectF(w * 0.44, h * 0.42, w * 0.12, h * 0.16))
            painter.drawRect(QRectF(w * 0.63, h * 0.42, w * 0.12, h * 0.16))

        elif name == "cpu":
            # پردازنده CPU
            pen = QPen(gold_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            # بدنه مرکزی
            painter.drawRoundedRect(QRectF(w * 0.25, h * 0.25, w * 0.50, h * 0.50), 4, 4)
            # پین‌های بیرونی
            for i in range(3):
                offset = 0.35 + i * 0.15
                painter.drawLine(QPointF(w * offset, h * 0.12), QPointF(w * offset, h * 0.25))
                painter.drawLine(QPointF(w * offset, h * 0.75), QPointF(w * offset, h * 0.88))
                painter.drawLine(QPointF(w * 0.12, h * offset), QPointF(w * 0.25, h * offset))
                painter.drawLine(QPointF(w * 0.75, h * offset), QPointF(w * 0.88, h * offset))
            # هسته داخلی
            painter.setBrush(QBrush(gold_color))
            painter.drawRect(QRectF(w * 0.40, h * 0.40, w * 0.20, h * 0.20))

        elif name == "arch":
            # معماری 64 بیت
            pen = QPen(gold_color, 2.0)
            painter.setPen(pen)
            painter.drawRoundedRect(QRectF(w * 0.12, h * 0.18, w * 0.76, h * 0.64), 6, 6)
            font = QFont("Arial", int(w * 0.26), QFont.Bold)
            painter.setFont(font)
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "64")

        elif name == "storage" or name == "drive":
            # دیسک سخت HDD/SSD
            pen = QPen(gold_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawRoundedRect(QRectF(w * 0.18, h * 0.20, w * 0.64, h * 0.60), 6, 6)
            # پلاتر دیسک
            painter.drawEllipse(QPointF(w * 0.50, h * 0.46), w * 0.18, h * 0.18)
            painter.drawPoint(QPointF(w * 0.50, h * 0.46))
            # LED وضعیت
            painter.drawEllipse(QPointF(w * 0.68, h * 0.70), w * 0.03, h * 0.03)

        elif name == "windows":
            # آیکون ویندوز ۴ تکه
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(gold_color))
            gap = w * 0.05
            half = (w * 0.65 - gap) / 2.0
            x1 = w * 0.18
            x2 = x1 + half + gap
            y1 = h * 0.18
            y2 = y1 + half + gap
            painter.drawRoundedRect(QRectF(x1, y1, half, half), 2, 2)
            painter.drawRoundedRect(QRectF(x2, y1, half, half), 2, 2)
            painter.drawRoundedRect(QRectF(x1, y2, half, half), 2, 2)
            painter.drawRoundedRect(QRectF(x2, y2, half, half), 2, 2)

        elif name == "database" or name == "sql":
            # سیلندر دیتابیس SQL
            pen = QPen(gold_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            # دیسک بالایی
            painter.drawEllipse(QPointF(w * 0.50, h * 0.28), w * 0.30, h * 0.10)
            # بدنه و دیسک وسط
            painter.drawArc(QRectF(w * 0.20, h * 0.40, w * 0.60, h * 0.20), 0, -180 * 16)
            # بدنه و دیسک پایین
            painter.drawArc(QRectF(w * 0.20, h * 0.60, w * 0.60, h * 0.20), 0, -180 * 16)
            # خطوط عمودی بغل
            painter.drawLine(QPointF(w * 0.20, h * 0.28), QPointF(w * 0.20, h * 0.70))
            painter.drawLine(QPointF(w * 0.80, h * 0.28), QPointF(w * 0.80, h * 0.70))

        elif name == "shield":
            # سپر امنیتی ادمین
            pen = QPen(gold_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(w * 0.50, h * 0.18)
            path.lineTo(w * 0.80, h * 0.30)
            path.quadTo(w * 0.80, h * 0.65, w * 0.50, h * 0.82)
            path.quadTo(w * 0.20, h * 0.65, w * 0.20, h * 0.30)
            path.closeSubpath()
            painter.drawPath(path)

        elif name == "refresh" or name == "retry":
            # فلش چرخان رفرش/تلاش مجدد
            pen = QPen(gold_color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawArc(QRectF(w * 0.20, h * 0.20, w * 0.60, h * 0.60), 45 * 16, 270 * 16)
            # نوک پیکان
            path = QPainterPath()
            path.moveTo(w * 0.50, h * 0.12)
            path.lineTo(w * 0.64, h * 0.20)
            path.lineTo(w * 0.50, h * 0.28)
            painter.drawPath(path)

        elif name == "log":
            # دفترچه لاگ و گزارش
            pen = QPen(gold_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawRoundedRect(QRectF(w * 0.22, h * 0.16, w * 0.56, h * 0.68), 4, 4)
            painter.drawLine(QPointF(w * 0.34, h * 0.32), QPointF(w * 0.66, h * 0.32))
            painter.drawLine(QPointF(w * 0.34, h * 0.48), QPointF(w * 0.66, h * 0.48))
            painter.drawLine(QPointF(w * 0.34, h * 0.64), QPointF(w * 0.54, h * 0.64))

        elif name == "folder":
            # پوشه
            pen = QPen(gold_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(w * 0.18, h * 0.32)
            path.lineTo(w * 0.38, h * 0.32)
            path.lineTo(w * 0.46, h * 0.42)
            path.lineTo(w * 0.82, h * 0.42)
            path.lineTo(w * 0.82, h * 0.74)
            path.lineTo(w * 0.18, h * 0.74)
            path.closeSubpath()
            painter.drawPath(path)

        elif name == "play":
            # دکمه اجرای برنامه (مثلث پلی)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(gold_color))
            path = QPainterPath()
            path.moveTo(w * 0.30, h * 0.22)
            path.lineTo(w * 0.78, h * 0.50)
            path.lineTo(w * 0.30, h * 0.78)
            path.closeSubpath()
            painter.drawPath(path)

        elif name in ("server", "central_server"):
            # آیکون رک سرور مرکزی
            pen = QPen(gold_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            # یونیت بالایی
            painter.drawRoundedRect(QRectF(w * 0.18, h * 0.20, w * 0.64, h * 0.26), 4, 4)
            painter.drawEllipse(QPointF(w * 0.72, h * 0.33), w * 0.03, h * 0.03)
            painter.drawLine(QPointF(w * 0.26, h * 0.33), QPointF(w * 0.58, h * 0.33))
            # یونیت پایینی
            painter.drawRoundedRect(QRectF(w * 0.18, h * 0.54, w * 0.64, h * 0.26), 4, 4)
            painter.drawEllipse(QPointF(w * 0.72, h * 0.67), w * 0.03, h * 0.03)
            painter.drawLine(QPointF(w * 0.26, h * 0.67), QPointF(w * 0.58, h * 0.67))

        elif name in ("client", "workstation", "pos"):
            # آیکون مانیتور ایستگاه کلاینت / صندوق
            pen = QPen(gold_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            # صفحه نمایش
            painter.drawRoundedRect(QRectF(w * 0.16, h * 0.18, w * 0.68, h * 0.48), 4, 4)
            # پایه مانیتور
            painter.drawLine(QPointF(w * 0.50, h * 0.66), QPointF(w * 0.50, h * 0.78))
            painter.drawLine(QPointF(w * 0.32, h * 0.78), QPointF(w * 0.68, h * 0.78))

        elif name in ("user", "technician", "person"):
            # آیکون کاربر / کارشناس استقرار
            pen = QPen(gold_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            # سر کاربر
            painter.drawEllipse(QPointF(w * 0.50, h * 0.34), w * 0.16, h * 0.16)
            # شانه و بدن
            path = QPainterPath()
            path.moveTo(w * 0.22, h * 0.78)
            path.quadTo(w * 0.24, h * 0.56, w * 0.50, h * 0.56)
            path.quadTo(w * 0.76, h * 0.56, w * 0.78, h * 0.78)
            painter.drawPath(path)

        else:
            # دایره اکسنت پیش‌فرض
            pen = QPen(gold_color, 2.0)
            painter.setPen(pen)
            painter.drawEllipse(center, w * 0.35, h * 0.35)

        painter.end()
        return QIcon(pix)
