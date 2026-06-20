# -*- coding: utf-8 -*-
"""
SSH 客户端封装 - 支持更好的错误提示和诊断
"""
import paramiko
import socket
import sys
import os
import time
import re


class SSHConnectionError(Exception):
    """SSH 连接失败，带详细诊断信息"""
    pass


class SSHCommandError(Exception):
    """命令执行失败"""
    pass


def diagnose(host: str, port: int, timeout: int = 5) -> dict:
    """
    连接前的本地诊断，返回诊断结果
    """
    results = {
        "host": host,
        "port": port,
        "dns_ok": False,
        "ping_ok": False,
        "tcp_ok": False,
        "ping_ms": None,
        "suggestions": [],
    }
    
    # DNS 解析
    try:
        socket.gethostbyname(host)
        results["dns_ok"] = True
    except socket.gaierror:
        results["suggestions"].append(f"❌ 域名 '{host}' 无法解析，请检查 IP 地址是否正确")
        return results
    
    # Ping 检测
    try:
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        # Windows 不支持 ICMP，用 TCP 端口检测代替
        sock.close()
        # 尝试 TCP 连接到 SSH 端口
        s = socket.socket()
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        results["ping_ok"] = True
        results["ping_ms"] = round((time.time() - start) * 1000)
    except socket.timeout:
        results["suggestions"].append(f"❌ {host}:{port} 连接超时（{timeout}s），路由器可能离线或端口被阻")
        results["suggestions"].append("💡 检查：1) 路由器是否通电 2) 网线是否插好 3) 能否 ping 通")
    except socket.error as e:
        results["suggestions"].append(f"❌ {host}:{port} TCP 连接失败: {e}")
        results["suggestions"].append("💡 检查：路由器是否重启/防火墙阻断了 SSH")
    except Exception as e:
        results["suggestions"].append(f"⚠️  诊断异常: {e}")
    
    return results


class SSHClient:
    def __init__(self, host, user="root", port=22, password=None,
                 identity_file=None, timeout=10, verbose=False):
        self.host = host
        self.user = user
        self.port = port
        self.verbose = verbose
        self.client = None
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 诊断
        if verbose:
            diag = diagnose(host, port, timeout=3)
            if not diag["dns_ok"]:
                raise SSHConnectionError(f"域名解析失败: {host}")
            if not diag["ping_ok"]:
                print(f"⚠️  警告: {host}:{port} 不可达", file=sys.stderr)
                for s in diag["suggestions"]:
                    print(f"   {s}", file=sys.stderr)

        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": user,
            "timeout": timeout,
            "look_for_keys": True,
            "allow_agent": True,
        }
        if password:
            connect_kwargs["password"] = password
        if identity_file:
            identity_file = os.path.expanduser(identity_file)
            if os.path.exists(identity_file):
                connect_kwargs["key_filename"] = identity_file
            else:
                raise SSHConnectionError(f"密钥文件不存在: {identity_file}")

        try:
            self.client.connect(**connect_kwargs)
        except paramiko.AuthenticationException:
            raise SSHConnectionError(
                f"认证失败: 密码或密钥错误\n"
                f"  主机: {host}:{port}\n"
                f"  用户: {user}\n"
                f"💡 解决: openwrt config 或设置正确密码"
            )
        except socket.timeout:
            raise SSHConnectionError(
                f"连接超时 ({timeout}s): {host}:{port}\n"
                f"  原因: 路由器离线 / 防火墙阻断 / SSH 端口不是 {port}\n"
                f"💡 检查: 1) 路由器是否重启中\n"
                f"        2) 通过 Web 管理界面确认 SSH 端口\n"
                f"        3) 路由器 LAN IP 是否变化（查 DHCP 服务器）"
            )
        except paramiko.NoValidConnectionsError as e:
            raise SSHConnectionError(
                f"无法连接到 {host}:{port}\n"
                f"  错误: {e}\n"
                f"💡 检查: SSH 服务是否在 {port} 端口监听（Dropbear 默认 22）"
            )
        except socket.error as e:
            # 区分不同错误
            err_msg = str(e)
            if "Connection refused" in err_msg:
                raise SSHConnectionError(
                    f"连接被拒绝: {host}:{port}\n"
                    f"  原因: SSH 服务未监听该端口\n"
                    f"💡 解决: 1) 确认 OpenWrt SSH 端口（默认 22）\n"
                    f"        2) 检查 /etc/config/dropbear 配置\n"
                    f"        3) 尝试: openwrt config --set port=22"
                )
            elif "No route to host" in err_msg:
                raise SSHConnectionError(
                    f"无法路由到 {host}\n"
                    f"  原因: 主机不可达（网络不通）\n"
                    f"💡 检查: 1) 确认路由器 IP（可能变了）\n"
                    f"        2) 检查本机网络/DNS 设置\n"
                    f"        3) 查 DHCP 服务器leases确认当前 IP"
                )
            elif "Network is unreachable" in err_msg:
                raise SSHConnectionError(
                    f"网络不可达: 本机无默认路由或在同一网段\n"
                    f"💡 检查: 本机是否连接到同一路由器"
                )
            else:
                raise SSHConnectionError(
                    f"网络错误 ({host}:{port}): {e}\n"
                    f"💡 如路由器刚重启，请等待 1-2 分钟后再试"
                )
        except paramiko.SSHException as e:
            raise SSHConnectionError(
                f"SSH 协议错误: {e}\n"
                f"💡 可能是服务器SSH版本不兼容或连接数已满"
            )
        except Exception as e:
            raise SSHConnectionError(
                f"连接失败: {type(e).__name__}: {e}\n"
                f"  主机: {host}:{port}  用户: {user}"
            )

    def exec(self, cmd: str, timeout=30, check=False) -> str:
        """
        执行命令并返回输出
        :param cmd: 命令
        :param timeout: 超时秒数
        :param check: 是否检查返回码（非0则抛异常）
        """
        try:
            stdin, stdout, stderr = self.client.exec_command(cmd, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            stderr_text = stderr.read().decode("utf-8", errors="replace").strip()
            stdout_text = stdout.read().decode("utf-8", errors="replace").strip()

            if check and exit_code != 0:
                raise SSHCommandError(
                    f"命令执行失败 (exit {exit_code}): {cmd}\n{stderr_text}"
                )
            return stdout_text
        except socket.timeout:
            raise SSHCommandError(f"命令超时 ({timeout}s): {cmd}")
        except socket.error as e:
            raise SSHConnectionError(f"执行命令时连接断开: {e}")
        except Exception as e:
            if "not connected" in str(e).lower():
                raise SSHConnectionError("SSH 连接已断开")
            raise

    def exec_json(self, cmd: str, timeout=30):
        """执行命令并尝试解析为 JSON"""
        import json
        output = self.exec(cmd, timeout=timeout)
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            raise ValueError(f"命令输出不是有效 JSON:\n{output[:500]}")

    def exec_sudo(self, cmd: str, timeout=30) -> str:
        """使用 sudo 执行命令（适用于非 root 用户场景）"""
        sudo_cmd = f"sudo {cmd}"
        return self.exec(sudo_cmd, timeout=timeout)

    def file_exists(self, path: str) -> bool:
        """检查文件是否存在"""
        result = self.exec(f'test -e "{path}" && echo "1" || echo "0"')
        return result.strip() == "1"

    def read_file(self, path: str) -> str:
        """读取远程文件内容"""
        return self.exec(f"cat {path}", timeout=10)

    def write_file(self, path: str, content: str) -> str:
        """写入远程文件"""
        # 用 sftp 更安全，但这里用 heredoc 简单实现
        safe_content = content.replace("'", "'\"'\"'")
        return self.exec(f"cat > {path} << 'EOF'\n{content}\nEOF")

    def close(self):
        if self.client:
            self.client.close()
            self.client = None
