"""恢复镜像下载：封装 OpenCorePkg 的 macrecovery。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .compat import BOARD_ID, VERSION_NAME
from .util import TOOLS_DIR, download, log, sha256_file

MACRECOVERY_URL = (
    "https://raw.githubusercontent.com/acidanthera/OpenCorePkg/master/"
    "Utilities/macrecovery/macrecovery.py"
)
MIN_DMG_BYTES = 300 * 1024 * 1024   # 正常 BaseSystem.dmg 都在 400MB 以上


def ensure_macrecovery() -> Path:
    return download(MACRECOVERY_URL, TOOLS_DIR / "macrecovery.py")


def check_dmg(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "文件不存在"
    size = path.stat().st_size
    if size < MIN_DMG_BYTES:
        return False, f"体积异常：{size} 字节（疑似下载被截断）"
    with open(path, "rb") as fh:
        fh.seek(-512, 2)
        trailer = fh.read(4)
    if trailer != b"koly":
        return False, "DMG 尾部缺少 koly 魔数，文件已损坏"
    return True, f"{size} 字节 / SHA256 {sha256_file(path)[:16]}…"


def download_recovery(version: str, out_dir: Path) -> Path:
    """下载指定版本的恢复镜像，返回 com.apple.recovery.boot 目录。"""
    board = BOARD_ID.get(version)
    if not board:
        raise RuntimeError(
            f"没有 {version} 的内置 board-id。请到 Dortania 指南核对后手工执行 macrecovery。"
        )
    script = ensure_macrecovery()
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"下载 macOS {VERSION_NAME.get(version, version)} 恢复镜像（board-id {board}）…")
    proc = subprocess.run(
        [sys.executable, str(script), "-b", board, "-m", "00000000000000000", "download"],
        cwd=str(out_dir), capture_output=True, text=True, timeout=1800,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"macrecovery 失败：{proc.stdout[-400:]} {proc.stderr[-400:]}")

    boot_dir = out_dir / "com.apple.recovery.boot"
    dmg = boot_dir / "BaseSystem.dmg"
    ok, detail = check_dmg(dmg)
    if not ok:
        raise RuntimeError(f"恢复镜像校验失败：{detail}")
    log(f"恢复镜像就绪：{detail}")
    return boot_dir
