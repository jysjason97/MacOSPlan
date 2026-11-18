"""PyInstaller 入口：绝对导入 + 强制控制台 UTF-8（否则中文在 GBK 代码页下会乱码）。"""
import sys

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:  # noqa: BLE001
        pass

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from macplan.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
