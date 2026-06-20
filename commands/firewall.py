"""防火墙管理命令"""
import json


class FirewallCommands:
    def __init__(self, ssh, output):
        self.ssh = ssh
        self.output = output

    def run(self, subcmd, args):
        dispatch = {
            "rules":     self.rules,
            "nat":       self.nat,
            "zones":     self.zones,
            "redirects": self.redirects,
            "status":    self.status,
        }
        return self.output.dump(dispatch.get(subcmd, self._help)())

    def _help(self):
        return {"error": "未知子命令，可用: rules / nat / zones / redirects / status"}

    # ── 防火墙规则 ──
    def rules(self):
        raw = self.ssh.exec("iptables -L -n -v --line-numbers 2>/dev/null")
        return {"raw": raw, "description": "iptables filter表规则（包含INPUT/FORWARD/OUTPUT链）"}

    def nat(self):
        raw = self.ssh.exec("iptables -t nat -L -n -v --line-numbers 2>/dev/null")
        return {"raw": raw, "description": "iptables nat表规则（包含PREROUTING/POSTROUTING/OUTPUT链）"}

    def zones(self):
        raw = self.ssh.exec("uci show firewall 2>/dev/null | grep -E '=zone'")
        # 解析 zone 配置
        zones = []
        for line in raw.strip().splitlines():
            parts = line.split("=", 1)
            if len(parts) == 2:
                zones.append({"config_key": parts[0], "type": parts[1]})
        return {"zones": zones, "raw_uci": raw}

    def redirects(self):
        raw = self.ssh.exec("uci show firewall 2>/dev/null | grep -E '=redirect'")
        return {"redirects": raw, "description": "端口转发规则"}

    def status(self):
        # 综合状态
        chains = self.ssh.exec(
            "for chain in INPUT OUTPUT FORWARD; do echo \"=== $chain ===\"; "
            "iptables -L $chain -n --line-numbers 2>/dev/null; done"
        )
        forward = self.ssh.exec("cat /proc/sys/net/ipv4/ip_forward 2>/dev/null")
        return {
            "ip_forward": forward.strip(),
            "chains": chains,
        }