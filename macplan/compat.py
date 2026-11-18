"""可行性判定与 macOS 版本推荐。

判定原则：只推荐「原生支持到的那一代」，不做越级。
越级 = 需要打补丁 = 这台机器上多出来的不确定性。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .hardware import cpu_generation

# CPU 代次 → (推荐版本, 原生最高版本, 说明)
# 只写到能被 OpenCore 正常驱动的范围；更老的机器建议直接放弃。
INTEL_TABLE: dict[int, tuple[str, str, str]] = {
    1: ("unsupported", "unsupported", "Nehalem/Arrandale：无核显加速，macOS 无实用价值"),
    2: ("10.13", "10.13", "Sandy Bridge：需大量补丁，仅 High Sierra"),
    3: ("10.15", "10.15", "Ivy Bridge：Catalina 为原生上限"),
    4: ("11", "11", "Haswell：Big Sur 为原生上限，Monterey 起被砍"),
    5: ("12", "12", "Broadwell：Monterey 为原生上限"),
    6: ("12", "12", "Skylake：Monterey 为原生上限，Ventura 起被砍"),
    7: ("13", "13", "Kaby Lake：Ventura 为原生上限"),
    8: ("13", "14", "Kaby Lake-R / Coffee Lake：Ventura 稳，Sonoma 可试（机型需按 2018 款）"),
    9: ("14", "14", "Coffee Lake Refresh：Sonoma"),
    10: ("14", "14", "Comet Lake：Sonoma"),
    11: ("15", "15", "Tiger Lake：Sequoia"),
    12: ("15", "15", "Alder Lake：Sequoia，需注意大小核调度"),
    13: ("15", "15", "Raptor Lake：Sequoia，需注意大小核调度"),
}

SMBIOS_BY_GEN = {
    3: "MacBookPro10,1",
    4: "MacBookPro11,1",
    5: "MacBookPro12,1",
    6: "MacBookPro13,1",
    7: "MacBookPro14,1",
    8: "MacBookPro15,2",
    9: "MacBookPro15,1",
    10: "MacBookPro16,2",
    11: "MacBookPro16,3",
    12: "MacBookPro17,1",
    13: "MacBookPro18,3",
}

# macrecovery 使用的 board-id（对应 Dortania 指南里的机型）
BOARD_ID = {
    "10.13": "Mac-7BA5B2D9E42DDD94",
    "10.14": "Mac-7BA5B2DFE22DDD8C",
    "10.15": "Mac-00BE6ED71E35EB86",
    "11": "Mac-42FD25EABCABB274",
    "12": "Mac-FFE5EF870D7BA81A",
    "13": "Mac-4B682C642B45593E",
    "14": "Mac-827FAC58A8FDFA22",
}

VERSION_NAME = {
    "10.13": "High Sierra",
    "10.14": "Mojave",
    "10.15": "Catalina",
    "11": "Big Sur",
    "12": "Monterey",
    "13": "Ventura",
    "14": "Sonoma",
    "15": "Sequoia",
}

# 受支持的 AMD 独显（有核显时只是加分项，无核显时是唯一出路）
AMD_SUPPORTED = ("RX 460", "RX 470", "RX 480", "RX 550", "RX 560", "RX 570", "RX 580",
                 "RX 590", "RX 5500", "RX 5600", "RX 5700", "RX 6600", "RX 6800", "RX 6900")
NVIDIA_UNSUPPORTED = ("GTX", "RTX", "MX", "Quadro", "GT ")

# Stela：把 arm64 macOS 翻译成 x86-64 执行的路线，只认 NVIDIA 独显
# 依据 https://github.com/tylertms/Stela 的 Hardware requirements
STELA_GPU_RE = re.compile(r"(GTX\s*16|RTX\s*(20|30|40|50))", re.I)
AMD_CPU_RE = re.compile(r"(Ryzen|Threadripper|EPYC|FX-|Bulldozer)", re.I)
STELA_MIN_MEMORY_GB = 8


@dataclass
class Recommendation:
    verdict: str                     # supported / workable / stela / unsupported
    version: str | None
    version_name: str | None
    board_id: str | None
    smbios: str | None
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    wifi_mode: str | None = None     # itlwm / native / none
    route: str = "opencore"          # opencore / stela / none
    stela: dict[str, Any] | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict, "version": self.version,
            "version_name": self.version_name, "board_id": self.board_id,
            "smbios": self.smbios, "reasons": self.reasons, "risks": self.risks,
            "todos": self.todos, "wifi_mode": self.wifi_mode,
            "route": self.route, "stela": self.stela,
        }


def evaluate_stela(hw: dict) -> dict:
    """判断这台机器能不能走 Stela（arm64 → x86-64 翻译层）。

    只认 NVIDIA GTX 16 / RTX 20-50；AMD 显卡不在支持列表里。
    """
    cpu = str(hw.get("cpu") or "")
    gpus = [str(g) for g in (hw.get("gpus") or [])]
    nvidia = [g for g in gpus if STELA_GPU_RE.search(g)]
    memory = float(hw.get("memory_gb") or 0)

    reasons: list[str] = []
    blockers: list[str] = []
    todos: list[str] = []

    if nvidia:
        reasons.append(f"检测到 Stela 支持的 NVIDIA 显卡：{', '.join(nvidia)}")
    else:
        blockers.append("没有 GTX 16 / RTX 20-50 系列显卡：Stela 的 Metal 驱动只覆盖这一档 NVIDIA")

    if memory >= STELA_MIN_MEMORY_GB:
        reasons.append(f"内存 {memory:.0f}GB，满足 ≥8GB 要求")
    else:
        blockers.append(f"内存 {memory:.0f}GB，低于 Stela 要求的 8GB")

    cpu_ok = True
    if AMD_CPU_RE.search(cpu):
        reasons.append("AMD x86-64 CPU（Bulldozer 及以后）在 Stela 的 CPU 支持范围内")
    elif cpu:
        reasons.append("Intel x86-64 CPU 在 Stela 的 CPU 支持范围内")

    # 这些是 Stela 当前版本的硬缺口，不是配置问题
    risks = [
        "Wi-Fi / 蓝牙 / 音频目前完全没有驱动（README 明写 None currently supported）",
        "性能损失大：arm64 指令要翻译成 x86-64 执行，日常使用明显偏慢",
        "项目仍在开发中，官方说明「可能仍然无法在受支持的硬件上启动」",
        "笔记本独显常走 Optimus / MUX，Stela 可能识别不到；台式机成功率更高",
    ]
    todos = [
        "从 https://github.com/tylertms/Stela/releases 下载 stela.exe",
        "准备 U 盘：在线安装 8GB，离线安装 32GB（会被清空）",
        "双击 stela.exe → 选 U 盘和安装器 → 从 U 盘启动（Secure Boot 必须关）",
        "起不来时用 stela.exe log --output log.txt 抓日志，提 Issue 用",
    ]

    return {
        "eligible": not blockers,
        "gpu": nvidia,
        "cpu_ok": cpu_ok,
        "reasons": reasons,
        "blockers": blockers,
        "risks": risks,
        "todos": todos,
        "link": "https://github.com/tylertms/Stela",
    }


def _apply_stela(rec: Recommendation, stela: dict, lead: str) -> Recommendation:
    rec.route = "stela"
    rec.verdict = "stela"
    rec.version = None
    rec.version_name = "macOS (arm64，由 Stela 翻译执行)"
    rec.board_id = None
    rec.smbios = "Stela 模拟 M2 Mac mini（不需要 SMBIOS）"
    rec.reasons = [lead] + stela["reasons"]
    rec.risks = stela["risks"]
    rec.todos = stela["todos"]
    rec.stela = stela
    return rec


def _wifi_advice(networks: list[str]) -> tuple[str | None, list[str], list[str]]:
    names = " | ".join(networks).lower()
    risks: list[str] = []
    todos: list[str] = []
    # 只对真正的无线网卡给建议，别把 Intel 有线网卡（I219 之类）当成 Wi-Fi
    if not any(k in names for k in ("wi-fi", "wifi", "wireless", "wlan", "802.11")):
        return None, risks, todos
    if "intel" in names:
        todos.append("Wi-Fi 用 itlwm + HeliPort；装完按说明书清除 Info.plist 里的明文密码")
        risks.append("Intel 网卡无 AWDL：隔空投送 / 接力 / 通用控制 / 随航 / 定位 全部不可用")
        return "itlwm", risks, todos
    if "broadcom" in names:
        todos.append("Broadcom 网卡通常原生可用，确认型号在支持列表内（如 BCM94360）")
        return "native", risks, todos
    if any(k in names for k in ("realtek", "qualcomm", "atheros", "mediatek")):
        risks.append("无线网卡不在 macOS 支持范围，需换卡或用 USB 无线网卡")
        todos.append("优先考虑更换为 BCM94360CS2 等免驱卡")
        return "none", risks, todos
    risks.append("未识别到无线网卡，安装阶段可能需要有线网络")
    return None, risks, todos


def _graphics_advice(gpus: list[str]) -> tuple[bool, list[str]]:
    text = " | ".join(gpus)
    notes: list[str] = []
    has_intel = "intel" in text.lower()
    has_amd = any(g.upper() in text.upper() for g in AMD_SUPPORTED)
    has_bad_nvidia = any(g in text.upper() for g in NVIDIA_UNSUPPORTED)
    if has_intel:
        notes.append("检测到 Intel 核显：走 iGPU 驱动（AAPL,ig-platform-id + device-id）")
        return True, notes
    if has_amd:
        notes.append("无核显但有受支持的 AMD 独显：可用，需注入对应 framebuffer")
        return True, []
    if has_bad_nvidia:
        notes.append("只有 NVIDIA 独显：macOS 12 起无驱动，不能作为图形输出")
        return False, notes
    notes.append("未找到可驱动的图形设备")
    return False, notes


def evaluate(hw: dict) -> Recommendation:
    raw_cpu = hw.get("cpu")
    if isinstance(raw_cpu, dict):
        cpu = str(raw_cpu.get("Processor Name") or raw_cpu.get("Model")
                  or raw_cpu.get("Name") or "")
    else:
        cpu = str(raw_cpu or "")
    gen = cpu_generation(cpu)
    gpus = [str(g) for g in (hw.get("gpus") or [])]
    networks = [str(n) for n in (hw.get("networks") or [])]
    stela = evaluate_stela(hw)

    rec = Recommendation(verdict="unsupported", version=None, version_name=None,
                         board_id=None, smbios=None, data=hw)
    rec.reasons.append(f"CPU：{cpu or '未识别'}（判定为 Intel 第 {gen} 代）" if gen > 0 else f"CPU：{cpu}")

    wifi_mode, wifi_risks, wifi_todos = _wifi_advice(networks)
    rec.wifi_mode = wifi_mode
    rec.risks.extend(wifi_risks)
    rec.todos.extend(wifi_todos)

    if gen == 0:
        rec.reasons.append("AMD 平台：OpenCore + Intel 核显这套方案不适用")
        if stela["eligible"]:
            return _apply_stela(rec, stela, "AMD 平台走不了常规 OpenCore 路线，但可以走 Stela")
        rec.reasons.extend(stela["blockers"])
        rec.verdict = "unsupported"
        return rec

    if gen < 0:
        rec.reasons.append("CPU 型号没有被识别，无法判定代次")
        rec.verdict = "unsupported"
        return rec

    if gen not in INTEL_TABLE:
        rec.reasons.append(f"检测到 {', '.join(gpus) or '未知显卡'}")
        lead = (f"第 {gen} 代（含 Core Ultra / Arrow Lake 等新平台）在 OpenCore 上没有可用核显驱动")
        if stela["eligible"]:
            return _apply_stela(rec, stela, lead + "，但可以用 Stela")
        rec.reasons.append(lead + "，开源社区也还没有成熟方案")
        rec.reasons.extend(stela["blockers"])
        rec.verdict = "unsupported"
        return rec

    gfx_ok, gfx_notes = _graphics_advice(gpus)
    rec.reasons.extend(gfx_notes)

    version, max_version, note = INTEL_TABLE[gen]
    rec.reasons.append(note)

    if version == "unsupported" or not gfx_ok:
        if stela["eligible"]:
            return _apply_stela(rec, stela, "核显不可驱动，改用 Stela（它只需要 NVIDIA 独显）")
        rec.verdict = "unsupported"
        if not gfx_ok:
            rec.reasons.append("图形不可驱动是硬门槛：装上也只是一块没有加速的屏幕")
        return rec

    rec.version = version
    rec.version_name = VERSION_NAME.get(version, version)
    rec.board_id = BOARD_ID.get(version)
    rec.smbios = SMBIOS_BY_GEN.get(gen)

    if version != max_version:
        rec.reasons.append(f"该代次原生最高可到 {VERSION_NAME.get(max_version, max_version)}，"
                           f"但推荐停在 {rec.version_name}：驱动最全、坑最少")

    rec.risks.append("EFI 放在 FAT32 分区上，任何拿到 U 盘的人都能读到其中的 Wi-Fi 明文密码")
    rec.risks.append("系统更新不要走 OTA：SSV 校验会失败")
    rec.todos.append("BIOS：UEFI 模式、关 Secure Boot、关 Fast Boot、DVMT ≥ 64MB")
    rec.todos.append("准备好 ≥8GB 的闲置 U 盘，制作过程会清空它")
    rec.todos.append("装完必须把 OpenCore 拷进硬盘 ESP，否则拔掉 U 盘就开不了机")

    rec.verdict = "supported" if version == "13" or gen >= 7 else "workable"
    return rec


def render(rec: Recommendation) -> str:
    icon = {"supported": "✅", "workable": "⚠️", "stela": "🧭", "unsupported": "❌"}[rec.verdict]
    title = {"supported": "可用", "workable": "勉强可用",
             "stela": "可走 Stela（实验性路线）", "unsupported": "不建议"}[rec.verdict]
    lines = [f"{icon} 结论：{title}"]

    if rec.route == "stela" and rec.stela:
        lines.append("   路线：Stela —— 把 arm64 macOS 翻译成 x86-64 执行")
        lines.append(f"   项目：{rec.stela['link']}")
        lines.append(f"   目标：{rec.version_name}")
        lines.append(f"   模拟机型：{rec.smbios}")
    elif rec.version:
        lines.append(f"   推荐系统：macOS {rec.version_name}（{rec.version}）")
        lines.append(f"   SMBIOS：{rec.smbios}    恢复镜像 board-id：{rec.board_id or '需手工核对'}")

    if rec.reasons:
        lines.append("   依据：")
        lines.extend(f"     · {r}" for r in rec.reasons)
    if rec.risks:
        lines.append("   风险 / 不可用功能：")
        lines.extend(f"     · {r}" for r in rec.risks)
    if rec.todos:
        lines.append("   下一步：")
        lines.extend(f"     · {t}" for t in rec.todos)
    return "\n".join(lines)
