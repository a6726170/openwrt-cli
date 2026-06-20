# -*- coding: utf-8 -*-
"""
路由器自检命令 (doctor)
一键检查：SSH / UCI / WiFi / DHCP / 防火墙 / 固件 / 内存 / ZeroTier
发现问题给出修复建议
"""

import socket
import time
import re
import json
from typing import Optional


class DoctorCommand:
    def __init__(self, ssh_client):
        self.ssh = ssh_client

    def run(self, args):
        """执行完整自检，支持 --quick（快速模式）和 --json（JSON输出）"""
        quick = getattr(args, "quick", False)
        json_out = getattr(args, "json", False)
        
        if json_out:
            result = self.quick_check()
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        output = []
        output.append("🔍 开始路由器体检...")
        output.append("=" * 50)
        
        all_passed = True
        
        if not self._check_ssh(output):
            all_passed = False
            output.append("=" * 50)
            output.append("❌ SSH 不可用，体检中止")
            return "\n".join(output)
        
        if not quick:
            self._check_firmware(output)
        
        self._check_load(output)
        self._check_memory(output)
        
        wifi_issues = self._check_wifi(output) if not quick else False
        if wifi_issues:
            all_passed = False
        
        self._check_dhcp(output)
        
        if not quick:
            self._check_firewall(output)
        
        self._check_zerotier(output)
        
        if not quick:
            self._check_wan(output)
            self._check_qos(output)
        
        output.append("=" * 50)
        if all_passed:
            output.append("✅ 体检完成：所有项目正常")
        else:
            output.append("⚠️  体检完成：发现问题，建议修复（见上文）")
        
        return "\n".join(output)

    def _exec(self, cmd: str) -> str:
        try:
            return self.ssh.exec(cmd)
        except Exception as e:
            return f"ERROR: {e}"

    def _check_ssh(self, output) -> bool:
        output.append("\n📡 [1/10] SSH 连接")
        try:
            result = self.ssh.exec("echo ok").strip()
            if result == "ok":
                ssh_proc = self.ssh.exec("ps | grep dropbear | grep -v grep | wc -l").strip()
                output.append(f"   ✅ SSH 正常 (dropbear进程: {ssh_proc})")
                return True
            else:
                output.append("   ❌ SSH 响应异常")
                return False
        except Exception as e:
            output.append(f"   ❌ SSH 连接失败: {e}")
            output.append("   💡 建议：检查密码、端口、SSH服务是否开启")
            return False

    def _check_firmware(self, output):
        output.append("\n🖥️  [2/10] 固件信息")
        try:
            ver = self._exec("cat /proc/version | head -1")
            model = self._exec("cat /tmp/sysinfo/model | head -1").strip()
            openwrt_ver = self._exec("cat /usr/lib/os-release | grep PRETTY").strip()
            kernel = ver.split(" ")[2] if ver else "unknown"
            output.append(f"   型号: {model}")
            output.append(f"   内核: {kernel}")
            if openwrt_ver:
                output.append(f"   系统: {openwrt_ver.split('=')[1].strip('\"')}")
            uptime_hours = float(self._exec("cat /proc/uptime").split()[0]) / 3600
            if uptime_hours > 720:
                output.append(f"   ⚠️  运行时间 {uptime_hours:.0f} 小时，建议定期重启")
        except Exception as e:
            output.append(f"   ❌ 无法获取固件信息: {e}")

    def _check_load(self, output):
        output.append("\n📊 [3/10] 系统负载")
        try:
            load = self._exec("cat /proc/loadavg").strip().split()
            cpu_count = self._exec("cat /proc/cpuinfo | grep processor | wc -l").strip()
            load_1 = float(load[0])
            load_5 = float(load[1])
            cores = int(cpu_count) if cpu_count.isdigit() else 2
            
            output.append(f"   CPU 核心数: {cores}")
            output.append(f"   1分钟负载: {load_1} (理想 < {cores})")
            output.append(f"   5分钟负载: {load_5}")
            
            if load_1 > cores * 2:
                output.append("   🔴 负载过高！CPU 可能过载")
            elif load_1 > cores:
                output.append("   🟡 负载偏高，有进程排队")
            else:
                output.append("   ✅ 负载正常")
            
            for temp_path in ["/sys/class/thermal/thermal_zone0/temp"]:
                temp_out = self._exec(f"cat {temp_path} 2>/dev/null")
                if temp_out and temp_out.strip().isdigit():
                    temp_c = int(temp_out.strip()) / 1000
                    output.append(f"   🌡️  CPU温度: {temp_c:.1f}°C")
                    if temp_c > 80:
                        output.append("   🔴 温度过高！注意散热")
                    break
        except Exception as e:
            output.append(f"   ❌ 无法获取负载信息: {e}")

    def _check_memory(self, output):
        output.append("\n💾 [4/10] 内存状态")
        try:
            meminfo = self._exec("cat /proc/meminfo")
            total_kb = int(re.search(r"MemTotal:\s+(\d+)", meminfo).group(1))
            avail_kb = int(re.search(r"MemAvailable:\s+(\d+)", meminfo).group(1))
            total_mb = total_kb / 1024
            avail_mb = avail_kb / 1024
            used_pct = (1 - avail_kb / total_kb) * 100
            
            output.append(f"   总内存: {total_mb:.0f} MB")
            output.append(f"   可用内存: {avail_mb:.0f} MB")
            output.append(f"   已用: {used_pct:.1f}%")
            
            if used_pct > 90:
                output.append("   🔴 内存严重不足！可能导致卡顿/重启")
                output.append("   💡 建议：检查是否有内存泄漏进程，重启路由器")
            elif used_pct > 75:
                output.append("   🟡 内存使用偏高")
            else:
                output.append("   ✅ 内存充足")
        except Exception as e:
            output.append(f"   ❌ 无法获取内存信息: {e}")

    def _check_wifi(self, output) -> bool:
        issues = []
        output.append("\n📶 [5/10] WiFi 状态")
        try:
            wifi_list = self._exec("ubus call network.wireless status 2>/dev/null")
            hostapd_count = self._ssh_count_process("hostapd")
            wpa_count = self._ssh_count_process("wpa_supplicant")
            
            output.append(f"   hostapd 进程: {hostapd_count}")
            output.append(f"   wpa_supplicant 进程: {wpa_count}")
            
            if wifi_list and "ap" in wifi_list.lower():
                output.append("   ✅ WiFi 接口已启用")
                ssid_out = self._exec("uci get wireless.@wifi-iface[0].ssid 2>/dev/null")
                if ssid_out.strip():
                    output.append(f"   SSID: {ssid_out.strip()}")
            else:
                issues.append("WiFi 未启用")
                output.append("   ⚠️  未检测到活跃的 WiFi 接口")
            
            if hostapd_count == 0:
                issues.append("WiFi 服务未运行")
                output.append("   🔴 WiFi 服务未运行！检查 hostapd 配置")
            
            if not issues:
                output.append("   ✅ WiFi 正常")
                return False
            return True
        except Exception as e:
            output.append(f"   ⚠️  WiFi 检测失败: {e}")
            return True

    def _ssh_count_process(self, name: str) -> int:
        try:
            out = self.ssh.exec(f"ps | grep '{name}' | grep -v grep | wc -l").strip()
            return int(out) if out.isdigit() else 0
        except:
            return 0

    def _check_dhcp(self, output):
        output.append("\n🌐 [6/10] DHCP 服务")
        try:
            dnsmasq_count = self._ssh_count_process("dnsmasq")
            leases = self._exec("cat /tmp/dhcp.leases 2>/dev/null | wc -l").strip()
            active_leases = int(leases) if leases.isdigit() else 0
            
            output.append(f"   dnsmasq 进程: {dnsmasq_count}")
            output.append(f"   DHCP 在线设备: {active_leases} 台")
            
            if dnsmasq_count == 0:
                output.append("   🔴 DHCP 服务未运行！设备无法自动获取 IP")
                output.append("   💡 建议：/etc/init.d/dnsmasq start")
            elif active_leases == 0:
                output.append("   🟡 当前无设备通过 DHCP 获取 IP")
            else:
                output.append("   ✅ DHCP 正常")
        except Exception as e:
            output.append(f"   ❌ DHCP 检测失败: {e}")

    def _check_firewall(self, output):
        output.append("\n🔥 [7/10] 防火墙")
        try:
            output.append(f"   防火墙规则数: {self._exec('iptables -L | wc -l').strip()}")
            wan_ssh = self._exec("iptables -L INPUT -v -n 2>/dev/null | grep 'dpt:22' | head -1").strip()
            if wan_ssh:
                output.append("   ⚠️  SSH 端口(22)可能对 WAN 开放！建议限制 IP")
            else:
                output.append("   ✅ WAN 无法直接访问 SSH")
            nat_rules = self._exec("iptables -t nat -L | wc -l").strip()
            output.append(f"   NAT 规则数: {nat_rules}")
            output.append("   ✅ 防火墙运行正常")
        except Exception as e:
            output.append(f"   ❌ 防火墙检测失败: {e}")

    def _parse_zerotier_status(self, parts: list) -> tuple:
        KNOWN_STATUSES = {
            "OK", "REQUESTING_CONFIGURATION", "ACCESS_DENIED",
            "NOT_FOUND", "PORT_ERROR", "CLIENT_TOO_OLD", "BANNED",
            "NORMAL", "MY", "HELD", "BACKUP"
        }
        status_idx = None
        for i in range(len(parts) - 1, -1, -1):
            if parts[i].upper() in KNOWN_STATUSES:
                status_idx = i
                break
        if status_idx is None or status_idx + 1 >= len(parts):
            return parts[0] if parts else "?", "?", "?", "?"
        
        net_id = parts[0]
        port_idx = None
        for i in range(1, status_idx):
            if not re.match(r"^[0-9a-fA-F:]+$", parts[i]):
                port_idx = i
                break
        port = parts[port_idx] if port_idx else "?"
        status = parts[status_idx].upper()
        ip_cidr = parts[status_idx + 1] if status_idx + 1 < len(parts) else "?"
        return net_id, port, status, ip_cidr

    def _check_zerotier(self, output):
        output.append("\n🔗 [8/10] ZeroTier VPN")
        try:
            zt_count = self._ssh_count_process("zerotier-one")
            output.append(f"   zerotier-one 进程: {zt_count}")

            if zt_count > 0:
                zt_networks = self._exec(
                    "zerotier-cli listnetworks 2>/dev/null | tail -n +2"
                ).strip()
                if zt_networks:
                    for line in zt_networks.split("\n"):
                        parts = line.split()
                        if len(parts) >= 4:
                            net_id, port, status, ip_cidr = self._parse_zerotier_status(parts)
                            output.append(f"   网络 {net_id[:12]}... ({port}) 状态: {status}")
                            if ip_cidr != "?":
                                output.append(f"      IP: {ip_cidr}")
                            if status == "OK":
                                output.append("   ✅ ZeroTier 已连接")
                            elif status == "REQUESTING_CONFIGURATION":
                                output.append("   🟡 ZeroTier 正在获取配置...")
                            elif status == "ACCESS_DENIED":
                                output.append("   🔴 ZeroTier 被拒绝加入网络！")
                            else:
                                output.append(f"   🟡 ZeroTier 状态: {status}")
                else:
                    output.append("   🟡 ZeroTier 正在运行但未加入网络")
            else:
                output.append("   ℹ️  ZeroTier 未安装或未运行")
        except Exception as e:
            output.append(f"   ℹ️  ZeroTier 检测跳过: {e}")

    def _check_wan(self, output):
        """检查 WAN 口（通过 ubus 实时获取，UCI 不记录 DHCP 动态 IP）"""
        output.append("\n🌍 [9/10] WAN 口状态")
        try:
            wan_dev = self._exec("uci get network.wan.device 2>/dev/null").strip()
            wan_ip = ""
            wan_gw = ""
            
            # 方法1：通过 ubus + jsonfilter 实时获取
            ubus_out = self._exec(
                "ubus call network.interface dump 2>/dev/null | "
                "jsonfilter -e '@.interface[@.interface=\"wan\"]' -a"
            ).strip()
            if ubus_out and ubus_out != "" and ubus_out != "null":
                try:
                    import json as _json
                    wan_list = _json.loads(ubus_out)
                    if isinstance(wan_list, list) and len(wan_list) > 0:
                        wan_data = wan_list[0]
                        addrs = wan_data.get("ipv4-address", [])
                        wan_ip = addrs[0]["address"] if addrs else ""
                        for r in wan_data.get("route", []):
                            if r.get("target") == "0.0.0.0":
                                wan_gw = r.get("nexthop", "")
                                break
                except Exception:
                    pass
            
            # 方法2：直接解析 ubus JSON
            if not wan_ip:
                ubus_raw = self._exec("ubus call network.interface dump 2>/dev/null").strip()
                if ubus_raw:
                    try:
                        import json as _json2
                        data = _json2.loads(ubus_raw)
                        for iface in data.get("interface", []):
                            if iface.get("interface") == "wan":
                                addrs = iface.get("ipv4-address", [])
                                wan_ip = addrs[0]["address"] if addrs else ""
                                for r in iface.get("route", []):
                                    if r.get("target") == "0.0.0.0":
                                        wan_gw = r.get("nexthop", "")
                                        break
                                break
                    except Exception:
                        pass
            
            # 方法3：ifconfig fallback
            if not wan_ip:
                wan_ip = self._exec(
                    "ifconfig wan 2>/dev/null | "
                    "awk '/inet /{print }' | tr -d 'addr:'"
                ).strip()
            
            output.append(f"   WAN IP: {wan_ip or '未获取'}")
            output.append(f"   WAN 网关: {wan_gw or '未获取'}")
            output.append(f"   WAN 设备: {wan_dev or '未获取'}")
            
            if wan_gw:
                ping_out = self._exec(
                    f"ping -c 2 -W 2 {wan_gw} 2>/dev/null | grep -E 'received|packets'"
                ).strip()
                if "0% packet loss" in ping_out or "2 received" in ping_out or "1 received" in ping_out:
                    output.append("   ✅ WAN 上行正常")
                elif ping_out:
                    output.append("   🟡 WAN 上行有丢包")
            
            mtu = self._exec("cat /sys/class/net/br-lan/mtu 2>/dev/null").strip()
            if mtu:
                output.append(f"   LAN MTU: {mtu}")
        except Exception as e:
            output.append(f"   ❌ WAN 检测失败: {e}")

    def _check_qos(self, output):
        output.append("\n🚀 [10/10] 流量控制 (QoS)")
        try:
            sqm_status = self._exec("/etc/init.d/sqm status 2>/dev/null | head -1").strip()
            qos_enabled = "active" in sqm_status.lower() if sqm_status else False
            
            if qos_enabled:
                output.append("   ✅ SQM QoS 已启用")
            else:
                tc_out = self._exec("tc qdisc show 2>/dev/null | head -3").strip()
                if tc_out and "qdisc" in tc_out:
                    output.append("   🟡 检测到流量整形规则（可能由其他方式配置）")
                else:
                    output.append("   ℹ️  QoS 未启用（网络正常时可不开）")
        except Exception as e:
            output.append(f"   ℹ️  QoS 检测跳过: {e}")

    def quick_check(self) -> dict:
        checks = {}
        try:
            checks["ssh"] = self.ssh.exec("echo ok").strip() == "ok"
        except:
            checks["ssh"] = False
        
        if checks["ssh"]:
            try:
                load = self._exec("cat /proc/loadavg").strip().split()[0]
                checks["load_1min"] = float(load)
                
                meminfo = self._exec("cat /proc/meminfo")
                total = int(re.search(r"MemTotal:\s+(\d+)", meminfo).group(1))
                avail = int(re.search(r"MemAvailable:\s+(\d+)", meminfo).group(1))
                checks["memory_used_pct"] = round((1 - avail/total) * 100, 1)
                
                leases = self._exec("cat /tmp/dhcp.leases 2>/dev/null | wc -l").strip()
                checks["dhcp_leases"] = int(leases) if leases.isdigit() else 0
                
                checks["zerotier"] = self._ssh_count_process("zerotier-one") > 0
                checks["wifi"] = self._ssh_count_process("hostapd") > 0
                checks["dnsmasq"] = self._ssh_count_process("dnsmasq") > 0
                checks["uptime_hours"] = round(float(self._exec("cat /proc/uptime").split()[0]) / 3600, 1)
                
                # WAN IP（快速检查）
                import json as _json
                wan_ip = ""
                ubus_raw = self._exec("ubus call network.interface dump 2>/dev/null").strip()
                if ubus_raw:
                    try:
                        data = _json.loads(ubus_raw)
                        for iface in data.get("interface", []):
                            if iface.get("interface") == "wan":
                                addrs = iface.get("ipv4-address", [])
                                wan_ip = addrs[0]["address"] if addrs else ""
                                break
                    except Exception:
                        pass
                checks["wan_ip"] = wan_ip
            except:
                pass
        
        return checks