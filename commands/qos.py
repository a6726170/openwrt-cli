"""QoS / 流量整形命令"""
import re


class QoSCommands:
    def __init__(self, ssh, output):
        self.ssh = ssh
        self.output = output

    def run(self, subcmd, args):
        dispatch = {
            "status":     self.status,
            "rules":      self.rules,
            "classes":    self.classes,
            "stats":      self.stats,
            "interrupts": self.interrupts,
        }
        return self.output.dump(dispatch.get(subcmd, self._help)())

    def _help(self):
        return {"error": "未知子命令，可用: status / rules / classes / stats / interrupts"}

    # ── QoS 状态 ──
    def status(self):
        # 检查 SQM（Smart Queue Management）是否启用
        sqm_status = self.ssh.exec("/etc/init.d/sqm status 2>/dev/null || echo 'sqm_not_found'")
        sqm_enabled = "active" in sqm_status.lower() or "running" in sqm_status.lower()
        # 检查 qos-gargoyle
        qos_status = self.ssh.exec("/etc/init.d/qos-gargoyle status 2>/dev/null || echo 'not_found'")

        # tc qdisc 概览
        tc_qdisc = self.ssh.exec("tc qdisc show 2>/dev/null")

        # 当前带宽（wan 接口）
        wan_dev = self.ssh.exec("uci get network.wan.device 2>/dev/null || uci get network.wan.ifname 2>/dev/null || echo 'br-lan'")
        speedtest = self.ssh.exec(f"cat /sys/class/net/{wan_dev}/speed 2>/dev/null || echo 'unknown'")

        return {
            "sqm": {
                "enabled": sqm_enabled,
                "status_output": sqm_status.strip(),
            },
            "qos_gargoyle": qos_status.strip(),
            "tc_qdisc": tc_qdisc.strip(),
            "wan_device": wan_dev.strip(),
            "wan_speed": speedtest.strip(),
        }

    # ── QoS 规则 ──
    def rules(self):
        # 尝试读取 SQM 配置
        sqm_conf = self.ssh.exec("uci show sqm 2>/dev/null | grep -E 'sqm\\.\\w+\\.enabled'")
        # 尝试读取 qos-gargoyle 配置
        qos_conf = self.ssh.exec("uci show qos-gargoyle 2>/dev/null | head -40")
        return {
            "sqm_config": sqm_conf,
            "qos_config": qos_conf,
        }

    # ── 队列类别 ──
    def classes(self):
        raw = self.ssh.exec("tc class show 2>/dev/null")
        return {"classes": raw.strip()}

    # ── 流量统计 ──
    def stats(self):
        raw = self.ssh.exec("tc -s qdisc show 2>/dev/null")
        return {"qdisc_stats": raw.strip()}

    # ── 中断统计（网络卡负载） ──
    def interrupts(self):
        # 显示网络相关中断统计
        net_irqs = self.ssh.exec(
            "cat /proc/interrupts 2>/dev/null | grep -E 'eth|wan|lan|ath|wlan|无线' || "
            "cat /proc/interrupts 2>/dev/null | head -40"
        )
        return {"interrupts": net_irqs}