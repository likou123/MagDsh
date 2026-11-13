"""消息框封装：保持中文按钮与系统一致的交互。"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def _message_box(parent: QWidget | None, title: str, text: str, icon) -> QMessageBox:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(icon)
    box.setText(text)
    box.setWindowIcon(parent.windowIcon() if parent is not None else box.windowIcon())
    return box


def info(parent: QWidget | None, text: str, title: str = "MagDsh") -> None:
    box = _message_box(parent, title, text, QMessageBox.Information)
    box.addButton("确定", QMessageBox.AcceptRole)
    box.exec()


def warn(parent: QWidget | None, text: str, title: str = "MagDsh") -> None:
    box = _message_box(parent, title, text, QMessageBox.Warning)
    box.addButton("确定", QMessageBox.AcceptRole)
    box.exec()


def error(parent: QWidget | None, text: str, title: str = "MagDsh") -> None:
    box = _message_box(parent, title, text, QMessageBox.Critical)
    box.addButton("确定", QMessageBox.AcceptRole)
    box.exec()


def confirm(parent: QWidget | None, text: str, title: str = "MagDsh") -> bool:
    """对应 MessageBoxButtons.YesNo + 警告图标，返回 True 表示选择“是”。"""
    box = _message_box(parent, title, text, QMessageBox.Warning)
    yes = box.addButton("是", QMessageBox.YesRole)
    box.addButton("否", QMessageBox.NoRole)
    box.setDefaultButton(yes)
    box.exec()
    return box.clickedButton() is yes
