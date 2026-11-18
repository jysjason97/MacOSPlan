"""Wi-Fi 凭据采集与 itlwm 预置。

安全边界：
- 只在本地 netsh 读取，不联网、不上传；
- 只在用户明确同意后写入 EFI；
- 写入的是明文，说明书里必须提示「装完清除」。
"""
from __future__ import annotations

import plistlib
import re
from pathlib import Path

from .util import log

SSID_RE = re.compile(r"SSID[^:：]*[：:]\s*(.+)")
KEY_RE = re.compile(r"(?:关键内容|Key Content)[^:：]*[：:]\s*(.*)")


def list_profiles() -> list[str]:
    from .util import run_ps
    out = run_ps('netsh wlan show profiles | Out-String')
    names: list[str] = []
    for line in out.splitlines():
        if ":" not in line and "：" not in line:
            continue
        value = re.split(r"[:：]", line, maxsplit=1)[-1].strip()
        if not value or value in {"Name", "名称"}:
            continue
        names.append(value)
    return names


def profile_detail(name: str) -> dict[str, str]:
    from .util import run_ps
    out = run_ps(f'chcp 65001 > $null; netsh wlan show profile name="{name}" key=clear | Out-String')
    result: dict[str, str] = {"profile": name}
    for line in out.splitlines():
        m = SSID_RE.search(line)
        if m:
            result["ssid"] = m.group(1).strip()
        m = KEY_RE.search(line)
        if m:
            result["password"] = m.group(1).strip()
    result.setdefault("ssid", name)
    return result


def collect(include_passwords: bool = True) -> list[dict[str, str]]:
    profiles = []
    for name in list_profiles():
        try:
            profiles.append(profile_detail(name))
        except Exception as exc:  # noqa: BLE001
            log(f"读取 Wi-Fi 配置失败：{name} / {exc}", level="WARN")
    log(f"共读取 {len(profiles)} 个 Wi-Fi 配置")
    return profiles


def find_itlwm_info_plist(efi_dir: Path) -> Path | None:
    for p in efi_dir.rglob("itlwm.kext/Contents/Info.plist"):
        return p
    return None


def patch_itlwm(kext_info: Path, profiles: list[dict[str, str]]) -> int:
    """把 SSID/密码写进 WiFiConfig，返回写入条目数。"""
    raw = kext_info.read_bytes()
    is_binary = raw.startswith(b"bplist00")
    data = plistlib.loads(raw)

    entries = [
        {"ssid": p["ssid"], "password": p.get("password", "")}
        for p in profiles
        if p.get("ssid") and p.get("password")
    ]
    if not entries:
        return 0
    data["WiFiConfig"] = entries
    kext_info.write_bytes(plistlib.dumps(
        data, fmt=plistlib.FMT_BINARY if is_binary else plistlib.FMT_XML))
    log(f"已向 itlwm 写入 {len(entries)} 组 Wi-Fi（明文，装完请清除）", level="WARN")
    return len(entries)


def wipe_itlwm(kext_info: Path) -> bool:
    raw = kext_info.read_bytes()
    is_binary = raw.startswith(b"bplist00")
    data = plistlib.loads(raw)
    if "WiFiConfig" not in data:
        return False
    data.pop("WiFiConfig")
    kext_info.write_bytes(plistlib.dumps(
        data, fmt=plistlib.FMT_BINARY if is_binary else plistlib.FMT_XML))
    return True
