"""写盘后的校验：文件树哈希、DMG 完整性、EFI 结构、卷状态。"""
from __future__ import annotations

from pathlib import Path

from .recovery import check_dmg
from .util import human_size, log, sha256_tree


def compare_tree(source: Path, dest: Path, *, ignore: set[str] | None = None) -> dict:
    src = sha256_tree(source)
    dst = sha256_tree(dest)
    missing = [k for k in src if k not in dst]
    mismatch = [k for k in src if k in dst and dst[k] != src[k]]
    return {
        "source_files": len(src),
        "dest_files": len(dst),
        "missing": missing,
        "mismatch": mismatch,
        "ok": not missing and not mismatch,
    }


def check_efi_boot_files(volume: Path) -> list[str]:
    problems: list[str] = []
    oc = volume / "EFI" / "OC" / "OpenCore.efi"
    launcher = volume / "EFI" / "BOOT" / "BOOTx64.efi"
    if not oc.exists():
        problems.append("EFI/OC/OpenCore.efi 缺失，插上盘不会出现 OpenCore 菜单")
    elif not 300_000 < oc.stat().st_size < 1_000_000:
        problems.append(f"OpenCore.efi 体积 {oc.stat().st_size} 字节，不像正常构建产物")
    if not launcher.exists():
        problems.append("EFI/BOOT/BOOTx64.efi 缺失，主板找不到引导文件")
    elif launcher.stat().st_size > 500_000:
        problems.append("BOOTx64.efi 过大（疑似 Windows bootmgfw），不是 OpenCore 启动器")
    return problems


def verify(volume: Path, efi_source: Path, recovery_source: Path) -> bool:
    ok = True
    log("① 校验 EFI 文件树…")
    efi_result = compare_tree(efi_source, volume / "EFI")
    log(f"   EFI：{efi_result['source_files']} 个文件，"
        f"缺失 {len(efi_result['missing'])}，不一致 {len(efi_result['mismatch'])}")
    if not efi_result["ok"]:
        ok = False
        for name in (efi_result["missing"] + efi_result["mismatch"])[:10]:
            log(f"   异常文件：{name}", level="WARN")

    log("② 校验恢复镜像…")
    dmg = volume / "com.apple.recovery.boot" / "BaseSystem.dmg"
    dmg_ok, detail = check_dmg(dmg)
    log(f"   BaseSystem.dmg：{detail}")
    ok = ok and dmg_ok

    log("③ 校验引导文件结构…")
    problems = check_efi_boot_files(volume)
    if problems:
        ok = False
        for p in problems:
            log(f"   {p}", level="WARN")
    else:
        log("   引导文件结构正常")

    log("④ 汇总…")
    total = sha256_tree(volume)
    log(f"   U 盘共 {len(total)} 个文件 / {human_size(sum((volume / p).stat().st_size for p in total))}")
    log("校验通过" if ok else "校验未通过，请重新写入", level="INFO" if ok else "ERROR")
    return ok
