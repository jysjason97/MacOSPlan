"""生成 README 用的安装流程图（GIF）。

产物：docs/assets/install-flow.gif
用法：python scripts/make_install_gif.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 960, 540
S = 2  # 2 倍渲染后缩小，边缘更干净

BG = "#F6F8FA"
INK = "#111827"
MUTED = "#6B7280"
TEAL = "#0D9488"
TEAL_DK = "#115E59"
MINT = "#CCFBF1"
AMBER = "#F59E0B"
WHITE = "#FFFFFF"
LINE = "#E5E7EB"
PANEL = "#0F172A"
PANEL_2 = "#1E293B"

FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size * S, index=0)


class Pen:
    def __init__(self, img: Image.Image):
        self.img = img
        self.d = ImageDraw.Draw(img)

    def rrect(self, box, r=0, fill=None, outline=None, width=1):
        self.d.rounded_rectangle([v * S for v in box], radius=r * S,
                                 fill=fill, outline=outline, width=width * S)

    def rect(self, box, fill=None, outline=None, width=1):
        self.d.rectangle([v * S for v in box], fill=fill, outline=outline, width=width * S)

    def line(self, xy, fill=INK, width=1):
        self.d.line([v * S for v in xy], fill=fill, width=width * S)

    def poly(self, points, fill=None, outline=None, width=1):
        self.d.polygon([(x * S, y * S) for x, y in points], fill=fill,
                       outline=outline, width=width * S)

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.d.ellipse([v * S for v in box], fill=fill, outline=outline, width=width * S)

    def text(self, xy, s, size=16, bold=False, fill=INK, anchor="mm"):
        self.d.text((xy[0] * S, xy[1] * S), s, font=font(size, bold),
                    fill=fill, anchor=anchor)


def base(step: int | None, total: int = 8) -> Image.Image:
    img = Image.new("RGB", (W * S, H * S), BG)
    p = Pen(img)
    # 顶部品牌
    p.ellipse((36, 26, 56, 46), fill=TEAL)
    p.text((66, 36), "MacPlan", 18, True, INK, anchor="lm")
    if step:
        p.text((W - 40, 36), f"第 {step} / {total} 步", 15, False, MUTED, anchor="rm")
    # 底部进度点
    if step:
        cx0, gap = W / 2 - (total - 1) * 11, 22
        for i in range(total):
            x = cx0 + i * gap
            color = TEAL if i < step else "#D1D5DB"
            r = 5 if i < step else 4
            p.ellipse((x - r, 505 - r, x + r, 505 + r), fill=color)
    return img


def caption(p: Pen, main: str, sub: str = "") -> None:
    p.text((W / 2, 428), main, 25, True, INK)
    if sub:
        p.text((W / 2, 462), sub, 15, False, MUTED)


# ------------------------------------------------------------------ 场景

def scene_title() -> Image.Image:
    img = Image.new("RGB", (W * S, H * S), BG)
    p = Pen(img)
    p.ellipse((W / 2 - 26, 96, W / 2 + 26, 148), fill=TEAL)
    p.text((W / 2, 122), "8", 30, True, WHITE)
    p.text((W / 2, 196), "从 Windows 到 macOS", 46, True, INK)
    p.text((W / 2, 250), "一个闲置 U 盘，八步，跟着做就行", 18, False, MUTED)
    p.rrect((W / 2 - 96, 288, W / 2 + 96, 326), 19, MINT)
    p.text((W / 2, 307), "MacPlan · 黑苹果一键装机助手", 14, True, TEAL_DK)
    p.text((W / 2, 402), "开始前只需准备：一台 Windows 电脑 + 一个 ≥8GB 的闲置 U 盘", 16, False, MUTED)
    return img


def scene_scan() -> Image.Image:
    img = base(1)
    p = Pen(img)
    # 笔记本
    p.rrect((260, 96, 700, 356), 12, WHITE, LINE, 1)
    p.rect((276, 110, 684, 340), fill=PANEL)
    # 屏内扫描线
    for i, y in enumerate(range(132, 330, 26)):
        w = 300 - (i % 3) * 40
        p.rrect((300, y, 300 + w, y + 10), 5, "#1E293B" if i % 2 else "#134E4A")
    p.rrect((300, 236, 452, 246), 5, TEAL)
    p.text((318, 241), "UHD 620", 11, False, MINT, anchor="lm")
    # 底边
    p.poly([(238, 356), (722, 356), (742, 378), (218, 378)], fill="#E5E7EB")
    p.rrect((456, 360, 504, 366), 3, "#CBD5E1")
    caption(p, "① 运行 MacPlan，自动扫描硬件", "CPU 代次 / 核显 / 无线网卡 / 声卡 / 硬盘 —— 不用自己查型号")
    return img


def scene_pick() -> Image.Image:
    img = base(2)
    p = Pen(img)
    p.rrect((232, 108, 728, 350), 14, WHITE, LINE, 1)
    p.text((268, 146), "推荐系统", 14, False, MUTED, anchor="lm")
    p.text((268, 182), "macOS Ventura 13", 34, True, INK, anchor="lm")
    p.line((268, 212, 692, 212), fill=LINE)
    for i, s in enumerate(["SMBIOS  MacBookPro15,2",
                           "board-id  Mac-4B682C642B45593E",
                           "理由  Kaby Lake-R 的原生上限"]):
        p.text((268, 240 + i * 30), s, 14, False, MUTED, anchor="lm")
    p.ellipse((656, 268, 700, 312), fill=MINT)
    p.text((678, 290), "✓", 22, True, TEAL)
    caption(p, "② 选「原生支持」的版本，不追新", "越新的系统需要越多补丁，越容易睡不醒、没声音、更新失败")
    return img


def scene_usb(progress: float) -> Image.Image:
    img = base(3)
    p = Pen(img)
    # U 盘
    p.rrect((392, 178, 560, 288), 16, TEAL)
    p.rrect((560, 210, 616, 256), 6, "#CBD5E1")
    p.rrect((600, 218, 616, 248), 4, "#94A3B8")
    p.text((476, 226), "32G", 22, True, WHITE)
    p.text((476, 258), "MACBOOT", 11, False, MINT)
    # 箭头
    p.line((300, 232, 372, 232), fill=TEAL, width=2)
    p.poly([(372, 224), (392, 232), (372, 240)], fill=TEAL)
    p.text((268, 232), "EFI", 15, True, TEAL_DK, anchor="rm")
    # 进度条
    p.rrect((300, 356, 660, 376), 10, LINE)
    if progress > 0:
        p.rrect((300, 356, 300 + 360 * progress, 376), 10, TEAL)
    p.text((680, 366), f"{int(progress * 100)}%", 15, True, TEAL_DK, anchor="lm")
    caption(p, "③ 写入启动盘（≥8GB，内容会被清空）", "EFI + 恢复镜像 + 说明书，写完自动做 SHA256 全量校验")
    return img


def scene_bios() -> Image.Image:
    img = base(4)
    p = Pen(img)
    p.rrect((222, 96, 738, 356), 12, PANEL)
    p.text((252, 124), "BIOS Setup  ·  Security", 14, True, "#94A3B8", anchor="lm")
    p.line((252, 142, 708, 142), fill="#334155")
    rows = [("Boot Mode", "UEFI", True),
            ("Secure Boot", "Disabled", True),
            ("Fast Boot", "Disabled", True),
            ("VT-x", "Enabled", True)]
    for i, (k, v, on) in enumerate(rows):
        y = 176 + i * 42
        p.text((252, y), k, 15, False, "#E2E8F0", anchor="lm")
        p.rrect((566, y - 14, 700, y + 14), 14, "#134E4A" if on else "#334155")
        p.text((633, y), v, 12, True, MINT if on else "#94A3B8")
        p.ellipse((686, y - 6, 698, y + 6), fill=TEAL if on else "#475569")
    caption(p, "④ 进 BIOS：UEFI、关 Secure Boot、关 Fast Boot", "HP 开机按 F10；别的品牌查对应键（F2 / Del / Esc）")
    return img


def scene_menu() -> Image.Image:
    img = base(5)
    p = Pen(img)
    p.rect((0, 72, W, 396), fill=PANEL)
    p.text((60, 100), "OpenCore Boot Menu", 13, False, "#94A3B8", anchor="lm")
    p.text((W - 60, 100), "按 空格 显示隐藏项", 12, False, AMBER, anchor="rm")

    items = [("⊞", "Windows", False), ("⚙", "macOS Base System (dmg)", True), ("↺", "Reset NVRAM", False)]
    for i, (icon, name, hi) in enumerate(items):
        y = 146 + i * 74
        if hi:
            p.rrect((150, y - 26, 810, y + 26), 10, "#134E4A", TEAL, 2)
            p.rrect((170, y - 16, 202, y + 16), 6, AMBER)
            p.text((186, y), icon, 14, True, WHITE)
            p.text((220, y), name, 17, True, MINT, anchor="lm")
            p.text((790, y), "← 选它", 13, True, AMBER, anchor="rm")
        else:
            p.rrect((150, y - 26, 810, y + 26), 10, PANEL_2)
            p.text((186, y), icon, 14, False, "#94A3B8")
            p.text((220, y), name, 16, False, "#CBD5E1", anchor="lm")

    caption(p, "⑤ 开机 F9 → 选 U 盘 → 按空格 → 选 macOS", "名字可能是 ___U___(dmg)：中文卷标在 OpenCanopy 里没有字形")
    return img


def scene_erase() -> Image.Image:
    img = base(6)
    p = Pen(img)
    p.rrect((208, 96, 752, 356), 12, WHITE, LINE, 1)
    p.rrect((208, 96, 752, 132), 12, "#F1F5F9")
    p.text((228, 114), "磁盘工具", 14, True, INK, anchor="lm")
    p.ellipse((716, 104, 742, 124), fill="#EF4444")
    # 左侧磁盘列表
    p.text((230, 154), "内部", 12, False, MUTED, anchor="lm")
    for i, (nm, sel) in enumerate([("APPLE SSD AP0256M", True), ("disk0s1  EFI", False)]):
        y = 176 + i * 34
        p.rrect((228, y - 12, 470, y + 12), 6, MINT if sel else "#F8FAFC")
        p.text((240, y), nm, 12, sel, TEAL_DK if sel else MUTED, anchor="lm")
    # 右侧操作
    p.text((500, 176), "名称  Macintosh HD", 13, False, INK, anchor="lm")
    p.text((500, 208), "格式  APFS", 13, True, TEAL_DK, anchor="lm")
    p.text((500, 240), "方案  GUID 分区图", 13, True, TEAL_DK, anchor="lm")
    p.text((500, 272), "⚠ 整块硬盘都会被清空", 12, False, "#B45309", anchor="lm")
    p.rrect((636, 306, 726, 334), 8, AMBER)
    p.text((681, 320), "抹掉", 14, True, WHITE)
    caption(p, "⑥ 磁盘工具：整块硬盘抹成 APFS / GUID", "别只抹分区；抹完关掉磁盘工具，回到「重新安装 macOS」")
    return img


def scene_install(progress: float) -> Image.Image:
    img = base(7)
    p = Pen(img)
    p.rrect((222, 110, 738, 340), 14, PANEL)
    p.text((W / 2, 168), "macOS 安装程序", 18, True, "#E2E8F0")
    p.rrect((300, 216, 660, 238), 11, "#1E293B")
    p.rrect((300, 216, 300 + 360 * progress, 238), 11, TEAL)
    p.text((W / 2, 270), f"正在安装… 约 {int(progress * 100)}%", 13, False, "#94A3B8")
    p.text((W / 2, 300), "剩余时间：看进度条就行，别拔 U 盘", 12, False, "#64748B")
    caption(p, "⑦ 安装中，中途会重启 2~3 次", "每次重启都从 OpenCore 菜单选同一个安装项，U 盘保持插着")
    return img


def scene_done() -> Image.Image:
    img = base(8)
    p = Pen(img)
    # 桌面渐变
    top, bottom = (14, 116, 144), (204, 251, 241)
    for y in range(72, 396):
        t = (y - 72) / 324
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        p.line((0, y, W, y), fill=color, width=1)
    p.rect((0, 72, W, 96), fill=(255, 255, 255, 255))
    p.text((20, 84), "", 10)
    # 菜单栏元素
    p.ellipse((18, 80, 26, 88), fill=INK)
    for i, x in enumerate([720, 752, 784, 816, 848]):
        p.rrect((x, 82, x + 18, 86), 2, "#94A3B8")
    # Dock
    p.rrect((330, 356, 630, 388), 14, WHITE)
    for i in range(5):
        x = 348 + i * 52
        p.rrect((x, 364, x + 30, 380), 6, [TEAL, AMBER, "#3B82F6", "#10B981", "#8B5CF6"][i])
    # 成功徽章
    p.ellipse((W / 2 - 34, 176, W / 2 + 34, 244), fill=MINT)
    p.text((W / 2, 210), "✓", 34, True, TEAL)
    p.text((W / 2, 132), "装好了", 30, True, WHITE)
    caption(p, "⑧ 把 EFI 拷进硬盘，拔掉 U 盘也能开机", "这一步不做，等于每次开机都得插着 U 盘")
    return img


def scene_outro() -> Image.Image:
    img = Image.new("RGB", (W * S, H * S), BG)
    p = Pen(img)
    p.text((W / 2, 150), "接下来会遇到的问题，都在文档里", 26, True, INK)
    p.rrect((180, 196, 780, 262), 12, WHITE, LINE, 1)
    p.text((210, 229), "docs/小白安装指南.md", 16, True, TEAL_DK, anchor="lm")
    p.text((750, 229), "逐步图文", 13, False, MUTED, anchor="rm")
    p.rrect((180, 280, 780, 346), 12, WHITE, LINE, 1)
    p.text((210, 313), "docs/装机陪跑提示词.md", 16, True, TEAL_DK, anchor="lm")
    p.text((750, 313), "丢给 AI，让它陪你装", 13, False, MUTED, anchor="rm")
    p.rrect((180, 364, 780, 430), 12, WHITE, LINE, 1)
    p.text((210, 397), "docs/踩坑清单.md", 16, True, TEAL_DK, anchor="lm")
    p.text((750, 397), "出事时查这里", 13, False, MUTED, anchor="rm")
    return img


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "docs" / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)

    frames: list[Image.Image] = []
    durations: list[int] = []

    def add(img: Image.Image, ms: int) -> None:
        frames.append(img.resize((W, H), Image.LANCZOS))
        durations.append(ms)

    add(scene_title(), 1600)
    add(scene_scan(), 1700)
    add(scene_pick(), 1700)
    add(scene_usb(0.0), 900)
    add(scene_usb(0.45), 600)
    add(scene_usb(1.0), 1300)
    add(scene_bios(), 1800)
    add(scene_menu(), 2000)
    add(scene_erase(), 1800)
    add(scene_install(0.2), 900)
    add(scene_install(0.75), 1100)
    add(scene_done(), 2000)
    add(scene_outro(), 2200)

    gif_path = out_dir / "install-flow.gif"
    frames[0].save(gif_path, save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=True, disposal=2)

    # 联系表，方便人工检查
    cols, rows = 3, 5
    thumb_w, thumb_h = 320, 180
    sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), "white")
    for i, f in enumerate(frames):
        sheet.paste(f.resize((thumb_w, thumb_h), Image.LANCZOS),
                    ((i % cols) * thumb_w, (i // cols) * thumb_h))
    sheet.save(out_dir / "_contact-sheet.png")
    print(f"gif: {gif_path} ({gif_path.stat().st_size / 1024:.0f} KB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
