"""备份与恢复命令"""
import hashlib
import datetime


class BackupCommands:
    def __init__(self, ssh, output):
        self.ssh = ssh
        self.output = output

    def run(self, subcmd, args):
        dispatch = {
            "create":  self.create,
            "restore": self.restore,
            "list":    self.list,
        }
        return self.output.dump(dispatch.get(subcmd, self._help)())

    def _help(self):
        return {"error": "未知子命令，可用: create / restore / list"}

    def create(self, output="/tmp/openwrt-backup.tar.gz", exclude=None):
        exclude = exclude or []
        exclude_args = " ".join(f"--exclude={e}" for e in exclude)

        # 备份配置
        cmd = (
            f"sysupgrade -b {output} 2>/dev/null || "
            f"tar -czf {output} {exclude_args} "
            f"/etc/config/ /etc/crontabs/ /etc/passwd /etc/group "
            f"/etc/shadow /etc/dropbear/ /etc/firewall.user "
            f"/etc/rc.local /etc/sysctl.conf /etc/hotplug.d/ "
            f"2>/dev/null"
        )
        out = self.ssh.exec(cmd, timeout=60)

        # 计算 SHA256
        sha256 = ""
        if self.ssh.file_exists(output):
            sha256 = self.ssh.exec(f"sha256sum {output}").strip().split()[0] if self.ssh.file_exists(output) else ""

        size = self.ssh.exec(f"ls -lh {output} 2>/dev/null").strip()

        return {
            "backup_file": output,
            "size": size,
            "sha256": sha256,
            "output": out.strip(),
        }

    def restore(self, backup_file, confirm=False):
        if not confirm:
            return {
                "error": "恢复需要 --confirm 参数",
                "warning": "此操作会重启网络服务，请谨慎！",
            }

        # 校验文件存在
        if not self.ssh.file_exists(backup_file):
            return {"error": f"文件不存在: {backup_file}"}

        # 执行恢复（sysupgrade）
        out = self.ssh.exec(f"sysupgrade -r {backup_file} 2>&1", timeout=60)
        return {
            "backup_file": backup_file,
            "output": out.strip(),
            "note": "恢复完成，设备可能已重启",
        }

    def list(self):
        raw = self.ssh.exec("find /tmp -name '*.tar.gz' -mtime -7 2>/dev/null | sort")
        files = []
        for path in raw.strip().splitlines():
            info = self.ssh.exec(f"ls -lh {path} 2>/dev/null").strip()
            files.append({"path": path, "info": info})
        return {"recent_backups": files}