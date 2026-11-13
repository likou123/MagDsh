"""配色、字体与绘制辅助（对应原 C# Theme.cs）。"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

# ---------------------------------------------------------------- 颜色
WINDOW = QColor(255, 255, 255)
SURFACE = QColor(247, 249, 252)
SURFACE_STRONG = QColor(242, 246, 251)
BORDER = QColor(229, 235, 243)
BORDER_STRONG = QColor(213, 222, 235)
TEXT = QColor(16, 24, 40)
MUTED = QColor(102, 112, 133)
SUBTLE = QColor(152, 162, 179)
ACCENT = QColor(0, 116, 253)
ACCENT_HOVER = QColor(0, 103, 224)
ACCENT_PRESSED = QColor(0, 89, 196)
ACCENT_SOFT = QColor(234, 243, 255)
ACCENT_DISABLED = QColor(184, 208, 240)
SUCCESS = QColor(18, 148, 95)
SUCCESS_SOFT = QColor(236, 253, 243)
SUCCESS_BORDER = QColor(205, 241, 224)
WARNING = QColor(181, 71, 8)
WARNING_SOFT = QColor(255, 250, 235)
WARNING_BORDER = QColor(254, 223, 137)
DANGER = QColor(217, 45, 32)
DANGER_SOFT = QColor(254, 243, 242)
DANGER_BORDER = QColor(254, 205, 202)
ACCENT_BORDER = QColor(205, 226, 255)

# 控件内部使用的中性色
GLYPH_HOVER = QColor(243, 245, 248)
GLYPH_PRESSED = QColor(234, 238, 244)
BUTTON_PRESSED = QColor(239, 243, 249)
BUTTON_HOVER = QColor(247, 250, 254)
BUTTON_BORDER_HOVER = QColor(190, 208, 230)
BUTTON_DISABLED_FILL = QColor(248, 249, 251)
ROW_DIVIDER = QColor(237, 242, 248)
PROGRESS_TRACK = QColor(237, 242, 248)
SPINNER_TRACK = QColor(225, 235, 249)
RING_PENDING = QColor(203, 213, 225)
DOT_PENDING = QColor(226, 232, 240)

FAMILY = "Microsoft YaHei UI"
FAMILY_FALLBACKS = ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial")


def font(size: float, bold: bool = False) -> QFont:
    """对应 Theme.UI(size, style)。"""
    f = QFont(FAMILY, -1)
    f.setPointSizeF(size)
    f.setBold(bold)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


# ---------------------------------------------------------------- 绘制
def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    """对应 Theme.RoundRect：半径自动收敛到短边的一半。"""
    path = QPainterPath()
    w = rect.width()
    h = rect.height()
    diameter = max(1.0, min(radius * 2.0, min(w, h)))
    if diameter <= 1.0:
        path.addRect(rect)
        path.closeSubpath()
        return path

    r = diameter / 2.0
    path.moveTo(rect.left() + r, rect.top())
    path.lineTo(rect.right() - r, rect.top())
    path.arcTo(QRectF(rect.right() - diameter, rect.top(), diameter, diameter), 90, -90)
    path.lineTo(rect.right(), rect.bottom() - r)
    path.arcTo(QRectF(rect.right() - diameter, rect.bottom() - diameter, diameter, diameter), 0, -90)
    path.lineTo(rect.left() + r, rect.bottom())
    path.arcTo(QRectF(rect.left(), rect.bottom() - diameter, diameter, diameter), 270, -90)
    path.lineTo(rect.left(), rect.top() + r)
    path.arcTo(QRectF(rect.left(), rect.top(), diameter, diameter), 180, -90)
    path.closeSubpath()
    return path


def fill_rounded(painter: QPainter, color: QColor, rect: QRectF, radius: float) -> None:
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawPath(rounded_path(rect, radius))
    painter.restore()


def draw_rounded_border(
    painter: QPainter, color: QColor, rect: QRectF, radius: float, width: float = 1.0
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(color)
    pen.setWidthF(width)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    inset = QRectF(
        rect.left() + width / 2.0,
        rect.top() + width / 2.0,
        max(1.0, rect.width() - width),
        max(1.0, rect.height() - width),
    )
    painter.drawPath(rounded_path(inset, max(1.0, radius - width / 2.0)))
    painter.restore()


def ellipsize(text: str, f: QFont, width: float) -> str:
    """对应 Theme.Ellipsize：宽度不足时二分截断并追加省略号。"""
    if not text or width <= 0:
        return ""
    metrics = QFontMetricsF(f)
    if metrics.horizontalAdvance(text) <= width:
        return text

    ell = "\u2026"
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        candidate = text[:mid] + ell
        if metrics.horizontalAdvance(candidate) <= width:
            low = mid
        else:
            high = mid - 1
    return ell if low <= 0 else text[:low] + ell


# ---------------------------------------------------------------- 资源
def resource_dir() -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "magdsh", "assets")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def resource_path(name: str) -> str:
    return os.path.join(resource_dir(), name)


_logo_cache: QPixmap | None = None


def load_logo() -> QPixmap | None:
    global _logo_cache
    if _logo_cache is not None:
        return _logo_cache
    try:
        pixmap = QPixmap(resource_path("logo.png"))
        if not pixmap.isNull():
            _logo_cache = pixmap
    except Exception:
        _logo_cache = None
    return _logo_cache


def load_app_icon() -> QIcon:
    try:
        icon = QIcon(resource_path("MagDsh.ico"))
        if not icon.isNull():
            return icon
    except Exception:
        pass
    return QIcon()
