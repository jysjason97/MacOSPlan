"""EFI 生成：驱动 OpCore-Simplify，并打上安装期必做的补丁。"""
from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from .util import TOOLS_DIR, download, log, require, run_ps

OPCORE_TAG = os.environ.get("MACPLAN_OPCORE_TAG", "2.1.2")
OPCORE_ZIP = f"https://github.com/lzhoang2801/OpCore-Simplify/archive/refs/tags/{OPCORE_TAG}.zip"

# 菜单应答规则：按提示词片段匹配，返回要输入的字符串
ANSWER_RULES: list[tuple[str, str]] = [
    ("select option", "1"),                 # 主菜单：Build OpenCore EFI
    ("hardware sniffer", "n"),
    ("path to", ""),                        # 交空回车，走默认/已有 Report.json
    ("macos version", "13"),
    ("wifi", "2"),                          # itlwm
    ("scan", "y"),
    ("kext", "y"),
    ("continue", "y"),
    ("confirm", "y"),
]

DRIVER = r'''
import sys, builtins
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

import utils.Utils as U

ANSWERS = __ANSWERS__
LOG = open(Path(TOOL_DIR) / "macplan_answers.log", "a", encoding="utf-8")
_state = {"last": ""}

def fake_request_input(*args, **kwargs):
    prompt = " ".join(str(a) for a in args) if args else str(kwargs.get("prompt", ""))
    print(prompt)
    answer = ""
    for key, value in ANSWERS:
        if key.lower() in prompt.lower():
            answer = value
            break
    LOG.write(f"{prompt!r} -> {answer!r}\n"); LOG.flush()
    return answer or ""

U.Utils.request_input = staticmethod(fake_request_input)

main_py = TOOL_DIR / "OpCore-Simplify.py"
code = main_py.read_text(encoding="utf-8")
exec(compile(code, str(main_py), "exec"), {"__name__": "__main__", "__file__": str(main_py)})
'''


def ensure_opcore() -> Path:
    zip_path = download(OPCORE_ZIP, TOOLS_DIR / f"OpCore-Simplify-{OPCORE_TAG}.zip")
    target = TOOLS_DIR / f"OpCore-Simplify-{OPCORE_TAG}"
    if target.exists() and (target / "OpCore-Simplify.py").exists():
        return target
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(TOOLS_DIR)
    # GitHub 压缩包会多一层目录
    for child in TOOLS_DIR.iterdir():
        if child.is_dir() and child.name.startswith(f"OpCore-Simplify-{OPCORE_TAG}"):
            if (child / "OpCore-Simplify.py").exists():
                return child
    if not (target / "OpCore-Simplify.py").exists():
        raise RuntimeError("OpCore-Simplify 解压后结构异常")
    return target


def build(report_json: Path, version: str, out_dir: Path) -> Path:
    """跑一次 EFI 生成，返回 Results/EFI 目录。"""
    tool = ensure_opcore()
    require(report_json.exists(), f"缺少硬件报告：{report_json}")
    driver = tool / "_macplan_driver.py"
    driver.write_text(DRIVER.replace("__ANSWERS__", repr(ANSWER_RULES)), encoding="utf-8")

    log("开始生成 EFI（OpCore-Simplify 自动应答，日志在 macplan_answers.log）…")
    proc = subprocess.run([sys.executable, str(driver)], cwd=str(tool),
                          capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        log(proc.stdout[-2000:], level="WARN")
        raise RuntimeError(
            "OpCore-Simplify 执行失败。常见原因：Report.json 路径没被识别、"
            "菜单项在新版本里改了名字。请看 tools/OpCore-Simplify-*/macplan_answers.log"
        )

    results = tool / "Results"
    efi = results / "EFI"
    require(efi.exists(), f"没有找到输出目录 {efi}")

    shutil.copytree(efi, out_dir, dirs_exist_ok=True)
    patch_config(out_dir / "OC" / "config.plist")
    return out_dir


def patch_config(config: Path) -> None:
    """安装期三个致命项 + 启动项注册，一次改完。"""
    require(config.exists(), f"缺少 {config}")
    backup = config.with_suffix(".plist.macplan.bak")
    if not backup.exists():
        shutil.copy2(config, backup)

    with open(config, "rb") as fh:
        data = plistlib.load(fh)

    misc = data.setdefault("Misc", {})
    security = misc.setdefault("Security", {})
    security["DmgLoading"] = "Any"          # Signed 校验不过 → 恢复项完全不显示
    security["SecureBootModel"] = "Disabled"
    security["ScanPolicy"] = 0              # 非 0 会把 U 盘上的安装项过滤掉

    boot = misc.setdefault("Boot", {})
    boot["LauncherOption"] = "Bootstrap"    # 让 OC 自己往 NVRAM 注册启动项
    boot["LauncherPath"] = "Default"
    boot["RequestBootVarRouting"] = True

    with open(config, "wb") as fh:
        plistlib.dump(data, fh)
    log("config.plist 已打补丁：DmgLoading=Any / SecureBootModel=Disabled / "
        "ScanPolicy=0 / LauncherOption=Bootstrap")


def check_structure(efi: Path) -> list[str]:
    """EFI 结构自检，返回问题列表。"""
    problems: list[str] = []
    oc = efi / "OC" / "OpenCore.efi"
    launcher = efi / "BOOT" / "BOOTx64.efi"
    if not oc.exists():
        problems.append("缺少 EFI/OC/OpenCore.efi")
    elif not 300_000 < oc.stat().st_size < 1_000_000:
        problems.append(f"OpenCore.efi 体积异常：{oc.stat().st_size} 字节")
    if not launcher.exists():
        problems.append("缺少 EFI/BOOT/BOOTx64.efi")
    elif launcher.stat().st_size > 500_000:
        problems.append("BOOTx64.efi 体积过大，疑似 Windows 的 bootmgfw 而非 OpenCore 启动器")
    return problems
