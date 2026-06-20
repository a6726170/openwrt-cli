#!/usr/bin/env python3
"""
OpenWrt CLI — AI-Agent Ready 管理工具
支持网络、防火墙、QoS、监控、服务、用户、备份等操作
"""

import argparse
import json
import re
import sys
from pathlib import Path

from core.ssh_client import SSHClient, SSHConnectionError
from core.output import OutputFormatter
from core.config import ConfigManager

# 导入子命令模块
from commands.network import NetworkCommands
from commands.firewall import FirewallCommands
from commands.qos import QoSCommands
from commands.monitor import MonitorCommands
from commands.service import ServiceCommands
from commands.user import UserCommands
from commands.backup import BackupCommands
from commands.system import SystemCommands
from commands.doctor import DoctorCommand
from commands.interactive import run_interactive
from commands.config import run as run_config


def _normalize_format_argv(argv: list) -> tuple:
    """
    规范化命令行参数：将 -f json / --format json 移到最前面，
    解决 "openwrt network leases -f json" 这类写法的问题。
    
    返回: (processed_argv, format_value)  format_value 可能是 None
    """
    fmt = None
    new_argv = []
    skip_next = False
    
    for i, token in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        
        if token in ("-f", "--format"):
            if i + 1 < len(argv):
                fmt = argv[i + 1]
                skip_next = True
                continue
        elif token.startswith("-f=") or token.startswith("--format="):
            m = re.match(r"^--?f(?:ormat)?=(.+)$", token)
            if m:
                fmt = m.group(1)
                continue
        elif token.startswith("-") and not token.startswith("--"):
            # 短选项合并，如 -fjson
            m = re.match(r"^-f(.+)$", token)
            if m:
                fmt = m.group(1)
                continue
        
        new_argv.append(token)
    
    return (new_argv, fmt)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="openwrt-cli",
        description="OpenWrt CLI 管理工具 — AI-Agent Ready",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  openwrt-cli -H 192.168.1.1 -u root monitor system
  openwrt-cli -H 192.168.1.1 -u root network interfaces --format json
  openwrt-cli -H 192.168.1.1 -u root firewall rules list
  openwrt-cli -H 192.168.1.1 -u root qos status
  openwrt-cli -H 192.168.1.1 -u root service restart network
  openwrt-cli -H 192.168.1.1 -u root backup create --output /tmp/backup.tar.gz
"""
    )

    # 全局连接参数
    parser.add_argument("-H", "--host", help="OpenWrt 设备 IP 地址")
    parser.add_argument("-u", "--user", default="root", help="SSH 用户名 (默认: root)")
    parser.add_argument("-p", "--port", type=int, default=22, help="SSH 端口 (默认: 22)")
    parser.add_argument("-i", "--identity-file", help="SSH 私钥路径")
    parser.add_argument("--password", help="SSH 密码（不推荐，建议使用密钥）")

    # 配置管理
    parser.add_argument("--config", help="配置文件路径 (~/.openwrt-cli.yaml)")
    parser.add_argument("--save-config", action="store_true", help="保存连接参数到配置文件")
    parser.add_argument("--show-config", action="store_true", help="显示当前配置")

    # 输出格式
    # 注意：配合 _normalize_format_argv() 允许 -f json 出现在子命令之后
    parser.add_argument("-f", "--format", nargs="*", dest="format_arg",
                        default=None, metavar="FORMAT",
                        help="输出格式: text / json / compact (默认: text)")
    parser.add_argument("--pretty", action="store_true", default=True,
                        help="JSON 格式化输出 (默认: True)")

    parser.add_argument("-I", "--interactive", action="store_true",
                        help="交互式模式（引导操作）")

    # ========== 子命令 ==========
    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    # --- monitor ---
    monitor_parser = subparsers.add_parser("monitor", help="系统监控")
    monitor_sub = monitor_parser.add_subparsers(dest="monitor_cmd")

    m_system = monitor_sub.add_parser("system", help="系统概况")
    m_system.add_argument("--detail", action="store_true", help="详细信息")

    monitor_sub.add_parser("cpu", help="CPU 使用率")
    monitor_sub.add_parser("memory", help="内存使用")
    monitor_sub.add_parser("processes", help="进程列表")
    monitor_sub.add_parser("disk", help="磁盘使用")
    monitor_sub.add_parser("network-stats", help="网络流量统计")
    monitor_sub.add_parser("temperature", help="设备温度")
    monitor_sub.add_parser("uptime", help="运行时间")

    # --- network ---
    net_parser = subparsers.add_parser("network", help="网络管理")
    net_sub = net_parser.add_subparsers(dest="network_cmd")

    net_sub.add_parser("interfaces", help="列出所有网络接口")
    net_sub.add_parser("routes", help="路由表")
    net_sub.add_parser("dns", help="DNS 服务器")
    net_sub.add_parser("dhcp", help="DHCP 状态")
    net_sub.add_parser("leases", help="DHCP 租约")

    net_reload = net_sub.add_parser("reload", help="重载网络配置")
    net_reload.add_argument("interface", nargs="?", help="指定接口（留空重载全部）")

    # --- firewall ---
    fw_parser = subparsers.add_parser("firewall", help="防火墙管理")
    fw_sub = fw_parser.add_subparsers(dest="firewall_cmd")

    fw_sub.add_parser("rules", help="列出防火墙规则")
    fw_sub.add_parser("nat", help="NAT 规则")
    fw_sub.add_parser("zones", help="防火墙区域")
    fw_sub.add_parser("redirects", help="端口转发")
    fw_sub.add_parser("status", help="防火墙总体状态")

    # --- qos ---
    qos_parser = subparsers.add_parser("qos", help="流量 QoS")
    qos_sub = qos_parser.add_subparsers(dest="qos_cmd")

    qos_sub.add_parser("status", help="QoS 状态")
    qos_sub.add_parser("rules", help="QoS 规则列表")
    qos_sub.add_parser("classes", help="QoS 队列类别")
    qos_sub.add_parser("stats", help="QoS 统计")
    qos_sub.add_parser("interrupts", help="中断统计（网络卡负载）")

    # --- service ---
    svc_parser = subparsers.add_parser("service", help="服务管理")
    svc_sub = svc_parser.add_subparsers(dest="service_cmd")

    svc_list = svc_sub.add_parser("list", help="列出所有服务")
    svc_list.add_argument("--running", action="store_true", help="仅显示运行中")

    svc_status = svc_sub.add_parser("status", help="服务状态")
    svc_status.add_argument("name", help="服务名称")

    svc_sub.add_parser("start", help="启动服务").add_argument("name", help="服务名称")
    svc_sub.add_parser("stop", help="停止服务").add_argument("name", help="服务名称")
    svc_sub.add_parser("restart", help="重启服务").add_argument("name", help="服务名称")
    svc_sub.add_parser("reload", help="重载服务配置").add_argument("name", help="服务名称")

    # --- user ---
    user_parser = subparsers.add_parser("user", help="用户管理")
    user_sub = user_parser.add_subparsers(dest="user_cmd")

    user_sub.add_parser("list", help="列出所有用户")
    user_list = user_sub.add_parser("groups", help="列出用户组")
    user_list.add_argument("username", nargs="?", help="指定用户（留空显示全部）")

    user_add = user_sub.add_parser("add", help="添加用户")
    user_add.add_argument("username", help="用户名")
    user_add.add_argument("--password", help="密码")
    user_add.add_argument("--groups", help="附加组 (逗号分隔)")

    user_passwd = user_sub.add_parser("passwd", help="修改密码")
    user_passwd.add_argument("username", help="用户名")
    user_passwd.add_argument("--password", required=True, help="新密码")

    user_sub.add_parser("delete", help="删除用户").add_argument("username", help="用户名")

    # --- backup ---
    bk_parser = subparsers.add_parser("backup", help="配置备份")
    bk_sub = bk_parser.add_subparsers(dest="backup_cmd")

    bk_create = bk_sub.add_parser("create", help="创建备份")
    bk_create.add_argument("--output", "-o", default="/tmp/openwrt-backup.tar.gz",
                           help="备份文件路径")
    bk_create.add_argument("--exclude", action="append", help="排除目录")

    bk_restore = bk_sub.add_parser("restore", help="恢复备份")
    bk_restore.add_argument("backup_file", help="备份文件路径")
    bk_restore.add_argument("--confirm", action="store_true",
                            help="确认恢复（会重启网络）")

    bk_sub.add_parser("list", help="列出备份文件")

    # --- system ---
    sys_parser = subparsers.add_parser("system", help="系统信息")
    sys_sub = sys_parser.add_subparsers(dest="system_cmd")

    sys_sub.add_parser("info", help="系统信息")
    sys_reboot = sys_sub.add_parser("reboot", help="重启设备")
    sys_reboot.add_argument("--confirm", action="store_true", help="确认重启")
    sys_shutdown = sys_sub.add_parser("shutdown", help="关闭设备")
    sys_shutdown.add_argument("--confirm", action="store_true", help="确认关机")

    sys_board = sys_sub.add_parser("board", help="硬件/型号信息")

    sys_hostname = sys_sub.add_parser("hostname", help="查询/修改主机名")
    sys_hostname.add_argument("new_hostname", nargs="?", help="新主机名（省略则查询当前）")

    # --- config ---
    subparsers.add_parser("config", help="首次配置（设置路由器连接信息）")

    # --- doctor ---
    doctor_parser = subparsers.add_parser("doctor", help="路由器自检（诊断）")
    doctor_parser.add_argument("--quick", action="store_true",
                               help="快速检查（不包含详细检测）")
    doctor_parser.add_argument("--json", action="store_true",
                               help="输出 JSON 格式快速检查结果")

    # --- interactive / config ---
    interactive_parser = subparsers.add_parser(
        "interactive", aliases=["conf"],
        help="交互式配置（向导模式）"
    )
    interactive_parser.add_argument(
        "sub", nargs="?", choices=["user", "hostname", "wifi", "lan", "service"],
        help="直接进入指定配置项"
    )

    return parser


def main():
    # 预处理：提取 -f json 等格式参数（允许放在子命令之后）
    _argv, _fmt_override = _normalize_format_argv(sys.argv[1:])
    
    parser = build_parser()
    args = parser.parse_args(_argv)
    
    # 合并 -f 参数（处理 normalize 后仍通过 nargs='*' 传入的情况）
    _final_fmt = None
    if args.format_arg and len(args.format_arg) > 0:
        _final_fmt = args.format_arg[-1]  # 最后一个值
    if _fmt_override:
        _final_fmt = _fmt_override
    if _final_fmt:
        if _final_fmt not in ("text", "json", "compact"):
            print(f"错误: 无效的输出格式 '{_final_fmt}' (可用: text/json/compact)", file=sys.stderr)
            return 1
        args.format = _final_fmt
    else:
        args.format = "text"

    # 无参数时显示帮助
    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    # 显示配置
    if args.show_config:
        cfg = ConfigManager(args.config).load()
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        return 0

    # 需要命令
    if not args.command:
        parser.print_help()
        return 1

    # 加载配置
    config_mgr = ConfigManager(args.config)
    cfg = config_mgr.load()

    # 合并命令行参数到配置（命令行优先）
    if args.host:
        cfg["host"] = args.host
    if args.user:
        cfg["user"] = args.user
    if args.port:
        cfg["port"] = args.port
    if args.identity_file:
        cfg["identity_file"] = args.identity_file
    if args.password:
        cfg["password"] = args.password

    # 保存配置
    if args.save_config:
        if not args.host:
            print("错误: --save-config 需要 -h 参数", file=sys.stderr)
            return 1
        config_mgr.save(cfg)
        print(f"配置已保存到: {config_mgr.config_path}")
        return 0

    # 检查必要参数
    if not cfg.get("host"):
        print("错误: 未指定 -h 参数，也未找到配置文件", file=sys.stderr)
        return 1

    # 输出格式化器
    output = OutputFormatter(args.format, pretty=args.pretty)

    # 建立 SSH 连接
    try:
        ssh = SSHClient(
            host=cfg["host"],
            user=cfg.get("user", "root"),
            port=cfg.get("port", 22),
            password=cfg.get("password"),
            identity_file=cfg.get("identity_file"),
        )
    except SSHConnectionError as e:
        print(f"连接失败:\n  {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"连接失败: {e}", file=sys.stderr)
        return 1

    # 分发命令
    try:
        result = None

        if args.command == "monitor":
            cmd = MonitorCommands(ssh, output)
            result = cmd.run(args.monitor_cmd, args)

        elif args.command == "network":
            cmd = NetworkCommands(ssh, output)
            result = cmd.run(args.network_cmd, args)

        elif args.command == "firewall":
            cmd = FirewallCommands(ssh, output)
            result = cmd.run(args.firewall_cmd, args)

        elif args.command == "qos":
            cmd = QoSCommands(ssh, output)
            result = cmd.run(args.qos_cmd, args)

        elif args.command == "service":
            cmd = ServiceCommands(ssh, output)
            result = cmd.run(args.service_cmd, args)

        elif args.command == "user":
            cmd = UserCommands(ssh, output)
            result = cmd.run(args.user_cmd, args)

        elif args.command == "backup":
            cmd = BackupCommands(ssh, output)
            result = cmd.run(args.backup_cmd, args)

        elif args.command == "system":
            cmd = SystemCommands(ssh, output)
            result = cmd.run(args.system_cmd, args)

        elif args.command == "doctor":
            cmd = DoctorCommand(ssh)
            # doctor 命令总是输出文本，不受 -f 影响
            _save_fmt = args.format
            args.format = "text"
            result = cmd.run(args)
            print(result)
            return 0

        elif args.command in ("interactive", "conf") or args.interactive:
            # 交互式配置模式（需要先有 SSH 连接）
            if args.command in ("interactive", "conf"):
                target = getattr(args, "sub", None) or "config"
            else:
                target = "config"
            result = run_interactive(ssh, output, target)
            if isinstance(result, dict):
                output.out(result)
            return 0

        elif args.command == "config":
            # 首次配置引导（不需要 SSH 连接）
            run_config(args)
            return 0

        if result is not None:
            print(result)
            return 0
        return 0

    except Exception as e:
        print(f"执行出错: {e}", file=sys.stderr)
        return 1
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main())