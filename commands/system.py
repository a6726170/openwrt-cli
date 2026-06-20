"""系统命令（信息/重启/关机）"""
import json


class SystemCommands:
    def __init__(self, ssh, output):
        self.ssh = ssh
        self.output = output

    def run(self, subcmd, args):
        dispatch = {
            "info":     self.info,
            "board":    self.board,
            "reboot":   self.reboot,
            "shutdown": self.shutdown,
            "hostname": self.hostname,
        }
        return self.output.dump(dispatch.get(subcmd, self._help)(args))

    def _help(self):
        return {"error": "未知子命令，可用: info / board / reboot / shutdown / hostname"}

    def info(self, args=None):
        raw = self.ssh.exec("ubus call system info 2>/dev/null")
        try:
            data = json.loads(raw)
        except Exception:
            data = {"raw": raw}

        hostname = self.ssh.exec("hostname").strip()
        uname = self.ssh.exec("uname -a").strip()
        return {"system_info": data, "hostname": hostname, "uname": uname}

    def board(self, args=None):
        raw = self.ssh.exec("ubus call system board 2>/dev/null")
        try:
            data = json.loads(raw)
        except Exception:
            data = {"raw": raw}
        return {"board": data}

    def reboot(self, args=None):
        confirm = getattr(args, 'confirm', False)
        if not confirm:
            return {
                "error": "reboot 需要 --confirm 参数",
                "warning": "此操作将重启设备！",
            }
        self.ssh.exec("reboot")
        return {"status": "ok", "action": "reboot", "message": "设备正在重启..."}

    def shutdown(self, args=None):
        confirm = getattr(args, 'confirm', False)
        if not confirm:
            return {
                "error": "shutdown 需要 --confirm 参数",
                "warning": "此操作将关闭设备！",
            }
        self.ssh.exec("poweroff")
        return {"status": "ok", "action": "shutdown", "message": "设备正在关机..."}

    def hostname(self, args=None):
        """查询或修改主机名"""
        new_hostname = getattr(args, 'new_hostname', None)
        current = self.ssh.exec("cat /proc/sys/kernel/hostname").strip()
        if not new_hostname:
            return {"hostname": current, "source": "实时查询"}
        self.ssh.exec(f"uci set system.@system[0].hostname='{new_hostname}'")
        self.ssh.exec("uci commit system")
        self.ssh.exec(f"hostname {new_hostname}")
        return {
            "status": "ok",
            "action": "hostname_set",
            "old_hostname": current,
            "new_hostname": new_hostname,
        }