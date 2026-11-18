"""U 盘识别、安全检查、写入。

设计原则：所有破坏性操作都要「显式确认」，默认只做只读探测。
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .util import human_size, log, require, run_ps_json

DISK_QUERY = r"""
$ProgressPreference='SilentlyContinue'
Get-Disk | Where-Object BusType -eq 'USB' | ForEach-Object {
  $d = $_
  $v = Get-Partition -DiskNumber $d.Number -ErrorAction SilentlyContinue |
       Get-Volume -ErrorAction SilentlyContinue | Where-Object DriveLetter
  [pscustomobject]@{
    Number = $d.Number
    Name   = $d.FriendlyName
    SizeGB = [math]::Round($d.Size/1GB, 1)
    BusType= $d.BusType
    Letters= @($v | ForEach-Object { $_.DriveLetter })
    FS     = (@($v | ForEach-Object { $_.FileSystem }) -join ',')
    Health = $d.HealthStatus
  }
} | ConvertTo-Json -Depth 3
"""


@dataclass
class UsbDisk:
    number: int
    name: str
    size_gb: float
    letters: list[str]
    fs: str
    health: str

    @property
    def volume(self) -> Path | None:
        for letter in self.letters:
            p = Path(f"{letter}:\\")
            if p.exists():
                return p
        return None


def list_usb() -> list[UsbDisk]:
    data = run_ps_json(DISK_QUERY) or []
    if isinstance(data, dict):
        data = [data]
    result = []
    for item in data:
        result.append(UsbDisk(
            number=int(item.get("Number", 0)),
            name=item.get("Name") or "USB",
            size_gb=float(item.get("SizeGB") or 0),
            letters=[str(x) for x in (item.get("Letters") or [])],
            fs=item.get("FS") or "",
            health=item.get("Health") or "",
        ))
    return result


def guard(disk: UsbDisk) -> None:
    """写入前的硬性门槛，任何一条不满足直接中止。"""
    require(disk.size_gb >= 7.4, f"容量不足：{disk.size_gb}GB，至少需要 8GB")
    require(disk.health in ("Healthy", "未知", ""), f"磁盘健康状态异常：{disk.health}")
    require(disk.volume is not None, "U 盘没有可用的盘符，先格式化并分配盘符")
    # 系统盘保护：盘符所在磁盘号必须等于枚举出来的 USB 磁盘号
    letter = disk.volume.drive
    check = run_ps_json(
        f"$p=Get-Partition -DriveLetter {letter[0]} -ErrorAction Stop;"
        "$p | Select-Object DiskNumber | ConvertTo-Json")
    if isinstance(check, dict) and int(check.get("DiskNumber", -1)) != disk.number:
        raise RuntimeError("盘符与 USB 磁盘号不匹配，疑似指向系统盘，已中止")


def format_fat32(disk: UsbDisk, label: str = "MACBOOT", *, confirm: str) -> None:
    """仅在用户输入 YES 且确认是 USB 盘时执行。"""
    require(confirm == "YES", "格式化被取消：需要显式确认")
    guard(disk)
    require(len(label) <= 11 and label.isascii(), "卷标必须是 ≤11 位的 ASCII 字符")
    log(f"格式化磁盘 {disk.number}（{disk.name} / {disk.size_gb}GB）→ FAT32 / {label}", level="WARN")
    run_ps_json(
        f"$ProgressPreference='SilentlyContinue';"
        f"Format-Volume -DiskNumber {disk.number} -FileSystem FAT32 "
        f"-NewFileSystemLabel '{label}' -Confirm:$false | Out-Null;"
        "Get-Volume | Where-Object FileSystemLabel -eq '" + label + "' | "
        "Select-Object DriveLetter,FileSystem,Size | ConvertTo-Json")


README_TEMPLATE = """MacPlan 启动盘
================

1. 关机，插上这块 U 盘，开机连按 F9（HP 机型）或其他品牌对应的启动菜单键
2. 选择 U 盘里的 EFI 项 → 进入 OpenCore 菜单
3. 如果只看到 Windows：按空格展开隐藏项
4. 选择带 macOS 图标的项（名称可能是 ___U___，这是中文卷标在 OpenCanopy 下没有字形导致的）
5. 进入恢复环境 → 先用「磁盘工具」抹掉整块硬盘（APFS / GUID），再「重新安装 macOS」
6. 装完第一次进系统后，先把 U 盘里的 EFI 拷进硬盘 ESP，再拔 U 盘
7. Wi-Fi 密码是明文写在 EFI 里的，用 HeliPort 连上后请立刻清除

详细步骤见仓库 docs/使用手册.md
"""


def write_payload(disk: UsbDisk, efi_dir: Path, recovery_dir: Path) -> Path:
    guard(disk)
    volume = disk.volume
    assert volume is not None
    require(efi_dir.exists(), f"EFI 目录不存在：{efi_dir}")
    require(recovery_dir.exists(), f"恢复镜像目录不存在：{recovery_dir}")

    log(f"写入 EFI → {volume / 'EFI'}")
    shutil.copytree(efi_dir, volume / "EFI", dirs_exist_ok=True)

    log(f"写入恢复镜像 → {volume / 'com.apple.recovery.boot'}")
    shutil.copytree(recovery_dir, volume / "com.apple.recovery.boot", dirs_exist_ok=True)

    (volume / "使用说明.txt").write_text(README_TEMPLATE, encoding="utf-8-sig")
    log(f"写入完成，可用空间 {human_size(shutil.disk_usage(volume).free)}")
    return volume
