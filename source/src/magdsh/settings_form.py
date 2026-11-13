"""软件位置设置窗口（对应原 C# SettingsForm.cs）。"""

from __future__ import annotations

import os

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QFileDialog, QLabel, QWidget

from . import theme
from .appinfo import (
    LauncherSettings,
    Log,
    SettingsStore,
    SoftwareCatalog,
    SoftwareSpec,
)
from .widgets import (
    BannerTone,
    ChromeBase,
    ChromeDialog,
    FlatButton,
    GlyphButton,
    InfoBanner,
    LogoView,
    PathField,
    PillTone,
    RoundedPanel,
    StatusPill,
)


def _label(
    parent: QWidget,
    text: str,
    size: float,
    bold: bool,
    color,
    geometry: tuple[int, int, int, int],
    align=Qt.AlignLeft | Qt.AlignVCenter,
) -> QLabel:
    label = QLabel(text, parent)
    label.setFont(theme.font(size, bold=bold))
    label.setStyleSheet(f"color:{color.name()};background:transparent;")
    label.setGeometry(*geometry)
    label.setAlignment(align)
    label.setTextInteractionFlags(Qt.NoTextInteraction)
    return label


class PathCard(RoundedPanel):
    browse_requested = Signal()
    path_changed = Signal()

    def __init__(self, spec: SoftwareSpec, parent: QWidget | None = None):
        super().__init__(parent, fill=theme.SURFACE, border=theme.BORDER, radius=14)
        self.spec = spec
        self.resolved_path: str | None = None
        self.setFixedHeight(124)

        self._title = _label(self, spec.display_name, 10.6, True, theme.TEXT, (18, 9, 480, 22))
        self._description = _label(
            self, spec.description, 8.3, False, theme.MUTED, (18, 31, 480, 18)
        )

        self._pill = StatusPill(self)
        self._pill.set_status("未找到", PillTone.WARNING)
        self._pill.move(552, 13)

        self.field = PathField(self)
        self.field.move(18, 53)
        self.field.resize(502, 36)
        self.field.setToolTip("可直接粘贴路径，或把文件夹 / exe 拖到这里")
        self.field.text_changed.connect(self._on_field_changed)
        self.field.line_edit.returnPressed.connect(self.path_changed.emit)

        self._browse = FlatButton("选择文件夹", primary=False, parent=self)
        self._browse.setFont(theme.font(8.7, bold=True))
        self._browse.setFixedSize(96, 36)
        self._browse.move(530, 53)
        self._browse.clicked.connect(self.browse_requested.emit)

        self._hint = _label(
            self,
            f"请选择包含 {spec.exe_name} 的文件夹",
            8.2,
            False,
            theme.MUTED,
            (18, 96, 608, 18),
        )

        self.layout_children()

    # ------------------------------------------------------------ API
    def set_path(self, path: str | None) -> None:
        display = path or ""
        resolved = SoftwareCatalog.resolve_selection(self.spec, display)
        if resolved:
            try:
                display = os.path.dirname(resolved)
            except Exception:
                pass
        self.field.set_text(display)
        self.validate_path()

    def validate_path(self) -> bool:
        resolved = SoftwareCatalog.resolve_selection(self.spec, self.field.text())
        self.resolved_path = resolved

        if not resolved:
            self.field.set_invalid(len(self.field.text()) > 0)
            self._pill.set_status("未找到", PillTone.WARNING)
            self._hint.setStyleSheet(f"color:{theme.WARNING.name()};background:transparent;")
            self._hint.setText(f"未找到 {self.spec.exe_name}，请选择包含该程序的文件夹")
            self._hint.setToolTip("")
            return False

        self.field.set_invalid(False)
        self._pill.set_status("已找到", PillTone.SUCCESS)
        self._hint.setStyleSheet(f"color:{theme.MUTED.name()};background:transparent;")
        self._hint.setText("将启动：" + os.path.basename(resolved))
        self._hint.setToolTip(resolved)
        return True

    def focus_input(self) -> None:
        self.field.line_edit.setFocus()

    def _on_field_changed(self, _text: str) -> None:
        self.validate_path()
        self.path_changed.emit()

    # ------------------------------------------------------------ 布局
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.layout_children()

    def layout_children(self) -> None:
        right = self.width() - 18
        self._pill.move(right - self._pill.width(), 13)
        title_width = max(100, self._pill.x() - self._title.x() - 8)
        self._title.setFixedWidth(title_width)
        self._description.setFixedWidth(title_width)
        self._browse.move(right - self._browse.width(), 53)
        field_width = max(120, self._browse.x() - self.field.x() - 10)
        self.field.resize(field_width, 36)
        self._hint.setFixedWidth(max(120, self.width() - 36))


class SettingsForm(ChromeDialog):
    def __init__(self, initial: LauncherSettings | None, parent: QWidget | None = None):
        super().__init__(700, 512, "MagDsh - 软件位置", parent)
        self._initial = initial or LauncherSettings()
        self.magpie_path: str = ""
        self.dsh_path: str = ""

        self._logo = LogoView(self, size=50)
        self._logo.move(28, 17)

        self._title = _label(self, "软件位置", 16.5, True, theme.TEXT, (92, 10, 460, 36))
        self._subtitle = _label(
            self,
            "请选择 Magpie 与 DeepSeek Harness 的安装文件夹",
            8.6,
            False,
            theme.MUTED,
            (94, 48, 500, 20),
        )

        self._close = GlyphButton(self)
        self._close.move(700 - 46, 16)
        self._close.clicked.connect(self._on_cancel)

        self._banner = InfoBanner(self, height=44)
        self._banner.setGeometry(28, 82, 644, 44)

        self._magpie_card = PathCard(SoftwareCatalog.MAGPIE, self)
        self._magpie_card.setGeometry(28, 138, 644, 124)
        self._magpie_card.browse_requested.connect(lambda: self._browse_for(self._magpie_card))
        self._magpie_card.path_changed.connect(self._on_path_changed)

        self._dsh_card = PathCard(SoftwareCatalog.DSH, self)
        self._dsh_card.setGeometry(28, 274, 644, 124)
        self._dsh_card.browse_requested.connect(lambda: self._browse_for(self._dsh_card))
        self._dsh_card.path_changed.connect(self._on_path_changed)

        self._error = _label(self, "", 8.4, False, theme.DANGER, (28, 405, 644, 20))

        self._auto = FlatButton("自动检测", parent=self)
        self._auto.setFont(theme.font(9.2, bold=True))
        self._auto.setGeometry(28, 442, 108, 38)
        self._auto.clicked.connect(self._auto_detect)

        self._local_hint = _label(
            self,
            "路径只保存在本机，下次启动自动使用",
            8.1,
            False,
            theme.SUBTLE,
            (146, 452, 280, 18),
        )

        self._cancel = FlatButton("取消", parent=self)
        self._cancel.setGeometry(456, 442, 78, 38)
        self._cancel.clicked.connect(self._on_cancel)

        self._save = FlatButton("保存并启动", primary=True, parent=self)
        self._save.setGeometry(544, 442, 128, 38)
        self._save.clicked.connect(self._save_and_close)

        self.enable_window_drag(self._logo, self._title, self._subtitle)

        self._load_initial_paths()
        self._update_banner()

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(theme.BORDER)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(28, 430, self.width() - 28, 430)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._magpie_card.resolved_path is None:
            self._magpie_card.focus_input()
        elif self._dsh_card.resolved_path is None:
            self._dsh_card.focus_input()

    # ------------------------------------------------------------ 交互
    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._save_and_close()
            return
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
            return
        super().keyPressEvent(event)

    def _on_cancel(self) -> None:
        self.reject()

    def _load_initial_paths(self) -> None:
        magpie = SoftwareCatalog.find_configured(SoftwareCatalog.MAGPIE, self._initial.magpie_path)
        dsh = SoftwareCatalog.find_configured(SoftwareCatalog.DSH, self._initial.dsh_path)
        self._magpie_card.set_path(magpie or self._initial.magpie_path)
        self._dsh_card.set_path(dsh or self._initial.dsh_path)

    def _auto_detect(self) -> None:
        self._magpie_card.set_path(SoftwareCatalog.detect_default(SoftwareCatalog.MAGPIE))
        self._dsh_card.set_path(SoftwareCatalog.detect_default(SoftwareCatalog.DSH))
        self._clear_error()
        self._update_banner()

    def _browse_for(self, card: PathCard) -> None:
        current = card.field.text()
        start = current if os.path.isdir(current) else ""
        title = f"选择 {card.spec.display_name} 所在的文件夹（应包含 {card.spec.exe_name}）"
        selected = QFileDialog.getExistingDirectory(self, title, start)
        if selected:
            card.field.set_text(selected)
            card.focus_input()

    def _on_path_changed(self) -> None:
        self._update_banner()
        self._clear_error()

    def _update_banner(self) -> None:
        magpie_ok = self._magpie_card.resolved_path is not None
        dsh_ok = self._dsh_card.resolved_path is not None

        if magpie_ok and dsh_ok:
            self._banner.set_message("两个软件都已找到，点击“保存并启动”即可。", BannerTone.SUCCESS)
            return

        if not magpie_ok and not dsh_ok:
            message = "未检测到 Magpie 和 DeepSeek Harness，请手动选择它们的安装文件夹。"
        elif not magpie_ok:
            message = "未检测到 Magpie，请选择包含 magpie.exe 的文件夹。"
        else:
            message = "未检测到 DeepSeek Harness，请选择包含其 exe 的文件夹。"
        self._banner.set_message(message, BannerTone.WARNING)

    def _clear_error(self) -> None:
        self._error.setText("")

    def _save_and_close(self) -> None:
        magpie_ok = self._magpie_card.validate_path()
        dsh_ok = self._dsh_card.validate_path()

        if not magpie_ok or not dsh_ok:
            self._error.setText("请先指定两个软件的有效安装文件夹。")
            if not magpie_ok:
                self._magpie_card.focus_input()
            else:
                self._dsh_card.focus_input()
            return

        settings = LauncherSettings(
            magpie_path=self._magpie_card.resolved_path or "",
            dsh_path=self._dsh_card.resolved_path or "",
        )

        if not SettingsStore.save(settings):
            from .dialogs import warn

            warn(
                self,
                "设置无法写入本机配置文件，但本次仍会继续启动。\r\n\r\n"
                + SettingsStore.config_file_path(),
                "MagDsh",
            )

        Log.info(
            f"Settings saved | magpie={settings.magpie_path} | dsh={settings.dsh_path}"
        )
        self.magpie_path = settings.magpie_path
        self.dsh_path = settings.dsh_path
        self.accept()
