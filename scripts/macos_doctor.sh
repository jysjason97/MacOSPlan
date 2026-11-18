#!/usr/bin/env bash
# MacPlan 装后体检 · 在 macOS 上运行：bash scripts/macos_doctor.sh
# 判据都写在注释里，别凭感觉判断「设备在 = 功能正常」。

set -u
PASS=0; WARN=0

ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; PASS=$((PASS+1)); }
bad()  { printf "  \033[33m!\033[0m %s\n" "$1"; WARN=$((WARN+1)); }
info() { printf "  · %s\n" "$1"; }
title(){ printf "\n\033[36m== %s ==\033[0m\n" "$1"; }

title "1. 系统"
sw_vers
info "内核参数：$(sysctl -n kern.osversion 2>/dev/null || echo unknown)"

title "2. 硬盘 ESP 里的 OpenCore（拔掉 U 盘能不能开机，只看这一项）"
sudo diskutil mount disk0s1 >/dev/null 2>&1 || true
OC="/Volumes/EFI/EFI/OC/OpenCore.efi"
if [ -f "$OC" ]; then
  SIZE=$(stat -f%z "$OC")
  if [ "$SIZE" -gt 300000 ] && [ "$SIZE" -lt 1000000 ]; then
    ok "EFI/OC/OpenCore.efi 存在（${SIZE} 字节）"
  else
    bad "OpenCore.efi 体积异常：${SIZE} 字节"
  fi
else
  bad "硬盘 ESP 里没有 EFI/OC/OpenCore.efi —— 现在开机靠的是 U 盘，拔了就不进系统"
fi

BOOT="/Volumes/EFI/EFI/BOOT/BOOTx64.efi"
if [ -f "$BOOT" ]; then
  B=$(stat -f%z "$BOOT")
  if [ "$B" -gt 500000 ]; then
    bad "BOOTx64.efi 是 ${B} 字节，像是 Windows 的 bootmgfw，不是 OpenCore 启动器"
  else
    ok "EFI/BOOT/BOOTx64.efi 正常（${B} 字节）"
  fi
else
  bad "缺少 EFI/BOOT/BOOTx64.efi"
fi

title "3. config.plist 关键项"
CFG="/Volumes/EFI/EFI/OC/config.plist"
if [ -f "$CFG" ]; then
  check_key() {
    local key="$1" want="$2" got
    got=$(plutil -extract "$key" raw "$CFG" 2>/dev/null)
    if [ -z "$got" ]; then bad "$key 读不到"; return; fi
    if [ "$got" = "$want" ]; then ok "$key = $got"; else bad "$key = $got（建议 $want）"; fi
  }
  check_key "Misc.Boot.LauncherOption" "Bootstrap"
  check_key "Misc.Security.DmgLoading" "Any"
  check_key "Misc.Security.SecureBootModel" "Disabled"
  check_key "Misc.Security.ScanPolicy" "0"
else
  bad "找不到 config.plist（ESP 没挂上？）"
fi

title "4. 第三方 kext 是否真的加载"
# config 里启用、kmutil 里看不到 = 加载失败，这是最常见的误判
LOADED=$(kmutil showloaded 2>/dev/null | grep -vic "com.apple")
if [ "$LOADED" -gt 0 ]; then ok "已加载第三方 kext：${LOADED} 条"; else bad "一条第三方 kext 都没加载"; fi
for K in Lilu VirtualSMC WhateverGreen AppleALC; do
  if kmutil showloaded 2>/dev/null | grep -qi "$K"; then ok "$K 已加载"; else bad "$K 未加载"; fi
done
if kmutil showloaded 2>/dev/null | grep -qi "VoodooSMBus"; then
  bad "VoodooSMBus 在加载，检查是否与 VoodooInput 类名冲突（看 kernel 日志 OSMetaClass is a duplicate）"
fi

title "5. 声卡 layout（有设备 ≠ 有声音，必须实际放首歌）"
LAYOUT=$(ioreg -r -n HDEF -l 2>/dev/null | grep -oE '"layout-id"=<[0-9a-f]+>' | head -1)
if [ -n "$LAYOUT" ]; then
  info "$LAYOUT（十进制换算后核对 AppleALC 列表；HP Pavilion ALC295 是 24，华硕 UX430UA 是 14）"
else
  bad "HDEF 里读不到 layout-id"
fi

title "6. USB 端口映射"
PORTS=$(ioreg -r -c AppleUSBXHCIPort -l 2>/dev/null | grep -c '"port"')
CONN=$(ioreg -r -c AppleUSBXHCIPort -l 2>/dev/null | grep -c '"UsbConnector"')
info "端口 ${PORTS} 个，带 UsbConnector 属性的 ${CONN} 个"
if [ "$PORTS" -gt 0 ] && [ "$CONN" -eq 0 ]; then
  bad "端口没有任何 UsbConnector 属性 —— UTBDefault 是空壳，蓝牙/摄像头睡眠唤醒会不稳"
else
  ok "端口映射看起来有内容"
fi

title "7. 电源与睡眠"
pmset -g custom
SLEEP=$(pmset -g custom 2>/dev/null | awk '/ sleep /{print $2}' | head -1)
if [ "${SLEEP:-99}" -le 3 ]; then
  bad "sleep=${SLEEP} 分钟，过短会放大蓝牙唤醒 bug（建议 15）"
else
  ok "sleep=${SLEEP} 分钟"
fi
for K in womp powernap proximitywake; do
  V=$(pmset -g custom 2>/dev/null | awk -v k="$K" '$1==k{print $2}' | head -1)
  [ "${V:-0}" = "0" ] && ok "$K = 0" || bad "$K = ${V:-?}（笔记本建议 0）"
done

title "8. 时区（Intel 网卡方案没有定位，自动时区会落到美国）"
TZ_LINK=$(readlink /etc/localtime)
info "$TZ_LINK"
case "$TZ_LINK" in
  *Asia/Shanghai*) ok "时区正确" ;;
  *) bad "时区不是 Asia/Shanghai：sudo systemsetup -settimezone Asia/Shanghai" ;;
esac
AUTO=$(defaults read /Library/Preferences/com.apple.timezone.auto Active 2>/dev/null || echo 0)
[ "$AUTO" = "0" ] && ok "自动时区已关闭" || bad "自动时区还开着，会反复跳回美国时间"

title "9. 蓝牙 kext 顺序与注入器"
ORDER=$(kmutil showloaded 2>/dev/null | grep -iE "IntelBluetoothFirmware|IntelBTPatcher|BlueToolFixup" | awk '{print $NF}')
info "加载顺序：$(echo "$ORDER" | tr '\n' ' ')"
if kmutil showloaded 2>/dev/null | grep -qi "IntelBluetoothInjector"; then
  bad "IntelBluetoothInjector 还在（Monterey 之后必须移除，它是无代码 kext，kextstat 里看不到）"
else
  ok "没有 IntelBluetoothInjector 残留"
fi

title "10. 图形"
system_profiler SPDisplaysDataType 2>/dev/null | sed -n '1,12p'

title "结果"
echo "  通过 ${PASS} 项，需处理 ${WARN} 项"
[ "$WARN" -eq 0 ] && echo "  可以拔掉 U 盘，正常使用了。" || echo "  按上面标 ! 的项逐条处理，处理完再跑一次本脚本。"
