"""自绘控件库（对应原 C# UiControls.cs）。"""

from __future__ import annotations

import os

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPen,
    QPixmap,
    QRegion,
)
from PySide6.QtWidgets import QDialog, QLineEdit, QWidget

from . import theme


# ================================================================ 窗口基类
class ChromeBase:
    """无边框圆角窗口：对应 C# ChromeForm（圆角裁切、Esc 关闭、标题区拖拽）。"""

    RADIUS = 16

    def _init_chrome(self, width: int, height: int, title: str) -> None:
        self.setWindowTitle(title)
        self.setWindowIcon(theme.load_app_icon())
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(width, height)
        self._drag_widgets: list[QWidget] = []

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform
        )
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        theme.fill_rounded(painter, theme.WINDOW, rect, self.RADIUS)
        theme.draw_rounded_border(painter, theme.BORDER, rect, self.RADIUS, 1.0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_mask()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_mask()

    def _apply_mask(self) -> None:
        rect = QRectF(0, 0, self.width(), self.height())
        path = theme.rounded_path(rect, self.RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------ 拖拽
    def enable_window_drag(self, *widgets: QWidget) -> None:
        for widget in widgets:
            widget.installEventFilter(self)
            self._drag_widgets.append(widget)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched in self._drag_widgets:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                handle = self.windowHandle()
                if handle is not None:
                    handle.startSystemMove()
                    return True
        return super().eventFilter(watched, event)


class ChromeWindow(ChromeBase, QWidget):
    def __init__(self, width: int, height: int, title: str, parent: QWidget | None = None):
        QWidget.__init__(self, parent)
        self._init_chrome(width, height, title)


class ChromeDialog(ChromeBase, QDialog):
    def __init__(self, width: int, height: int, title: str, parent: QWidget | None = None):
        QDialog.__init__(self, parent)
        self._init_chrome(width, height, title)
        self.setModal(True)


# ================================================================ 关闭按钮
class GlyphButton(QWidget):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, diameter: int = 30):
        super().__init__(parent)
        self.setFixedSize(diameter, diameter)
        self._hover = False
        self._pressed = False
        self.setCursor(Qt.ArrowCursor)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self._pressed = False
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if not self._pressed:
            return
        self._pressed = False
        self.update()
        if self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(0, 0, self.width(), self.height())

        if self._hover or self._pressed:
            fill = theme.GLYPH_PRESSED if self._pressed else theme.GLYPH_HOVER
            theme.fill_rounded(painter, fill, rect, 8)

        color = theme.TEXT if (self._hover or self._pressed) else theme.MUTED
        pen = QPen(color)
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        arm = 4.6
        painter.drawLine(
            QPointF(center.x() - arm, center.y() - arm), QPointF(center.x() + arm, center.y() + arm)
        )
        painter.drawLine(
            QPointF(center.x() + arm, center.y() - arm), QPointF(center.x() - arm, center.y() + arm)
        )


# ================================================================ Logo
class LogoView(QWidget):
    def __init__(self, parent: QWidget | None = None, size: int = 76):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing
        )
        rect = QRectF(0, 0, self.width(), self.height())
        pixmap = theme.load_logo()
        if pixmap is not None and not pixmap.isNull():
            painter.drawPixmap(rect, pixmap, QRectF(pixmap.rect()))
            return

        theme.fill_rounded(painter, theme.ACCENT, rect, 16)
        font = theme.font(self.height() * 0.42, bold=True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(rect, Qt.AlignCenter, "M")


# ================================================================ 提示横幅
class BannerTone:
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class InfoBanner(QWidget):
    def __init__(self, parent: QWidget | None = None, height: int = 44):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._message = ""
        self._tone = BannerTone.INFO
        self.setFont(theme.font(8.6))

    def set_message(self, message: str, tone: str = BannerTone.INFO) -> None:
        self._message = message or ""
        self._tone = tone
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(0, 0, self.width(), self.height())

        fill, border, badge = self._palette()
        theme.fill_rounded(painter, fill, rect, 10)
        theme.draw_rounded_border(painter, border, rect, 10, 1.0)

        # 左侧圆形徽标
        diameter = 18.0
        badge_rect = QRectF(18.0, (self.height() - diameter) / 2.0, diameter, diameter)
        painter.setPen(Qt.NoPen)
        painter.setBrush(badge)
        painter.drawEllipse(badge_rect)

        glyph_font = theme.font(9.0, bold=True)
        painter.setFont(glyph_font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(badge_rect, Qt.AlignCenter, self._glyph())

        # 右侧文字
        text_color = theme.DANGER if self._tone == BannerTone.ERROR else theme.TEXT
        font = self.font()
        text_rect = QRectF(40.0, 0, max(10.0, self.width() - 54.0), float(self.height()))
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(
            text_rect,
            int(Qt.AlignVCenter | Qt.AlignLeft),
            theme.ellipsize(self._message, font, int(text_rect.width())),
        )

    def _palette(self):
        if self._tone == BannerTone.SUCCESS:
            return theme.SUCCESS_SOFT, theme.SUCCESS_BORDER, theme.SUCCESS
        if self._tone == BannerTone.WARNING:
            return theme.WARNING_SOFT, theme.WARNING_BORDER, theme.WARNING
        if self._tone == BannerTone.ERROR:
            return theme.DANGER_SOFT, theme.DANGER_BORDER, theme.DANGER
        return theme.ACCENT_SOFT, theme.ACCENT_BORDER, theme.ACCENT

    def _glyph(self) -> str:
        if self._tone == BannerTone.SUCCESS:
            return "\u2713"
        if self._tone in (BannerTone.WARNING, BannerTone.ERROR):
            return "!"
        return "i"


# ================================================================ 状态胶囊
class PillTone:
    NEUTRAL = "neutral"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    ACCENT = "accent"


class StatusPill(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(74, 22)
        self._text = ""
        self._tone = PillTone.NEUTRAL
        self.setFont(theme.font(7.8, bold=True))

    def set_status(self, text: str, tone: str) -> None:
        self._text = text or ""
        self._tone = tone
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(0, 0, self.width(), self.height())

        fill, foreground = self._palette()
        theme.fill_rounded(painter, fill, rect, self.height() / 2.0)
        painter.setFont(self.font())
        painter.setPen(foreground)
        painter.drawText(rect, Qt.AlignCenter, self._text)

    def _palette(self):
        if self._tone == PillTone.SUCCESS:
            return theme.SUCCESS_SOFT, theme.SUCCESS
        if self._tone == PillTone.WARNING:
            return theme.WARNING_SOFT, theme.WARNING
        if self._tone == PillTone.DANGER:
            return theme.DANGER_SOFT, theme.DANGER
        if self._tone == PillTone.ACCENT:
            return theme.ACCENT_SOFT, theme.ACCENT
        return theme.SURFACE_STRONG, theme.MUTED


# ================================================================ 状态行
class StepState:
    PENDING = "pending"
    WORKING = "working"
    DONE = "done"
    FAILED = "failed"


class StatusRow(QWidget):
    """对应 C# StatusRow：圆环图标 + 标题 + 说明 + 右侧状态文字。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self._title = ""
        self._subtitle = ""
        self._state_text = ""
        self._state = StepState.PENDING
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------ API
    def set_state(self, state: str, state_text: str) -> None:
        self._state = state
        self._state_text = state_text or ""
        if state == StepState.WORKING:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def set_texts(self, title: str, subtitle: str) -> None:
        self._title = title or ""
        self._subtitle = subtitle or ""
        self.update()

    def _tick(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        width = float(self.width())
        height = float(self.height())

        center = QPointF(27.0, height / 2.0)
        self._draw_icon(painter, center)

        title_rect = QRectF(52.0, 6.0, max(10.0, width - 52.0 - 18.0 - 100.0), 22.0)
        title_font = theme.font(9.8, bold=True)
        painter.setFont(title_font)
        painter.setPen(theme.TEXT)
        painter.drawText(
            title_rect,
            int(Qt.AlignVCenter | Qt.AlignLeft),
            theme.ellipsize(self._title, title_font, int(title_rect.width())),
        )

        sub_rect = QRectF(52.0, 28.0, max(10.0, width - 52.0 - 18.0), 17.0)
        sub_font = theme.font(8.2)
        painter.setFont(sub_font)
        painter.setPen(theme.MUTED)
        painter.drawText(
            sub_rect,
            int(Qt.AlignVCenter | Qt.AlignLeft),
            theme.ellipsize(self._subtitle, sub_font, int(sub_rect.width())),
        )

        state_rect = QRectF(width - 18.0 - 92.0, 0.0, 92.0, height - 1.0)
        painter.setFont(theme.font(8.2, bold=self._state in (StepState.DONE, StepState.FAILED)))
        painter.setPen(self._state_color())
        painter.drawText(state_rect, int(Qt.AlignVCenter | Qt.AlignRight), self._state_text)

        pen = QPen(theme.ROW_DIVIDER)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(QPointF(52.0, height - 1.0), QPointF(width - 18.0, height - 1.0))

    def _state_color(self) -> QColor:
        if self._state == StepState.DONE:
            return theme.SUCCESS
        if self._state == StepState.FAILED:
            return theme.DANGER
        if self._state == StepState.WORKING:
            return theme.ACCENT
        return theme.SUBTLE

    def _draw_icon(self, painter: QPainter, center: QPointF) -> None:
        diameter = 18.0
        box = QRectF(center.x() - diameter / 2.0, center.y() - diameter / 2.0, diameter, diameter)

        if self._state == StepState.DONE:
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme.SUCCESS)
            painter.drawEllipse(box)
            pen = QPen(QColor(255, 255, 255))
            pen.setWidthF(1.7)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPolyline(
                [
                    QPointF(box.left() + 5.0, box.center().y() + 0.4),
                    QPointF(box.left() + 8.0, box.center().y() + 3.4),
                    QPointF(box.left() + 13.2, box.center().y() - 3.2),
                ]
            )
            return

        if self._state == StepState.FAILED:
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme.DANGER)
            painter.drawEllipse(box)
            font = theme.font(9.0, bold=True)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(box, Qt.AlignCenter, "!")
            return

        if self._state == StepState.WORKING:
            pen = QPen(theme.SPINNER_TRACK)
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(box.adjusted(1, 1, -1, -1))

            pen = QPen(theme.ACCENT)
            pen.setWidthF(2.0)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(box.adjusted(1, 1, -1, -1), int(-self._angle * 16), int(100 * 16))
            return

        pen = QPen(theme.RING_PENDING)
        pen.setWidthF(1.6)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(box.adjusted(1, 1, -1, -1))
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.DOT_PENDING)
        painter.drawEllipse(QRectF(center.x() - 2.0, center.y() - 2.0, 4.0, 4.0))


# ================================================================ 进度条
class AccentProgress(QWidget):
    """对应 C# AccentProgress：16ms 缓动（系数 0.16）。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self._value = 0.0
        self._target = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def target(self) -> float:
        return self._target

    def set_target(self, value: float) -> None:
        self._target = max(0.0, min(1.0, float(value)))
        if not self._timer.isActive():
            self._timer.start()

    def _tick(self) -> None:
        delta = self._target - self._value
        if abs(delta) < 0.005:
            self._value = self._target
            self._timer.stop()
            self.update()
            return
        self._value += delta * 0.16
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())

        theme.fill_rounded(painter, theme.PROGRESS_TRACK, rect, 2)
        if self._value > 0.0005:
            width = max(2.0, rect.width() * self._value)
            theme.fill_rounded(
                painter, theme.ACCENT, QRectF(0, 0, width, rect.height()), 2
            )


# ================================================================ 扁平按钮
class FlatButton(QWidget):
    """对应 C# FlatButton：圆角 10、字号 9.3 Bold，Primary 使用强调色。"""

    clicked = Signal()

    def __init__(self, text: str, primary: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self._text = text
        self._primary = primary
        self._hover = False
        self._pressed = False
        self._enabled = True
        self.setFixedHeight(38)
        self.setFont(theme.font(9.3, bold=True))
        self.setCursor(Qt.PointingHandCursor)

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def set_enabled_state(self, enabled: bool) -> None:
        self._enabled = enabled
        self.setEnabled(enabled)
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self._pressed = False
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._enabled:
            self._pressed = True
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if not self._pressed:
            return
        self._pressed = False
        self.update()
        if self._enabled and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)

        fill, border, foreground = self._palette()
        theme.fill_rounded(painter, fill, rect, 10)
        if border is not None:
            theme.draw_rounded_border(painter, border, rect, 10, 1.0)

        painter.setFont(self.font())
        painter.setPen(foreground)
        painter.drawText(rect, Qt.AlignCenter, self._text)

    def _palette(self):
        if not self._enabled:
            if self._primary:
                return theme.ACCENT_DISABLED, None, QColor(255, 255, 255)
            return theme.BUTTON_DISABLED_FILL, theme.BORDER, theme.SUBTLE

        if self._primary:
            if self._pressed:
                return theme.ACCENT_PRESSED, None, QColor(255, 255, 255)
            if self._hover:
                return theme.ACCENT_HOVER, None, QColor(255, 255, 255)
            return theme.ACCENT, None, QColor(255, 255, 255)

        if self._pressed:
            return theme.BUTTON_PRESSED, theme.BORDER_STRONG, theme.TEXT
        if self._hover:
            return theme.BUTTON_HOVER, theme.BUTTON_BORDER_HOVER, theme.TEXT
        return theme.WINDOW, theme.BORDER, theme.TEXT


# ================================================================ 圆角面板
class RoundedPanel(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        fill: QColor | None = None,
        border: QColor | None = None,
        radius: float = 14,
    ):
        super().__init__(parent)
        self._fill = fill if fill is not None else theme.SURFACE
        self._border = border if border is not None else theme.BORDER
        self._radius = radius

    def set_colors(self, fill: QColor | None = None, border: QColor | None = None) -> None:
        if fill is not None:
            self._fill = fill
        if border is not None:
            self._border = border
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        theme.fill_rounded(painter, self._fill, rect, self._radius)
        theme.draw_rounded_border(painter, self._border, rect, self._radius, 1.0)


# ================================================================ 路径输入框
class PathField(QWidget):
    """对应 C# PathField：圆角输入框，支持拖入文件夹或 exe。"""

    text_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setAcceptDrops(True)
        self._invalid = False
        self._dragging = False

        self._edit = QLineEdit(self)
        self._edit.setFrame(False)
        self._edit.setStyleSheet(
            "QLineEdit{background:transparent;border:none;padding:0px;}"
            "QLineEdit:focus{outline:none;}"
        )
        self._edit.setFont(theme.font(9.3))
        self._edit.setPlaceholderText("输入 exe 路径，或将文件夹拖入上方")
        self._edit.setGeometry(12, 0, max(10, self.width() - 24), self.height())
        self._edit.textChanged.connect(self._on_text_changed)
        self.line_edit = self._edit

    # ------------------------------------------------------------ API
    def text(self) -> str:
        return self._edit.text()

    def set_text(self, value: str) -> None:
        if self._edit.text() == (value or ""):
            return
        self._edit.setText(value or "")

    def set_invalid(self, invalid: bool) -> None:
        if self._invalid == invalid:
            return
        self._invalid = invalid
        self.update()

    def _on_text_changed(self, value: str) -> None:
        self.text_changed.emit(value)

    # ------------------------------------------------------------ 布局
    def resizeEvent(self, event) -> None:  # noqa: N802
        width = max(10, self.width() - 24)
        self._edit.setGeometry(12, 0, width, self.height())
        super().resizeEvent(event)

    def focusInEvent(self, event) -> None:  # noqa: N802
        self.update()

    # ------------------------------------------------------------ 拖放
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._dragging = True
            self.update()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._dragging = False
        self.update()

    def dropEvent(self, event) -> None:  # noqa: N802
        self._dragging = False
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            if not path:
                continue
            if os.path.isdir(path) or path.lower().endswith(".exe"):
                self._edit.setText(path)
                event.acceptProposedAction()
                break
            event.acceptProposedAction()
            break
        self.update()

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)

        theme.fill_rounded(painter, theme.WINDOW, rect, 8)
        if self._invalid:
            theme.draw_rounded_border(painter, theme.DANGER, rect, 8, 1.4)
        elif self._dragging or self._edit.hasFocus():
            theme.draw_rounded_border(painter, theme.ACCENT, rect, 8, 1.4)
        else:
            theme.draw_rounded_border(painter, theme.BORDER_STRONG, rect, 8, 1.0)
