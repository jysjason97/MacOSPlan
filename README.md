# MacPlan · 黑苹果一键装机助手

> 把「这台电脑能不能装 macOS」这个问题，变成一个跑完就有答案、有启动盘、有说明书的工具。

MacPlan 是一个 Windows 端工具：**检测硬件 → 推荐 macOS 版本 → 生成 OpenCore EFI → 制作可启动 U 盘 → 装后体检**，全部按顺序串起来，并把你可能踩的坑提前拦掉。

它不是又一个 EFI 生成器 —— EFI 生成交给成熟的开源项目 [OpCore-Simplify](https://github.com/lzhoang2801/OpCore-Simplify)，MacPlan 负责的是**判定、编排、校验和兜底**，也就是真正让人翻车的那部分。

---

## 它解决什么问题

| 常见翻车点 | MacPlan 怎么处理 |
|---|---|
| 不知道自己的机器能不能装 | 扫描 CPU / 核显 / 网卡 / 声卡 / 触控板，给出「能/勉强/不能」和理由 |
| 选错系统版本 | 按 CPU 代次推荐到**原生支持的最后一代**，而不是「越新越好」 |
| 跑去用 OpenCore-Legacy-Patcher | 明确区分：**OCLP 只给真 Mac 用，PC 走 OpCore-Simplify** |
| U 盘做完，OpenCore 菜单里没有安装项 | 预先修好 `DmgLoading` / `ScanPolicy` / `SecureBootModel` 三个致命项 |
| 菜单项名字是乱码，认不出来 | 强制把 U 盘卷标改成 ASCII，避免 OpenCanopy 吞中文字形 |
| Wi-Fi 装完连不上，或者密码明文躺在 EFI 里 | 安装期用 itlwm 预置，装完提醒切 HeliPort 并把明文清掉 |
| 装完拔了 U 盘开不了机 | 校验硬盘 ESP 里到底有没有 `EFI/OC/OpenCore.efi`，而不是看 `nvram` |
| 装完没声音 / 触控板不动 | 装后体检脚本逐项给判据，避免「设备在、功能死」的误判 |

---

## 工作流

```mermaid
flowchart TD
    A[启动 MacPlan] --> B[硬件扫描]
    B --> B1{Hardware-Sniffer}
    B1 -->|拿不到 Report.json| B2[WMI 兜底采集]
    B1 --> B3[Report.json + ACPI 表]
    B --> C[可行性判定与版本推荐]
    C -->|无可用核显/无解硬件| X[明确劝退 + 原因]
    C --> D[生成 OpenCore EFI]
    D --> D1[OpCore-Simplify 自动应答]
    D1 --> D2[补丁: DmgLoading/ScanPolicy/SecureBootModel]
    D --> E[下载 macOS 恢复镜像]
    E --> E1[macrecovery + 对应 board-id]
    D --> F[采集 Wi-Fi 凭据]
    F --> F1[可选: 注入 itlwm, 仅本地]
    E --> G[制作启动 U 盘]
    D --> G
    F1 --> G
    G --> G1[≥8GB · 可移动 · 非系统盘]
    G1 --> G2[写 EFI + 镜像 + 说明书]
    G2 --> H[SHA256 全量校验]
    H --> H1{通过?}
    H1 -->|否| G2
    H1 -->|是| I[输出装机说明书]
    I --> J[装完运行 macos_doctor.sh 体检]
```

---

## 快速开始

### 1. 直接用（打包好的 exe）

到 [Releases](../../releases) 下载 `MacPlan.exe`，双击运行，按提示走六步。

### 2. 从源码跑

```powershell
git clone https://github.com/jysjason97/MacOSPlan.git
cd MacOSPlan
python -m macplan            # 交互式向导
```

要求：Windows 10/11、Python 3.9+、能访问 GitHub 与 Apple 的下载服务器。

### 3. 分步执行（适合排障）

```powershell
python -m macplan scan                    # 只做硬件扫描，产出 Report.json
python -m macplan recommend               # 只做版本推荐
python -m macplan efi --report SysReport\Report.json --version 13
python -m macplan usb --drive D: --efi Results\EFI --recovery macrecovery\com.apple.recovery.boot
python -m macplan verify --drive D:
```

---

## 六步向导会问你什么

1. **准备一个不用的 U 盘**：≥ 8 GB，内容会被清空。工具会先验证它是不是可移动盘、是不是系统盘
2. **这台机器最终要连的 Wi-Fi**：SSID + 密码（可选，只写进本机 EFI，不上传任何服务器）
3. **是否单系统**：单系统会抹掉整块硬盘，工具会要求你二次确认并提醒备份
4. 扫描 → 推荐 → 生成 EFI → 制作 U 盘 → 校验，全程有日志

> ⚠️ **Wi-Fi 密码会被写进 `itlwm.kext/Contents/Info.plist`，而 EFI 在 FAT32 上是明文可读的。**
> MacPlan 会在说明书里明确写出这一点，并给出「装完切 HeliPort 后立即清除明文」的步骤。如果你不接受，可以在向导里选择「跳过 Wi-Fi 预置」。

---

## 两个必须说清楚的边界

**① OpCore-Legacy-Patcher 不能用在 PC 上。**
OCLP 是给**真 Mac**（2007 年起的旧机器）打补丁跑新系统的，它依赖苹果固件和原厂硬件。普通 PC 走的是 OpenCore + OpCore-Simplify 这条线，两者不是替代关系。

**② 不是所有机器都能装。**
没有可驱动的核显、也没有受支持的 AMD 独显的机器，macOS 装上也只是「能开机但没图形加速」，没有实用价值。MacPlan 遇到这种情况会直接给出劝退结论和硬件依据，而不是让你白折腾一天。

---

## 装完之后

仓库里带了一个 macOS 侧的体检脚本：

```bash
bash scripts/macos_doctor.sh
```

它逐项检查这次最容易漏的东西：硬盘 ESP 里有没有真正的 OpenCore、`LauncherOption` 是否 Bootstrap、`layout-id` 对不对、USB 端口映射有没有生效、蓝牙 kext 顺序、`pmset` 睡眠参数、时区是否被自动设成美国时间。

判据都写在脚本注释里，避免出现「设备节点在、功能其实死了」的误判（比如触控板看 `IOHIDDevice` 子节点永远是 0）。

---

## 文档

- [全流程踩坑清单](docs/踩坑清单.md) —— 从可行性判定到装后调优，按阶段整理
- [AI 诊断提示词](docs/AI诊断提示词.md) —— 配合 DeepSeek / 任意 LLM 做排障的现成提示词
- [使用手册](docs/使用手册.md) —— 向导每一步在干什么、失败怎么回退
- [架构与原理](docs/架构与原理.md) —— 为什么这么设计

---

## 许可与免责

代码 MIT。**macOS 的软件许可只允许安装在苹果硬件上**，本项目仅作个人研究与技术学习用途，使用者自行承担全部风险：包括但不限于数据丢失、硬件损坏、保修失效、系统不稳定。

`docs/踩坑清单.md` 里的硬件结论来自一次真实装机（HP Pavilion 14-ce0xxx），换机器请重新扫描，不要照抄。
