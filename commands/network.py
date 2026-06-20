"""网络管理命令"""
import json
from core.mac_vendor import lookup_enhanced


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
        }
        result = dispatch.get(subcmd, self._help)()
        if subcmd == "leases" and self.output.format_type == "text":
            return self._render_leases_text(result["leases"])
        return self.output.dump(result)

    def _help(self):
        return {"error": "未知子命令，可用: interfaces / routes / dns / dhcp / leases / reload"}

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