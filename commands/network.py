"""网络管理命令"""
import json
from core.mac_vendor import lookup_enhanced


def _fmt_bytes(num_bytes):
    """将字节数格式化为人类可读字符串"""
    if num_bytes < 0:
        return "—"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{abs(num_bytes):.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} PB"


def _rate_str(rx_bytes, tx_bytes, interval_sec):
    """计算并返回速率字符串"""
    def _rate(b):
        if interval_sec <= 0:
            return "—"
        r = b / interval_sec
        return _fmt_bytes(r) + "/s"
    return f"↓{_rate(rx_bytes)}  ↑{_rate(tx_bytes)}"


class NetworkCommands:
    def __init__(self, ssh, output):
        self.ssh = ssh
        self.output = output

    def run(self, subcmd, args):
        dispatch = {
            "interfaces": self.interfaces,
            "routes":     self.routes,
            "dns":        self.dns,
            "dhcp":       self.dhcp,
            "leases":     self.leases,
            "reload":     self.reload,
            "stats":      self.stats,
        }
        result = dispatch.get(subcmd, self._help)()
        if subcmd == "leases" and self.output.format_type == "text":
            return self._render_leases_text(result["leases"])
        if subcmd == "stats" and self.output.format_type == "text":
            return self._render_stats_text(result)
        return self.output.dump(result)

    def _help(self):
        return {"error": "未知子命令，可用: interfaces / routes / dns / dhcp / leases / stats / reload"}

    # ── 接口列表 ──
    def interfaces(self):
        raw = self.ssh.exec("ubus call network.interface dump")
        try:
            data = json.loads(raw)
        except Exception:
            return {"raw": raw}

        interfaces = []
        for iface in data.get("interface", []):
            name  = iface.get("interface", "")
            ipv4  = iface.get("ipv4-address", [])
            routes = iface.get("route", [])
            interfaces.append({
                "name":      name,
                "up":        iface.get("up", False),
                "device":    iface.get("device", ""),
                "proto":     iface.get("proto", ""),
                "l3_device": iface.get("l3_device", ""),
                "ipaddr":    ipv4[0]["address"] if ipv4 else "",
                "netmask":   str(ipv4[0]["mask"]) if ipv4 else "",
                "gateway":   routes[0].get("nexthop", "") if routes else "",
                "metric":    iface.get("metric", ""),
                "uptime":    iface.get("uptime", 0),
            })
        return {"interfaces": interfaces}

    # ── 路由表 ──
    def routes(self):
        raw = self.ssh.exec("ip route show")
        lines = []
        for line in raw.strip().splitlines():
            parts = line.split()
            if not parts:
                continue
            route = {"raw": line, "type": parts[0]}
            if parts[0] == "default":
                for i, p in enumerate(parts):
                    if p == "via" and i + 1 < len(parts):
                        route["via"] = parts[i + 1]
                    if p == "dev" and i + 1 < len(parts):
                        route["dev"] = parts[i + 1]
                    if p == "metric" and i + 1 < len(parts):
                        route["metric"] = parts[i + 1]
            else:
                route["network"] = parts[0]
                for i, p in enumerate(parts):
                    if p == "via" and i + 1 < len(parts):
                        route["via"] = parts[i + 1]
                    if p == "dev" and i + 1 < len(parts):
                        route["dev"] = parts[i + 1]
                    if p == "metric" and i + 1 < len(parts):
                        route["metric"] = parts[i + 1]
            lines.append(route)
        return {"routes": lines}

    # ── DNS ──
    def dns(self):
        resolv = self.ssh.exec(
            "cat /tmp/resolv.conf.d/resolv.conf.auto 2>/dev/null || "
            "cat /etc/resolv.conf 2>/dev/null"
        )
        servers = []
        for line in resolv.strip().splitlines():
            if line.startswith("nameserver"):
                servers.append(line.split()[1])
        return {"nameservers": servers}

    # ── DHCP 状态 ──
    def dhcp(self):
        raw = self.ssh.exec("uci show dhcp 2>/dev/null | grep -E '^dhcp\\.' | head -60")
        leases_raw = self.ssh.exec("cat /tmp/dhcp.leases 2>/dev/null")
        leases = []
        for line in leases_raw.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5:
                leases.append({
                    "timestamp": parts[0],
                    "mac":       parts[1],
                    "ip":        parts[2],
                    "hostname":  parts[3],
                    "client_id": parts[4] if len(parts) > 4 else "",
                })
        return {"uci_config": raw, "leases": leases}

    def _render_leases_text(self, leases):
        if not leases:
            return "暂无在线 DHCP 设备"
        headers = ["IP 地址", "MAC", "设备类型", "厂商", "主机名"]
        rows = []
        for le in leases:
            dev_type = le.get("device_type", "").replace("unknown", "??").replace("phone", "📱").replace("pc", "💻").replace("laptop", "💻").replace("camera", "📹").replace("router", "📡").replace("virtual", "🖥️").replace("cloud/hosted", "☁️")
            vendor = le.get("vendor") or "未知"
            hostname = le.get("hostname") or "—"
            rows.append([le["ip"], le["mac"], dev_type, vendor, hostname])
        return self.output.table(headers, rows)

    # ── DHCP 租约（含 MAC 厂商识别）─
    def leases(self):
        raw = self.ssh.exec("cat /tmp/dhcp.leases 2>/dev/null")
        leases = []
        for line in raw.strip().splitlines():
            parts = line.split()
            if len(parts) >= 4:
                mac = parts[1]
                mac_info = lookup_enhanced(mac)
                leases.append({
                    "ip":       parts[2],
                    "mac":      mac,
                    "hostname": parts[3] if parts[3] != "*" else "",
                    "expires":  parts[0],
                    "vendor":   mac_info["vendor"],
                    "device_type": mac_info["type"],
                })
        return {"leases": leases}

    # ── 重载网络 ──
    def reload(self, interface=None):
        if interface:
            out = self.ssh.exec(f"/etc/init.d/network reload {interface}")
        else:
            out = self.ssh.exec("/etc/init.d/network reload")
        return {"status": "ok", "output": out}

    # ══════════════════════════════════════════════
    #  流量统计（新增）
    # ══════════════════════════════════════════════

    def stats(self):
        """
        获取各网络接口的流量统计（累计字节数）。
        数据来源：/proc/net/dev（各接口的 rx/tx 字节/包统计）
        """
        raw = self.ssh.exec("cat /proc/net/dev")
        interfaces = []
        for line in raw.strip().splitlines():
            # 前两行是表头：Inter-|   Receive ...
            if line.strip().startswith("|") or ":" not in line:
                continue
            # 格式:   eth0:    rx_bytes ...
            parts = line.split(":")
            if len(parts) != 2:
                continue
            name = parts[0].strip()
            fields = parts[1].strip().split()
            if len(fields) < 10:
                continue
            try:
                rx_bytes = int(fields[0])
                rx_packets = int(fields[1])
                rx_errs = int(fields[2])
                rx_drop = int(fields[3])
                tx_bytes = int(fields[8])
                tx_packets = int(fields[9])
                tx_errs = int(fields[10])
                tx_drop = int(fields[11])
            except (ValueError, IndexError):
                continue

            interfaces.append({
                "name":       name,
                "rx_bytes":   rx_bytes,
                "tx_bytes":   tx_bytes,
                "rx_packets": rx_packets,
                "tx_packets": tx_packets,
                "rx_errors":  rx_errs,
                "tx_errors":  tx_errs,
                "rx_dropped": rx_drop,
                "tx_dropped": tx_drop,
            })

        # 同时获取 ubus 中的接口状态（含 uptime）
        ubus_raw = self.ssh.exec("ubus call network.interface dump")
        ubus_map = {}
        try:
            ubus_data = json.loads(ubus_raw)
            for iface in ubus_data.get("interface", []):
                ubus_map[iface.get("interface", "")] = iface
        except Exception:
            pass

        # 合并数据，标注已知接口
        known = {"wan", "lan", "loopback", "wan6"}
        enriched = []
        for iface in interfaces:
            name = iface["name"]
            ubus_info = ubus_map.get(name, {})
            enriched.append({
                "name":       name,
                "label":      name.upper() if name not in known else name.upper(),
                "up":         ubus_info.get("up", None),
                "rx_bytes":   iface["rx_bytes"],
                "tx_bytes":   iface["tx_bytes"],
                "rx_human":   _fmt_bytes(iface["rx_bytes"]),
                "tx_human":   _fmt_bytes(iface["tx_bytes"]),
                "rx_packets": iface["rx_packets"],
                "tx_packets": iface["tx_packets"],
                "rx_errors":  iface["rx_errors"],
                "tx_errors":  iface["tx_errors"],
                "rx_dropped": iface["rx_dropped"],
                "tx_dropped": iface["tx_dropped"],
                "rx_rate":    None,
                "tx_rate":    None,
            })
        return {"interfaces": enriched}

    def _render_stats_text(self, result):
        interfaces = result.get("interfaces", [])
        if not interfaces:
            return "未获取到接口流量数据"

        lines = []
        lines.append(f"{'接口':<8} {'状态':<5} {'收到':>12} {'发出':>12}  {'总流量':>12}")
        lines.append("─" * 58)

        for iface in interfaces:
            status = "🟢" if iface.get("up") else "🔴" if iface.get("up") is False else "⚪"
            rx = iface.get("rx_human", "—")
            tx = iface.get("tx_human", "—")
            total = _fmt_bytes(iface.get("rx_bytes", 0) + iface.get("tx_bytes", 0))
            label = iface.get("label", iface["name"].upper())
            lines.append(f"{label:<8} {status} {rx:>12} {tx:>12}  {total:>12}")

        lines.append("")
        lines.append("提示：流量为累计值（设备重启后清零）")
        lines.append("     查看实时速率请用: openwrt watch traffic")

        return "\n".join(lines)
