"""openwrt-cli config — 交互式配置路由器连接"""
import os
import sys
import platform
import questionary


def run(args=None):
    """引导用户完成首次配置，保存到 ~/.openwrt-cli.yaml"""
    from core.config import ConfigManager

    cfg = ConfigManager().load()
    system = platform.system()

    print("")
    print("╔══════════════════════════════════════╗")
    print("║   openwrt-cli  路由连接配置向导       ║")
    print("╚══════════════════════════════════════╝")
    print("")

    # ── 路由器 IP ──────────────────────────────────────
    default_ip = cfg.get("host") or "192.168.1.1"
    host = questionary.text(
        "路由器管理 IP 地址",
        default=default_ip,
        qmark="▶",
        style=questionary.Style([
            ("qmark", "#58a6ff bold"),
            ("answer", "#e6edf3 bold"),
        ])
    ).ask()

    if not host:
        print("❌ IP 地址不能为空")
        sys.exit(1)

    # ── SSH 用户名 ──────────────────────────────────────
    default_user = cfg.get("user") or "root"
    user = questionary.text(
        "SSH 用户名",
        default=default_user,
        qmark="▶",
    ).ask()

    if not user:
        print("❌ 用户名不能为空")
        sys.exit(1)

    # ── 认证方式 ────────────────────────────────────────
    auth_choice = questionary.select(
        "认证方式",
        choices=[
            "🔑 密码认证（输入明文密码）",
            "🔐 SSH 密钥文件（推荐，更安全）",
            "⏭  暂不设置（手动配置）",
        ],
        qmark="▶",
        style=questionary.Style([
            ("qmark", "#58a6ff bold"),
            ("pointer", "#58a6ff bold"),
        ])
    ).ask()

    password = None
    identity_file = None

    if "密码" in auth_choice:
        password = questionary.password(
            "SSH 密码",
            qmark="▶",
        ).ask()
    elif "密钥" in auth_choice:
        default_key = cfg.get("identity_file") or os.path.expanduser("~/.ssh/id_rsa")
        identity_file = questionary.text(
            "SSH 私钥路径",
            default=default_key,
            qmark="▶",
        ).ask()
        if identity_file and not os.path.exists(os.path.expanduser(identity_file)):
            print(f"⚠  密钥文件不存在：{identity_file}")
            confirm = questionary.confirm("是否仍要保存路径？", default=False).ask()
            if not confirm:
                sys.exit(0)
    else:
        print("⏭  跳过认证配置（后续可用 openwrt-cli config 重新配置）")

    # ── 端口 ───────────────────────────────────────────
    default_port = str(cfg.get("port", 22))
    port_str = questionary.text(
        "SSH 端口",
        default=default_port,
        qmark="▶",
        validate=lambda s: s.isdigit() and 1 <= int(s) <= 65535,
    ).ask()
    port = int(port_str) if port_str else 22

    # ── 保存配置 ───────────────────────────────────────
    new_cfg = {
        "host": host,
        "user": user,
        "port": port,
    }
    if password:
        new_cfg["password"] = password
    if identity_file:
        new_cfg["identity_file"] = os.path.expanduser(identity_file)

    ConfigManager().save(new_cfg)

    # ── 测试连接 ───────────────────────────────────────
    print("")
    print("🔄 正在测试连接...")
    try:
        from core.ssh_client import SSHClient, SSHConnectionError
        client = SSHClient(host, user, password=password, port=port,
                           identity_file=identity_file)
        client.connect()
        client.exec("cat /proc/sys/kernel/hostname")
        client.disconnect()
        print("")
        print("╔══════════════════════════════════════╗")
        print("║  ✅ 连接成功！配置已保存！             ║")
        print("╚══════════════════════════════════════╝")
        print("")
        print(f"   IP:      {host}")
        print(f"   用户:    {user}")
        print(f"   端口:    {port}")
        if identity_file:
            print(f"   密钥:    {identity_file}")
        else:
            print(f"   密码:    {'•' * len(password) if password else '未设置'}")
        print("")
        print("👉  立即体验：openwrt-cli doctor")
        print("")
    except SSHConnectionError as e:
        print("")
        print("⚠  配置已保存，但连接测试失败：")
        print(f"   {e.message}")
        print("")
        print("👉  常见原因：IP 错误 / 密码不对 / SSH 服务未开启")
        print("   修正配置：openwrt-cli config")
        print("")
    except Exception as e:
        print("")
        print(f"⚠  配置已保存，连接测试异常：{e}")
        print("")
