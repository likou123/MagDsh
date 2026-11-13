"""MagDsh 入口（对应原 C# Program.cs）。"""

from __future__ import annotations

import ctypes
import os
import sys
import traceback


def _configure_ui_scale() -> None:
    """Match the C# launcher's physical UI size.

    Qt otherwise multiplies the 500x342 / 700x512 layout by the Windows
    display scale (for example 1.25), making the Python UI visibly larger
    than the C# version. Cancelling that multiplier keeps the window at
    the same physical pixel size while leaving Qt's font rendering sharp.
    """
    try:
        # Query the real system DPI. A DPI-unaware process reports 96 here,
        # which would leave Qt's 1.25x window scaling in place.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    try:
        dpi = int(ctypes.windll.user32.GetDpiForSystem())
    except Exception:
        dpi = 96
    if dpi <= 0:
        dpi = 96
    os.environ["QT_SCALE_FACTOR"] = f"{96.0 / dpi:.6f}"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"


_configure_ui_scale()

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from . import theme
from .appinfo import Diagnostics, LauncherSettings, Log, SettingsStore, SoftwareCatalog
from .dialogs import info, error as error_box
from .launcher_form import APP_VERSION, LauncherForm
from .settings_form import SettingsForm

HELP_TEXT = (
    "MagDsh 1.1\r\n\r\n"
    "双击 MagDsh.exe：启动 Magpie，然后启动 DeepSeek Harness。\r\n"
    "如果未找到软件，会自动打开路径选择窗口。\r\n\r\n"
    "MagDsh.exe --settings\r\n"
    "    手动重新选择两个软件的安装文件夹。"
)


def has_argument(argv: list[str], value: str) -> bool:
    target = value.lower()
    return any(arg.lower() == target for arg in argv)


def remove_zone_identifier() -> None:
    """删除 exe 的 Zone.Identifier 备用数据流，避免 SmartScreen 提示。"""
    try:
        import ctypes

        exe = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
        if not exe:
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.DeleteFileW.argtypes = [ctypes.c_wchar_p]
        kernel32.DeleteFileW.restype = ctypes.c_bool
        if kernel32.DeleteFileW(exe + ":Zone.Identifier"):
            Log.info("Removed Zone.Identifier from launcher")
    except Exception:
        pass


def report_fatal(exc: BaseException | None) -> None:
    Log.error("Fatal error", exc or RuntimeError("unknown"))
    detail = "未知错误" if exc is None else str(exc)
    try:
        error_box(None, "MagDsh 遇到无法继续的问题。\r\n\r\n" + detail + "\r\n\r\n日志：" + Log.file_path())
    except Exception:
        pass


def _install_excepthook() -> None:
    def handler(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        Log.error("Unhandled exception", exc_value if exc_value else RuntimeError(text))
        report_fatal(exc_value if isinstance(exc_value, BaseException) else RuntimeError(text))

    sys.excepthook = handler


def _apply_font(app: QApplication) -> None:
    available = set(QFontDatabase.families())
    family = next((name for name in theme.FAMILY_FALLBACKS if name in available), None)
    font = QFont(family) if family else QFont()
    font.setPixelSize(12)
    app.setFont(font)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    args = argv[1:]

    remove_zone_identifier()

    app = QApplication(argv)
    app.setApplicationName("MagDsh")
    app.setApplicationDisplayName("MagDsh")
    app.setQuitOnLastWindowClosed(True)
    icon = theme.load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    _apply_font(app)
    _install_excepthook()

    force_settings = has_argument(args, "--settings") or has_argument(args, "-s")
    show_help = has_argument(args, "--help") or has_argument(args, "/?")

    if show_help:
        info(None, HELP_TEXT, "MagDsh")
        return 0

    try:
        saved = SettingsStore.load()
        magpie_path = SoftwareCatalog.find_configured(SoftwareCatalog.MAGPIE, saved.magpie_path)
        dsh_path = SoftwareCatalog.find_configured(SoftwareCatalog.DSH, saved.dsh_path)

        Diagnostics.trace(
            "detected | magpie="
            + (magpie_path or "(null)")
            + " | dsh="
            + (dsh_path or "(null)")
        )

        if force_settings or magpie_path is None or dsh_path is None:
            initial = LauncherSettings(
                magpie_path=magpie_path or saved.magpie_path,
                dsh_path=dsh_path or saved.dsh_path,
            )
            Log.info(
                "Opening settings | magpie="
                + (magpie_path or "(not found)")
                + " | dsh="
                + (dsh_path or "(not found)")
            )
            form = SettingsForm(initial)
            form.setWindowIcon(icon)
            if form.exec() != SettingsForm.DialogCode.Accepted:
                Diagnostics.trace("Main exit without launching")
                return 0
            magpie_path = form.magpie_path
            dsh_path = form.dsh_path

        Log.info(f"Launching | magpie={magpie_path} | dsh={dsh_path}")

        window = LauncherForm(magpie_path or "", dsh_path or "")
        window.show()
        window.raise_()
        window.activateWindow()
        code = app.exec()
        Diagnostics.trace("Main exit")
        return int(code)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        report_fatal(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
