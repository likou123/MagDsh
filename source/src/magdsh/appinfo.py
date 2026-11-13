"""软件目录、配置存储、进程启动与日志（对应原 C# AppInfo.cs）。"""

from __future__ import annotations

import ctypes
import os
import shutil
import socket
import subprocess
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only application
    winreg = None


# ---------------------------------------------------------------- 软件规格
class AppKind:
    MAGPIE = "magpie"
    DSH = "dsh"


@dataclass
class SoftwareSpec:
    kind: str
    key: str
    display_name: str
    description: str
    exe_name: str
    default_paths: List[str]
    search_roots: List[str]
    package_roots: List[str] = field(default_factory=list)


def _expand(raw: Optional[str]) -> Optional[str]:
    if not raw or not raw.strip():
        return None
    value = os.path.expandvars(os.path.expanduser(raw.strip().strip('"')))
    return value or None


_REG_UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
_REG_APP_PATHS = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
_REG_MAGPIE = r"Software\magpie"
_REG_VIEWS = (0x0100, 0x0200)  # KEY_WOW64_64KEY, KEY_WOW64_32KEY


def _clean_registry_path(raw: Optional[str]) -> Optional[str]:
    """Normalize registry paths such as '\"C:\\App\\app.exe\",0'."""
    if not raw or not raw.strip():
        return None
    value = raw.strip()
    if value.startswith('"'):
        end = value.find('"', 1)
        value = value[1:end] if end > 0 else value[1:]
    else:
        # DisplayIcon often appends ",0" to an unquoted executable path.
        if value.lower().endswith(",0"):
            value = value[:-2]
    return _expand(value.strip().strip('"'))


def _registry_value(root: int, key_path: str, value_name: str, view: int) -> Optional[str]:
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ | view) as key:
            value, _kind = winreg.QueryValueEx(key, value_name)
            return str(value) if value is not None else None
    except OSError:
        return None


def _trace_discovery(spec: SoftwareSpec, source: str, path: str) -> None:
    try:
        Diagnostics.trace(f"Discovery {spec.key} | {source} | {path}")
    except Exception:
        pass


class SoftwareCatalog:
    MAGPIE = SoftwareSpec(
        kind=AppKind.MAGPIE,
        key="magpie",
        display_name="Magpie",
        description="AI 模型路由网关",
        exe_name="magpie.exe",
        default_paths=[
            r"%LOCALAPPDATA%\Programs\magpie\magpie.exe",
            r"%ProgramFiles%\Magpie\Magpie.exe",
            r"%ProgramFiles(x86)%\Magpie\Magpie.exe",
            r"%USERPROFILE%\scoop\apps\magpie\current\Magpie.exe",
        ],
        search_roots=[
            r"%LOCALAPPDATA%\Programs",
            r"%ProgramFiles%",
            r"%ProgramFiles(x86)%",
        ],
        package_roots=[
            r"%LOCALAPPDATA%\Microsoft\WinGet\Packages",
            r"%USERPROFILE%\scoop\apps",
            r"%ProgramData%\chocolatey\lib",
        ],
    )

    DSH = SoftwareSpec(
        kind=AppKind.DSH,
        key="dsh",
        display_name="DeepSeek Harness",
        description="DeepSeek Harness 桌面端",
        exe_name="DeepSeek Harness.exe",
        default_paths=[
            r"%LOCALAPPDATA%\Programs\DeepSeek Harness\DeepSeek Harness.exe",
            r"%ProgramFiles%\DeepSeek Harness\DeepSeek Harness.exe",
            r"%ProgramFiles(x86)%\DeepSeek Harness\DeepSeek Harness.exe",
        ],
        search_roots=[
            r"%LOCALAPPDATA%\Programs",
            r"%ProgramFiles%",
            r"%ProgramFiles(x86)%",
        ],
        package_roots=[
            r"%LOCALAPPDATA%\Microsoft\WinGet\Packages",
            r"%USERPROFILE%\scoop\apps",
            r"%ProgramData%\chocolatey\lib",
        ],
    )

    @staticmethod
    def all() -> Iterable[SoftwareSpec]:
        yield SoftwareCatalog.MAGPIE
        yield SoftwareCatalog.DSH

    # -------------------------------------------------------- 查找
    @staticmethod
    def detect_default(spec: SoftwareSpec) -> Optional[str]:
        seen = set()
        for source, raw in SoftwareCatalog._candidate_sources(spec):
            path = SoftwareCatalog._candidate_path(spec, raw)
            if not path:
                continue
            normalized = os.path.normcase(os.path.abspath(path))
            if normalized in seen:
                continue
            seen.add(normalized)
            _trace_discovery(spec, source, path)
            return path
        return None

    @staticmethod
    def _candidate_path(spec: SoftwareSpec, raw: Optional[str]) -> Optional[str]:
        candidate = _clean_registry_path(raw)
        if not candidate:
            return None

        if os.path.isfile(candidate):
            if SoftwareCatalog.is_expected_executable(spec, candidate):
                return os.path.abspath(candidate)
            if spec.kind == AppKind.MAGPIE and os.path.basename(candidate).lower() == "magpie.com":
                sibling = os.path.join(os.path.dirname(candidate), "magpie.exe")
                if SoftwareCatalog.is_expected_executable(spec, sibling):
                    return os.path.abspath(sibling)
            return None

        if os.path.isdir(candidate):
            return SoftwareCatalog._find_in_directory(spec, candidate, 3, 320)
        return None

    @staticmethod
    def _candidate_sources(spec: SoftwareSpec):
        """Yield (source, raw path) in priority order."""
        yield from SoftwareCatalog._registry_candidates(spec)

        for path in _process_image_paths([spec.exe_name]):
            yield "running", path

        which = shutil.which(spec.exe_name)
        if which:
            yield "path", which
        if spec.kind == AppKind.MAGPIE:
            shim = shutil.which("magpie.com")
            if shim:
                yield "path-shim", os.path.join(os.path.dirname(shim), "magpie.exe")

        for raw in spec.default_paths:
            yield "default", raw

        for raw in spec.package_roots:
            root = _expand(raw)
            if not root or not os.path.isdir(root):
                continue
            tokens = ("magpie",) if spec.kind == AppKind.MAGPIE else ("deepseek", "harness", "dsh")
            try:
                entries = list(os.scandir(root))
            except OSError:
                continue
            for entry in entries:
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                if not any(token in entry.name.lower() for token in tokens):
                    continue
                found = SoftwareCatalog._find_in_directory(spec, entry.path, 3, 120)
                if found:
                    yield "package", found

        for raw in spec.search_roots:
            root = _expand(raw)
            if not root or not os.path.isdir(root):
                continue
            found = SoftwareCatalog._find_in_directory(spec, root, 3, 320)
            if found:
                yield "scan", found

    @staticmethod
    def _registry_candidates(spec: SoftwareSpec):
        if winreg is None:
            return
        # Magpie records a user-chosen install folder in HKCU\Software\magpie.
        if spec.kind == AppKind.MAGPIE:
            for view in _REG_VIEWS:
                value = _registry_value(
                    winreg.HKEY_CURRENT_USER, _REG_MAGPIE, "InstallLocation", view
                )
                if value:
                    yield "magpie-install-key", value

        # App Paths covers PATH-style registration, including per-machine installs.
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in _REG_VIEWS:
                value = _registry_value(
                    root,
                    _REG_APP_PATHS + "\\" + spec.exe_name,
                    "",
                    view,
                )
                if value:
                    yield "app-paths", value

        # NSIS/electron-builder and Magpie's uninstaller both publish InstallLocation.
        needles = (
            ("magpie",)
            if spec.kind == AppKind.MAGPIE
            else ("deepseek harness", "deepseek-harness")
        )
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in _REG_VIEWS:
                uninstall_key = _REG_UNINSTALL
                try:
                    with winreg.OpenKey(
                        root, uninstall_key, 0, winreg.KEY_READ | view
                    ) as key:
                        index = 0
                        while True:
                            try:
                                subkey_name = winreg.EnumKey(key, index)
                            except OSError:
                                break
                            index += 1
                            subkey_path = uninstall_key + "\\" + subkey_name
                            display = _registry_value(
                                root, subkey_path, "DisplayName", view
                            )
                            if not display:
                                continue
                            lowered = display.lower()
                            if not any(needle in lowered for needle in needles):
                                continue
                            location = _registry_value(
                                root, subkey_path, "InstallLocation", view
                            )
                            if location:
                                yield "uninstall-location", location
                            icon = _registry_value(
                                root, subkey_path, "DisplayIcon", view
                            )
                            if icon:
                                yield "uninstall-icon", icon
                except OSError:
                    continue

    @staticmethod
    def find_configured(spec: SoftwareSpec, configured_path: Optional[str]) -> Optional[str]:
        normalized = SoftwareCatalog.resolve_selection(spec, configured_path)
        if normalized:
            return normalized
        return SoftwareCatalog.detect_default(spec)

    @staticmethod
    def resolve_selection(spec: SoftwareSpec, value: Optional[str]) -> Optional[str]:
        """接受 exe 路径或文件夹（含上级目录），只在命中预期 exe 名时返回完整路径。"""
        if not value or not value.strip():
            return None

        path = _expand(value.strip().strip('"'))
        if not path:
            return None

        try:
            if os.path.isfile(path):
                return os.path.abspath(path) if SoftwareCatalog.is_expected_executable(spec, path) else None
            if os.path.isdir(path):
                return SoftwareCatalog._find_in_directory(spec, path, 3, 360)
        except OSError:
            pass
        return None

    @staticmethod
    def is_expected_executable(spec: SoftwareSpec, path: Optional[str]) -> bool:
        if not path or not path.strip():
            return False
        try:
            if not os.path.isfile(path):
                return False
            return os.path.basename(path).lower() == spec.exe_name.lower()
        except OSError:
            return False

    @staticmethod
    def _find_in_directory(spec: SoftwareSpec, directory: str, depth: int, limit: int) -> Optional[str]:
        queue = [(directory, 0)]
        visited = 0

        while queue and visited < limit:
            current, level = queue.pop(0)
            visited += 1
            try:
                direct = os.path.join(current, spec.exe_name)
                if os.path.isfile(direct):
                    return os.path.abspath(direct)

                try:
                    for name in os.listdir(current):
                        if not name.lower().endswith(".exe"):
                            continue
                        if name.lower() == spec.exe_name.lower():
                            return os.path.abspath(os.path.join(current, name))
                except OSError:
                    pass

                if level >= depth:
                    continue

                try:
                    children = os.listdir(current)
                except OSError:
                    continue

                for child in children:
                    child_path = os.path.join(current, child)
                    try:
                        if not os.path.isdir(child_path):
                            continue
                        # 跳过符号链接 / 目录联接，避免递归环
                        if os.path.islink(child_path):
                            continue
                        attrs = os.stat(child_path).st_file_attributes
                        if attrs & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
                            continue
                    except OSError:
                        continue
                    queue.append((child_path, level + 1))
            except OSError:
                continue

        return None


# ---------------------------------------------------------------- 配置存储
@dataclass
class LauncherSettings:
    magpie_path: str = ""
    dsh_path: str = ""


class SettingsStore:
    @staticmethod
    def config_file_path() -> str:
        override = os.environ.get("MAGDSH_CONFIG")
        if override and override.strip():
            return os.path.abspath(os.path.expandvars(override.strip()))
        local_appdata = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local"
        )
        return os.path.join(local_appdata, "MagDsh", "settings.ini")

    @staticmethod
    def load() -> LauncherSettings:
        settings = LauncherSettings()
        try:
            path = SettingsStore.config_file_path()
            if not os.path.isfile(path):
                return settings

            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle.read().splitlines():
                    equals = line.find("=")
                    if equals <= 0:
                        continue
                    key = line[:equals].strip()
                    value = line[equals + 1 :].strip()
                    if key.lower() == "magpie":
                        settings.magpie_path = value
                    elif key.lower() == "dsh":
                        settings.dsh_path = value
        except OSError:
            pass
        return settings

    @staticmethod
    def save(settings: LauncherSettings) -> bool:
        try:
            path = SettingsStore.config_file_path()
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            text = (
                "# MagDsh launcher settings\n"
                f"magpie={settings.magpie_path or ''}\n"
                f"dsh={settings.dsh_path or ''}\n"
            )

            temp = f"{path}.{os.getpid()}.tmp"
            with open(temp, "w", encoding="utf-8", newline="\r\n") as handle:
                handle.write(text)

            try:
                os.replace(temp, path)
            except OSError:
                with open(temp, "rb") as src, open(path, "wb") as dst:
                    dst.write(src.read())
                os.remove(temp)
            return True
        except OSError:
            return False


# ---------------------------------------------------------------- Win32 辅助
_TH32CS_SNAPPROCESS = 0x2
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32 = ctypes.WinDLL("user32", use_last_error=True)

_kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
_kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
_kernel32.Process32FirstW.restype = wintypes.BOOL
_kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
_kernel32.Process32NextW.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.DeleteFileW.argtypes = [wintypes.LPCWSTR]
_kernel32.DeleteFileW.restype = wintypes.BOOL
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
_kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

_user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.ShowWindowAsync.restype = wintypes.BOOL
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.SetForegroundWindow.restype = wintypes.BOOL
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.IsWindowVisible.restype = wintypes.BOOL
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD

_ENUMWINDOWSPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32.EnumWindows.argtypes = [_ENUMWINDOWSPROC, wintypes.LPARAM]
_user32.EnumWindows.restype = wintypes.BOOL


def _process_ids_by_name(exe_name: str) -> List[int]:
    """枚举所有进程，返回可执行文件名匹配的进程 ID。"""
    result: List[int] = []
    snapshot = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == _INVALID_HANDLE_VALUE:
        return result

    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        if not _kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return result
        while True:
            if (entry.szExeFile or "").lower() == exe_name.lower():
                result.append(int(entry.th32ProcessID))
            if not _kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        _kernel32.CloseHandle(snapshot)
    return result


def _process_image_paths(exe_names: Iterable[str]) -> List[str]:
    """Return executable paths for running processes with one of the names."""
    targets = {name.lower() for name in exe_names if name}
    result: List[str] = []
    snapshot = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == _INVALID_HANDLE_VALUE:
        return result

    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        if not _kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return result
        while True:
            if (entry.szExeFile or "").lower() in targets:
                process = _kernel32.OpenProcess(0x1000, False, entry.th32ProcessID)
                if process:
                    try:
                        buffer = ctypes.create_unicode_buffer(32768)
                        size = wintypes.DWORD(len(buffer))
                        if _kernel32.QueryFullProcessImageNameW(
                            process, 0, buffer, ctypes.byref(size)
                        ):
                            path = buffer.value.strip()
                            if path:
                                result.append(path)
                    finally:
                        _kernel32.CloseHandle(process)
            if not _kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        _kernel32.CloseHandle(snapshot)
    return result


def _windows_for_process(process_ids: List[int]) -> List[int]:
    handles: List[int] = []
    targets = set(process_ids)

    def callback(hwnd, _lparam):
        try:
            if not _user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD(0)
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in targets:
                handles.append(int(hwnd))
        except Exception:
            pass
        return True

    try:
        _user32.EnumWindows(_ENUMWINDOWSPROC(callback), 0)
    except Exception:
        pass
    return handles


class _PortProbe:
    """对应原 C# IsPortListening：回环连接，最多等待 250ms。"""

    @staticmethod
    def listen(port: int, timeout: float = 0.25) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False
        finally:
            try:
                sock.close()
            except OSError:
                pass


# ---------------------------------------------------------------- 启动器
@dataclass
class LaunchOutcome:
    success: bool = False
    message: str = ""


class AppLauncher:
    MAGPIE_PORT = 3425

    @staticmethod
    def is_running(spec: SoftwareSpec) -> bool:
        try:
            if spec.kind == AppKind.MAGPIE and _PortProbe.listen(AppLauncher.MAGPIE_PORT):
                Diagnostics.trace("IsRunning found magpie gateway on port 3425")
                return True

            ids = _process_ids_by_name(spec.exe_name)
            if ids:
                Diagnostics.trace(f"IsRunning found {spec.exe_name} | pid={ids[0]}")
                return True
            return False
        except Exception as exc:
            Diagnostics.trace(f"IsRunning error {spec.exe_name} | {exc}")
            return False

    @staticmethod
    def try_activate(spec: SoftwareSpec) -> None:
        try:
            ids = _process_ids_by_name(spec.exe_name)
            if not ids:
                return
            for hwnd in _windows_for_process(ids):
                _user32.ShowWindowAsync(wintypes.HWND(hwnd), 9)  # SW_RESTORE
                _user32.SetForegroundWindow(wintypes.HWND(hwnd))
        except Exception:
            pass

    @staticmethod
    def hide(spec: SoftwareSpec) -> None:
        """Hide existing top-level windows (used for the Magpie tray-only start)."""
        try:
            ids = _process_ids_by_name(spec.exe_name)
            if not ids:
                return
            for hwnd in _windows_for_process(ids):
                _user32.ShowWindowAsync(wintypes.HWND(hwnd), 0)  # SW_HIDE
        except Exception:
            pass

    @staticmethod
    def start(spec: SoftwareSpec, executable: str) -> LaunchOutcome:
        outcome = LaunchOutcome()
        try:
            if not SoftwareCatalog.is_expected_executable(spec, executable):
                outcome.message = f"{spec.display_name} 的可执行文件不存在：\r\n{executable}"
                return outcome

            directory = os.path.dirname(executable)
            args = [executable]
            if spec.kind == AppKind.MAGPIE:
                # Official magpie CLI: "magpie tray" starts only the tray icon,
                # without opening the main window.
                args.append("tray")
            Diagnostics.trace(
                f"Process.Start {spec.key} | {executable} | args={args[1:]} | cwd={directory}"
            )
            Log.info(
                f"Starting {spec.key} | exe={executable} | args={args[1:]} | cwd={directory} | shell=false"
            )

            started = time.perf_counter()
            creation_flags = 0
            if os.name == "nt":
                creation_flags = subprocess.CREATE_NO_WINDOW
            process = subprocess.Popen(
                args,
                cwd=directory,
                shell=False,
                creationflags=creation_flags,
                close_fds=True,
            )
            elapsed = int((time.perf_counter() - started) * 1000)
            Diagnostics.trace(f"Process.Start OK {spec.key} | pid={process.pid} | {elapsed} ms")
            Log.info(f"Started {spec.key} in {elapsed} ms | pid={process.pid}")

            outcome.success = True
            outcome.message = "已启动"
        except Exception as exc:
            Diagnostics.trace(f"Process.Start FAIL {spec.key} | {exc}")
            outcome.message = f"无法启动 {spec.display_name}。\r\n\r\n{exc}"
        return outcome


# ---------------------------------------------------------------- 日志
def _local_appdata() -> str:
    return os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")


class Diagnostics:
    """对应原 C# Diagnostics：写入 %LOCALAPPDATA%\\MagDsh\\startup.log。"""

    _lock = threading.Lock()

    @staticmethod
    def trace(message: str) -> None:
        try:
            directory = os.path.join(_local_appdata(), "MagDsh")
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, "startup.log")
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            with Diagnostics._lock:
                with open(path, "a", encoding="utf-8", newline="") as handle:
                    handle.write(f"[{stamp}] {message}\r\n")
        except OSError:
            pass


class Log:
    """对应原 C# Log：写入 %LOCALAPPDATA%\\MagDsh\\MagDsh.log，超过 256KB 重建。"""

    _lock = threading.Lock()

    @staticmethod
    def file_path() -> str:
        override = os.environ.get("MAGDSH_LOG")
        if override and override.strip():
            return os.path.abspath(os.path.expandvars(override.strip()))
        return os.path.join(_local_appdata(), "MagDsh", "MagDsh.log")

    @staticmethod
    def error(context: str, exc: Optional[BaseException]) -> None:
        Log._write(context, "(no exception)" if exc is None else repr(exc))

    @staticmethod
    def info(message: str) -> None:
        Log._write(message, None)

    @staticmethod
    def _write(context: str, detail: Optional[str]) -> None:
        try:
            path = Log.file_path()
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            if os.path.isfile(path) and os.path.getsize(path) > 256 * 1024:
                os.remove(path)

            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            text = f"[{stamp}] {context}\n"
            if detail is not None:
                text += detail + "\n"
            text += "\n"

            with Log._lock:
                with open(path, "a", encoding="utf-8", newline="") as handle:
                    handle.write(text)
        except OSError:
            pass
