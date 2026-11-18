"""命令行入口：交互式向导 + 可分步执行的子命令。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import compat, efibuild, hardware, recovery, usbdrive, verify, wifi
from .util import APP_NAME, REPO_ROOT, log

SYSREPORT = REPO_ROOT / "SysReport"
DEFAULT_EFI_OUT = REPO_ROOT / "Results" / "EFI"
DEFAULT_RECOVERY = REPO_ROOT / "macrecovery"


def _ask(prompt: str, default: str = "") -> str:
    raw = input(f"{prompt}{f' [{default}]' if default else ''}：").strip()
    return raw or default


def _yes(prompt: str, default: bool = False) -> bool:
    raw = _ask(prompt + " (y/n)", "y" if default else "n").lower()
    return raw.startswith("y")


# ---------------------------------------------------------------- 子命令

def cmd_scan(args: argparse.Namespace) -> int:
    hw = hardware.collect(Path(args.out))
    print(json.dumps(hw, ensure_ascii=False, indent=2))
    return 0


def cmd_recommend(args: argparse.Namespace) -> int:
    cache = REPO_ROOT / ".cache" / "hardware.json"
    if cache.exists():
        hw = json.loads(cache.read_text(encoding="utf-8"))
    else:
        hw = hardware.collect(SYSREPORT)
    rec = compat.evaluate(hw)
    print(compat.render(rec))
    (REPO_ROOT / "recommendation.json").write_text(
        json.dumps(rec.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if rec.verdict != "unsupported" else 2


def cmd_efi(args: argparse.Namespace) -> int:
    rec = json.loads((REPO_ROOT / "recommendation.json").read_text(encoding="utf-8"))
    version = args.version or str(rec.get("version") or "13")
    report = Path(args.report or (SYSREPORT / "Report.json"))
    efi = efibuild.build(report, version, Path(args.out))
    problems = efibuild.check_structure(efi)
    if problems:
        for p in problems:
            log(p, level="ERROR")
        return 1
    log(f"EFI 就绪：{efi}")
    return 0


def cmd_usb(args: argparse.Namespace) -> int:
    disks = usbdrive.list_usb()
    if not disks:
        raise RuntimeError("没有检测到 USB 磁盘")
    if args.drive:
        match = [d for d in disks if args.drive[0].upper() in d.letters]
        if not match:
            raise RuntimeError("指定的盘符不在 USB 磁盘列表里")
        disk = match[0]
    else:
        disk = disks[0]
    volume = usbdrive.write_payload(disk, Path(args.efi), Path(args.recovery))
    return 0 if verify.verify(volume, Path(args.efi), Path(args.recovery)) else 1


def cmd_verify(args: argparse.Namespace) -> int:
    volume = Path(args.drive.rstrip("\\/") + ":\\")
    return 0 if verify.verify(volume, Path(args.efi), Path(args.recovery)) else 1


# ---------------------------------------------------------------- 向导

def wizard() -> int:
    print(f"\n{'=' * 58}\n{APP_NAME} · 黑苹果一键装机助手\n{'=' * 58}\n")
    print("六步：硬件扫描 → 版本推荐 → 生成 EFI → 下载镜像 → 制作 U 盘 → 校验\n")

    print("【第 1 步 / 共 6 步】准备 U 盘")
    print("需要一个 ≥8GB 的闲置 U 盘，它的内容会被清空。")
    disks = usbdrive.list_usb()
    if not disks:
        print("❌ 没有检测到 USB 设备，请插好 U 盘后重试")
        return 1
    for i, d in enumerate(disks, 1):
        print(f"  {i}. 磁盘{d.number} {d.name} {d.size_gb}GB "
              f"{'/'.join(d.letters) or '无盘符'} {d.fs}")
    choice = _ask("选择 U 盘编号", "1")
    disk = disks[int(choice) - 1]
    usbdrive.guard(disk)

    if disk.fs.upper() != "FAT32":
        print(f"⚠️ 当前是 {disk.fs}，需要先转成 FAT32")
        if _yes("现在格式化（会清空该盘）", default=False):
            label = _ask("卷标（ASCII，≤11 位，用于 OpenCore 菜单显示）", "MACBOOT")
            print("⚠️ 这是最后一次确认，输入大写的 YES 才会执行：")
            if _ask("确认") == "YES":
                usbdrive.format_fat32(disk, label, confirm="YES")
                disk = [d for d in usbdrive.list_usb() if d.number == disk.number][0]
            else:
                print("已取消，请手动格式化为 FAT32 后重试")
                return 1

    print("\n【第 2 步 / 共 6 步】Wi-Fi（可选）")
    print("预置 Wi-Fi 可以让恢复环境直接联网，不必插网线。")
    print("代价：密码会以明文写进 EFI，拿到 U 盘的人都能看到。")
    wifi_ok = _yes("现在读取本机保存的 Wi-Fi 并写入启动盘", default=True)
    profiles = wifi.collect() if wifi_ok else []
    if profiles:
        ssid = profiles[0]["ssid"]
        print(f"  读取到 {len(profiles)} 组，首选 SSID：{ssid}")
    else:
        print("  跳过 Wi-Fi 预置，安装阶段请准备网线")

    print("\n【第 3 步 / 共 6 步】硬件扫描")
    hw = hardware.collect(SYSREPORT)
    report = hw.get("report_json")
    print(f"  来源：{hw.get('source')}　CPU：{hw.get('cpu')}　内存：{hw.get('memory_gb')}GB")
    print(f"  显卡：{', '.join(hw.get('gpus') or [])}")
    print(f"  网卡：{', '.join(hw.get('networks') or [])}")

    print("\n【第 4 步 / 共 6 步】可行性判定与版本推荐")
    rec = compat.evaluate(hw)
    print(compat.render(rec))
    (REPO_ROOT / "recommendation.json").write_text(
        json.dumps(rec.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    if rec.verdict == "unsupported":
        print("\n❌ 这台机器不建议安装。上面的依据已经说明原因，继续只会浪费时间。")
        return 2
    if not _yes("按上面的结论继续", default=True):
        return 0

    print("\n【第 5 步 / 共 6 步】生成 EFI + 下载恢复镜像")
    if not report:
        print("❌ 缺少 Hardware-Sniffer 生成的 Report.json，OpCore-Simplify 无法工作")
        print("   请手动运行 tools 下的 Hardware-Sniffer，或改用官方 GUI 生成后放到 SysReport/")
        return 1
    efibuild.build(Path(str(report)), str(rec.version), DEFAULT_EFI_OUT)
    recovery_dir = recovery.download_recovery(str(rec.version), DEFAULT_RECOVERY)

    print("\n【第 6 步 / 共 6 步】写入 U 盘并校验")
    volume = usbdrive.write_payload(disk, DEFAULT_EFI_OUT, recovery_dir)

    itlwm = wifi.find_itlwm_info_plist(DEFAULT_EFI_OUT)
    if profiles and itlwm:
        wifi.patch_itlwm(itlwm, profiles)
        # 补丁会改变 Info.plist 的哈希，重新写一遍确保盘上是最终版本
        usbdrive.write_payload(disk, DEFAULT_EFI_OUT, recovery_dir)

    if not verify.verify(volume, DEFAULT_EFI_OUT, recovery_dir):
        print("\n⚠️ 校验没通过，U 盘不可信，请重新运行本工具")
        return 1

    print("\n" + "=" * 58)
    print("✅ 启动盘做好了")
    print(f"   盘符：{volume}　卷标：{disk.fs or 'FAT32'}")
    print("   下一步：重启 → 连按 F9 → 选 U 盘 EFI → 按空格展开隐藏项 → 选 macOS 项")
    print("   装完请运行 scripts/macos_doctor.sh 体检")
    print("=" * 58)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="macplan", description=APP_NAME)
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("scan", help="只做硬件扫描")
    s.add_argument("--out", default=str(SYSREPORT))
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("recommend", help="只做版本推荐")
    s.set_defaults(func=cmd_recommend)

    s = sub.add_parser("efi", help="生成 EFI")
    s.add_argument("--report", default=None)
    s.add_argument("--version", default=None)
    s.add_argument("--out", default=str(DEFAULT_EFI_OUT))
    s.set_defaults(func=cmd_efi)

    s = sub.add_parser("usb", help="写入 U 盘")
    s.add_argument("--drive", default=None)
    s.add_argument("--efi", default=str(DEFAULT_EFI_OUT))
    s.add_argument("--recovery", default=str(DEFAULT_RECOVERY / "com.apple.recovery.boot"))
    s.set_defaults(func=cmd_usb)

    s = sub.add_parser("verify", help="校验 U 盘")
    s.add_argument("--drive", required=True)
    s.add_argument("--efi", default=str(DEFAULT_EFI_OUT))
    s.add_argument("--recovery", default=str(DEFAULT_RECOVERY / "com.apple.recovery.boot"))
    s.set_defaults(func=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        return wizard()
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\n已中止")
        return 130
    except Exception as exc:  # noqa: BLE001
        log(str(exc), level="ERROR")
        return 1
