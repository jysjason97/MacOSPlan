"""硬件采集：优先 Hardware-Sniffer，失败时退回 WMI 快照。"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .util import CACHE_DIR, TOOLS_DIR, download, log, run_ps_json

SNIFFER_VERSION = "2.1.2"
SNIFFER_URL = (
    "https://github.com/lzhoang2801/Hardware-Sniffer/releases/download/"
    f"{SNIFFER_VERSION}/Hardware-Sniffer-CLI.exe"
)

WMI_SCRIPT = r"""
$ProgressPreference='SilentlyContinue'
$cs  = Get-CimInstance Win32_ComputerSystem
$bb  = Get-CimInstance Win32_BaseBoard
$cpu = Get-CimInstance Win32_Processor
$gpu = Get-CimInstance Win32_VideoController
$mem = Get-CimInstance Win32_PhysicalMemory
$net = Get-CimInstance Win32_NetworkAdapter -Filter "PhysicalAdapter=True"
$disk= Get-CimInstance Win32_DiskDrive
$bios= Get-CimInstance Win32_BIOS
$sb = "unknown"
try { $sb = Confirm-SecureBootUEFI } catch { }
[pscustomobject]@{
  Vendor   = $cs.Manufacturer
  Model    = $cs.Model
  BoardVendor = $bb.Manufacturer
  BoardProduct= $bb.Product
  BiosVersion = $bios.SMBIOSBIOSVersion
  BiosDate = $bios.ReleaseDate
  CpuName  = $cpu.Name
  CpuCores = $cpu.NumberOfCores
  CpuThreads = $cpu.NumberOfLogicalProcessors
  MemoryGB = [math]::Round(($mem | Measure-Object -Property Capacity -Sum).Sum / 1GB, 1)
  MemoryModules = @($mem | ForEach-Object { [pscustomobject]@{ SizeGB=[math]::Round($_.Capacity/1GB,1); Speed=$_.Speed; Part=$_.PartNumber } })
  Gpus = @($gpu | ForEach-Object { [pscustomobject]@{ Name=$_.Name; PnpId=$_.PNPDeviceID; Driver=$_.DriverVersion } })
  Networks = @($net | ForEach-Object { [pscustomobject]@{ Name=$_.Name; PnpId=$_.PNPDeviceID; Mac=$_.MACAddress } })
  Disks = @($disk | ForEach-Object { [pscustomobject]@{ Model=$_.Model; SizeGB=[math]::Round($_.Size/1GB,0); Interface=$_.InterfaceType; Media=$_.MediaType } })
  SecureBoot = $sb
  Firmware = $env:firmware_type
} | ConvertTo-Json -Depth 4
"""


def ensure_sniffer() -> Path | None:
    """下载 Hardware-Sniffer CLI；失败返回 None，由调用方退回 WMI。"""
    try:
        return download(SNIFFER_URL, TOOLS_DIR / f"Hardware-Sniffer-CLI-{SNIFFER_VERSION}.exe")
    except Exception as exc:  # noqa: BLE001
        log(f"Hardware-Sniffer 不可用：{exc}", level="WARN")
        return None


def scan_with_sniffer(out_dir: Path) -> Path | None:
    exe = ensure_sniffer()
    if not exe:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    for args in (["-e", "-o", str(out_dir)], []):
        try:
            proc = subprocess.run([str(exe), *args], cwd=str(out_dir),
                                  capture_output=True, text=True, timeout=300)
            report = out_dir / "Report.json"
            if report.exists() and report.stat().st_size > 0:
                log(f"Hardware-Sniffer 输出：{report}")
                return report
            log(f"Hardware-Sniffer 返回码 {proc.returncode}，重试另一种参数", level="WARN")
        except Exception as exc:  # noqa: BLE001
            log(f"Hardware-Sniffer 执行失败：{exc}", level="WARN")
    return None


def scan_with_wmi() -> dict:
    data = run_ps_json(WMI_SCRIPT)
    return data if isinstance(data, dict) else {}


def normalize(report_json: Path | None, wmi: dict) -> dict:
    """把两种来源归一成同一种结构，供 compat 使用。"""
    result = {
        "source": "wmi",
        "vendor": wmi.get("Vendor") or "",
        "model": wmi.get("Model") or "",
        "board": f"{wmi.get('BoardVendor','')} {wmi.get('BoardProduct','')}".strip(),
        "bios": wmi.get("BiosVersion") or "",
        "cpu": wmi.get("CpuName") or "",
        "cores": wmi.get("CpuCores"),
        "memory_gb": wmi.get("MemoryGB"),
        "gpus": [g.get("Name", "") for g in (wmi.get("Gpus") or [])],
        "networks": [n.get("Name", "") for n in (wmi.get("Networks") or [])],
        "storage": [d.get("Model", "") for d in (wmi.get("Disks") or [])],
        "secure_boot": wmi.get("SecureBoot"),
        "firmware": wmi.get("Firmware"),
    }
    if report_json and report_json.exists():
        try:
            raw = json.loads(report_json.read_text(encoding="utf-8"))
            result["source"] = "hardware-sniffer"
            result["sniffer"] = raw
            # Sniffer 的键是「型号 → 属性」的字典，用它补全型号列表
            cpu = raw.get("CPU")
            if isinstance(cpu, dict):
                name = (cpu.get("Processor Name") or cpu.get("Model")
                        or cpu.get("Name") or cpu.get("Processor"))
                if name:
                    result["cpu"] = str(name)
            gpu = raw.get("GPU") or raw.get("Graphics") or {}
            if isinstance(gpu, dict) and gpu:
                result["gpus"] = list(gpu.keys())
            net = raw.get("Network") or {}
            if isinstance(net, dict) and net:
                result["networks"] = list(net.keys())
        except Exception as exc:  # noqa: BLE001
            log(f"Report.json 解析失败：{exc}", level="WARN")
    return result


def collect(out_dir: Path) -> dict:
    report = scan_with_sniffer(out_dir)
    wmi = scan_with_wmi()
    merged = normalize(report, wmi)
    merged["report_json"] = str(report) if report else None
    (CACHE_DIR / "hardware.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


CPU_RE = re.compile(r"i[3579][- ]?(\d{4,5})([A-Z]{0,2})", re.I)
ULTRA_RE = re.compile(r"Ultra\s*[579]", re.I)
RYZEN_RE = re.compile(r"Ryzen\s*(\d)", re.I)


def cpu_generation(cpu_name: str) -> int:
    """Intel 型号号 → 代次；Core Ultra 记为 15；AMD 返回 0；未知 -1。"""
    if ULTRA_RE.search(cpu_name):
        return 15
    m = CPU_RE.search(cpu_name)
    if m:
        num = m.group(1)
        return int(num[0]) if len(num) == 4 else int(num[:2])
    if RYZEN_RE.search(cpu_name):
        return 0
    return -1
