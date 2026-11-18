"""通用工具：命令执行、下载、哈希、日志。"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

APP_NAME = "MacPlan"
REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / ".cache"
TOOLS_DIR = REPO_ROOT / "tools"
LOG_DIR = REPO_ROOT / "logs"
USER_AGENT = "MacPlan/1.0 (+https://github.com/jysjason97/macplan)"


def ensure_dirs() -> None:
    for d in (CACHE_DIR, TOOLS_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def log(message: str, *, level: str = "INFO", echo: bool = True) -> None:
    ensure_dirs()
    line = f"[{time.strftime('%H:%M:%S')}][{level}] {message}"
    if echo:
        print(line, flush=True)
    with open(LOG_DIR / "macplan.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def run_ps(script: str, timeout: int = 180) -> str:
    """执行 PowerShell 片段并返回 stdout；失败抛 RuntimeError。"""
    ps = shutil.which("pwsh") or shutil.which("powershell")
    if not ps:
        raise RuntimeError("找不到 PowerShell")
    proc = subprocess.run(
        [ps, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"PowerShell 失败({proc.returncode}): {proc.stderr.strip()[:800]}")
    return proc.stdout.strip()


def run_ps_json(script: str) -> object:
    out = run_ps("$ProgressPreference='SilentlyContinue';" + script)
    return json.loads(out) if out else None


def download(url: str, dst: Path, *, retries: int = 3, timeout: int = 60) -> Path:
    """带 UA、断点重试的下载。已存在且非空则跳过。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(dst, "wb") as fh:
                shutil.copyfileobj(resp, fh)
            if dst.stat().st_size == 0:
                raise RuntimeError("下载到 0 字节")
            return dst
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            log(f"下载失败 {url} ({attempt}/{retries}): {exc}", level="WARN")
            if dst.exists():
                dst.unlink(missing_ok=True)
            time.sleep(2 * attempt)
    raise RuntimeError(f"下载失败：{url}") from last_err


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            result[str(p.relative_to(root)).replace("\\", "/")] = sha256_file(p)
    return result


def human_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}TB"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def is_windows() -> bool:
    return sys.platform.startswith("win")
