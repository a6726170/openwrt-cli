"""用户管理命令"""


class UserCommands:
    def __init__(self, ssh, output):
        self.ssh = ssh
        self.output = output

    def run(self, subcmd, args):
        dispatch = {
            "list":    self.list,
            "groups":  self.groups,
            "add":     self.add,
            "passwd":  self.passwd,
            "delete":  self.delete,
        }
        return self.output.dump(dispatch.get(subcmd, self._help)())

    def _help(self):
        return {"error": "未知子命令，可用: list / groups / add / passwd / delete"}

    def list(self):
        raw = self.ssh.exec("cat /etc/passwd")
        users = []
        for line in raw.strip().splitlines():
            parts = line.split(":")
            if len(parts) >= 7:
                users.append({
                    "username": parts[0],
                    "password": parts[1],
                    "uid":      parts[2],
                    "gid":      parts[3],
                    "gecos":    parts[4],
                    "home":     parts[5],
                    "shell":    parts[6],
                })
        return {"users": users}

    def groups(self, username=None):
        if username:
            raw = self.ssh.exec(f"groups {username} 2>/dev/null || cat /etc/group | grep {username}")
        else:
            raw = self.ssh.exec("cat /etc/group")
        return {"raw": raw}

    def add(self, username, password=None, groups=None):
        if not password:
            return {"error": "add 需要 --password 参数"}
        # 创建用户
        cmd = f"mkdir -p /home/{username} && useradd -m -s /bin/ash -G "
        cmd += groups.replace(",", ",") if groups else ""
        cmd += f" {username}"
        self.ssh.exec(cmd, check=False)
        # 设置密码
        out = self.ssh.exec(f'echo "{username}:{password}" | chpasswd -c SHA512 2>&1')
        return {
            "username": username,
            "groups": groups or "",
            "output": out.strip() or "用户创建成功",
        }

    def passwd(self, username, password):
        out = self.ssh.exec(f'echo "{username}:{password}" | chpasswd -c SHA512 2>&1')
        return {
            "username": username,
            "output": out.strip() or "密码修改成功",
        }

    def delete(self, username):
        out = self.ssh.exec(f"userdel {username} 2>&1 && rm -rf /home/{username}")
        return {
            "username": username,
            "output": out.strip() or "用户已删除",
        }