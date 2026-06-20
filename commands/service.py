"""服务管理命令"""
import json


class ServiceCommands:
    def __init__(self, ssh, output):
        self.ssh = ssh
        self.output = output

    def run(self, subcmd, args):
        dispatch = {
            "list":    self.list,
            "status":  self.status,
            "start":   self.start,
            "stop":    self.stop,
            "restart": self.restart,
            "reload":  self.reload,
        }
        return self.output.dump(dispatch.get(subcmd, self._help)())

    def _help(self):
        return {"error": "未知子命令，可用: list / status / start / stop / restart / reload"}

    def list(self, running_only=False):
        raw = self.ssh.exec("ls /etc/init.d/ 2>/dev/null")
        services = []
        for name in raw.strip().splitlines():
            name = name.strip()
            if not name:
                continue
            status_raw = self.ssh.exec(f"/etc/init.d/{name} running 2>/dev/null && echo 'running' || echo 'stopped'")
            is_running = "running" in status_raw
            if running_only and not is_running:
                continue
            services.append({"name": name, "running": is_running})
        return {"services": services}

    def status(self, name):
        raw = self.ssh.exec(f"/etc/init.d/{name} running 2>&1")
        is_running = "running" in raw.lower() or "active" in raw.lower()
        return {
            "service": name,
            "running": is_running,
            "raw_output": raw.strip(),
        }

    def start(self, name):
        out = self.ssh.exec(f"/etc/init.d/{name} start 2>&1")
        return {"service": name, "action": "start", "output": out.strip()}

    def stop(self, name):
        out = self.ssh.exec(f"/etc/init.d/{name} stop 2>&1")
        return {"service": name, "action": "stop", "output": out.strip()}

    def restart(self, name):
        out = self.ssh.exec(f"/etc/init.d/{name} restart 2>&1")
        return {"service": name, "action": "restart", "output": out.strip()}

    def reload(self, name):
        out = self.ssh.exec(f"/etc/init.d/{name} reload 2>&1")
        return {"service": name, "action": "reload", "output": out.strip()}