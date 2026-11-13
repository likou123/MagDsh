"""启动窗口（对应原 C# LauncherForm.cs）。"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QLabel, QWidget

from . import theme
from .appinfo import (
    AppKind,
    AppLauncher,
    Diagnostics,
    LauncherSettings,
    Log,
    SoftwareCatalog,
    SoftwareSpec,
)
from .dialogs import confirm, error as error_box
from .settings_form import SettingsForm
from .widgets import (
    AccentProgress,
    ChromeWindow,
    FlatButton,
    GlyphButton,
    LogoView,
    RoundedPanel,
    StatusRow,
    StepState,
)

APP_VERSION = "1.1.1"


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


class LauncherForm(ChromeWindow):
    def __init__(self, magpie_path: str, dsh_path: str, parent: QWidget | None = None):
        super().__init__(500, 342, "MagDsh", parent)
        self._magpie_path = magpie_path
        self._dsh_path = dsh_path
        self._running = False
        self._cancelled = False
        self._started = False

        self._logo = LogoView(self, size=76)
        self._logo.move(30, 26)

        self._title = _label(self, "MagDsh", 21.0, True, theme.TEXT, (126, 25, 310, 42))
        self._subtitle = _label(
            self,
            "一键启动 Magpie 与 DeepSeek Harness",
            8.7,
            False,
            theme.MUTED,
            (128, 68, 320, 20),
        )

        self._close = GlyphButton(self)
        self._close.move(454, 16)
        self._close.clicked.connect(self._on_close_clicked)

        self._card = RoundedPanel(self, fill=theme.SURFACE, border=theme.BORDER, radius=14)
        self._card.setGeometry(30, 124, 440, 120)

        self._magpie_row = StatusRow(self._card)
        self._magpie_row.setGeometry(6, 4, 428, 56)
        self._magpie_row.set_texts(SoftwareCatalog.MAGPIE.display_name, SoftwareCatalog.MAGPIE.description)
        self._magpie_row.set_state(StepState.PENDING, "等待中")

        self._dsh_row = StatusRow(self._card)
        self._dsh_row.setGeometry(6, 60, 428, 56)
        self._dsh_row.set_texts(SoftwareCatalog.DSH.display_name, SoftwareCatalog.DSH.description)
        self._dsh_row.set_state(StepState.PENDING, "等待中")
        self._dsh_row.show_divider = False

        self._footer = _label(self, "准备启动…", 8.5, False, theme.MUTED, (32, 260, 360, 20))
        self._version = _label(
            self,
            "v" + APP_VERSION,
            8.0,
            False,
            theme.SUBTLE,
            (392, 260, 76, 20),
            Qt.AlignRight | Qt.AlignTop,
        )

        self._progress = AccentProgress(self)
        self._progress.setGeometry(0, 338, 500, 4)

        self.enable_window_drag(self._logo, self._title, self._subtitle)

    # ------------------------------------------------------------ 事件
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._started:
            self._started = True
            self.run_sequence()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._cancelled = True
        super().closeEvent(event)

    def _on_close_clicked(self) -> None:
        self._cancelled = True
        self.close()

    def alive(self) -> bool:
        return not self._cancelled and self.isVisible() and not self.isHidden()

    # ------------------------------------------------------------ 序列
    def reset_rows(self) -> None:
        self._magpie_row.set_state(StepState.PENDING, "等待中")
        self._dsh_row.set_state(StepState.PENDING, "等待中")
        self._progress.set_target(0.0)
        self._set_footer("准备启动…", theme.MUTED)

    def _set_footer(self, text: str, color) -> None:
        self._footer.setStyleSheet(f"color:{color.name()};background:transparent;")
        self._footer.setText(text)

    def run_sequence(self) -> None:
        if self._running:
            return
        self._running = True
        self._cancelled = False

        Diagnostics.trace("LauncherForm sequence start")
        Log.info("Sequence started")

        self.reset_rows()
        self._errors = []
        self._progress.set_target(0.06)
        self._set_footer("准备启动…", theme.MUTED)

        QTimer.singleShot(260, self._step_start_magpie)

    def _step_start_magpie(self) -> None:
        if not self.alive():
            return
        self._start_one(
            SoftwareCatalog.MAGPIE,
            self._magpie_path,
            self._magpie_row,
            0.30,
            self._errors,
            self._after_magpie,
        )

    def _after_magpie(self) -> None:
        if not self.alive():
            return
        QTimer.singleShot(700, self._step_start_dsh)

    def _step_start_dsh(self) -> None:
        if not self.alive():
            return
        self._start_one(
            SoftwareCatalog.DSH,
            self._dsh_path,
            self._dsh_row,
            0.68,
            self._errors,
            self._after_dsh,
        )

    def _after_dsh(self) -> None:
        if not self.alive():
            return
        # Give the DSH window time to appear, then bring only DSH to the front.
        QTimer.singleShot(900, self._focus_dsh_and_finish)

    def _focus_dsh_and_finish(self) -> None:
        if not self.alive():
            return
        AppLauncher.try_activate(SoftwareCatalog.DSH)
        QTimer.singleShot(450, self._finish)

    def _start_one(self, spec: SoftwareSpec, path: Optional[str], row: StatusRow,
                   progress: float, errors: List[str], next_step) -> None:
        try:
            if AppLauncher.is_running(spec):
                row.set_state(StepState.DONE, "已在运行")
                Diagnostics.trace(f"Already running: {spec.key}")
                self._progress.set_target(progress)
                if spec.kind == AppKind.MAGPIE:
                    AppLauncher.hide(spec)
                else:
                    AppLauncher.try_activate(spec)
                if next_step is not None:
                    next_step()
                return

            row.set_state(StepState.WORKING, "正在启动…")
            self._set_footer(f"正在启动 {spec.display_name}…", theme.MUTED)
            self._progress.set_target(progress)
            QTimer.singleShot(140, lambda: self._do_start(spec, path, row, errors, next_step))
        except Exception as exc:
            self._handle_sequence_error(exc)

    def _do_start(self, spec: SoftwareSpec, path: Optional[str], row: StatusRow,
                  errors: List[str], next_step) -> None:
        try:
            if not self.alive():
                return

            outcome = AppLauncher.start(spec, path or "")
            if outcome.success:
                row.set_state(StepState.DONE, "已启动")
                Diagnostics.trace(f"Sequence: {spec.key} done")
                Log.info(f"Sequence: {spec.key} done")
                if spec.kind == AppKind.MAGPIE:
                    # magpie tray should already be windowless; hide a late
                    # window as a fallback so it never covers DSH.
                    QTimer.singleShot(300, lambda: AppLauncher.hide(spec))
                    QTimer.singleShot(900, lambda: AppLauncher.hide(spec))
                else:
                    QTimer.singleShot(700, lambda: AppLauncher.try_activate(spec))
                    QTimer.singleShot(1400, lambda: AppLauncher.try_activate(spec))
            else:
                row.set_state(StepState.FAILED, "启动失败")
                errors.append(f"{spec.display_name}\r\n{outcome.message}")
                Diagnostics.trace(f"Sequence: {spec.key} failed | {outcome.message}")
                Log.error(
                    f"Launch failed: {spec.display_name} -> {path}",
                    RuntimeError(outcome.message),
                )

            if next_step is not None:
                next_step()
        except Exception as exc:
            self._handle_sequence_error(exc)

    def _finish(self) -> None:
        if not self.alive():
            return

        if not self._errors:
            self._progress.set_target(1.0)
            self._set_footer("启动完成，窗口即将关闭", theme.SUCCESS)
            Log.info("Sequence completed")
            # One last activation while this window still owns the foreground.
            AppLauncher.try_activate(SoftwareCatalog.DSH)
            QTimer.singleShot(700, self.close)
            return

        self._progress.set_target(0.92)
        self._set_footer("部分程序启动失败", theme.DANGER)
        self._running = False
        Log.info("Sequence finished with errors: " + "; ".join(self._errors))

        details = "\r\n\r\n".join(self._errors)
        if confirm(self, details + "\r\n\r\n是否重新选择软件位置？", "MagDsh 启动失败"):
            if self.show_settings_dialog():
                QTimer.singleShot(120, self.run_sequence)

    def _handle_sequence_error(self, exc: BaseException) -> None:
        self._running = False
        Log.error("Launcher sequence failed", exc)
        if not self._cancelled:
            self._set_footer("启动器遇到问题", theme.DANGER)
            error_box(self, "启动器遇到问题：\r\n" + str(exc), "MagDsh")

    def show_settings_dialog(self) -> bool:
        current = LauncherSettings(magpie_path=self._magpie_path, dsh_path=self._dsh_path)
        form = SettingsForm(current, self)
        if form.exec() != QDialog.DialogCode.Accepted:
            return False
        self._magpie_path = form.magpie_path
        self._dsh_path = form.dsh_path
        return True
