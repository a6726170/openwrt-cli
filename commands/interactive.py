"""交互式配置命令（Phase 1）"""
import re
import questionary


# ──────────────────────────────────────────────
# 通用工具
# ──────────────────────────────────────────────

def is_valid_ip(ip: str) -> bool:
    pattern = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    return bool(re.match(pattern, ip))


def is_valid_hostname(name: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$", name))


def is_valid_password(pwd: str) -> bool:
    return 6 <= len(pwd) <= 128


def confirm_apply(ssh, warning: str) -> bool:
    """显示警告信息，返回用户是否确认继续"""
    print(f"\n⚠️  {warning}")
    return questionary.confirm("确认执行？", default=False).ask()


def apply_and_reload(ssh, config_type: str, service_name: str):
    """执行 uci commit + service reload，返回结果"""
    ssh.exec(f"uci commit {config_type}", timeout=10)
    out = ssh.exec(f"/etc/init.d/{service_name} reload 2>&1", timeout=15)
    return out


# ──────────────────────────────────────────────
# 用户密码修改
# ──────────────────────────────────────────────

def user_passwd_interactive(ssh):
    """交互式修改用户密码"""
    # 1. 列出所有用户
    raw = ssh.exec("cat /etc/passwd")
    users = []
    for line in raw.strip().splitlines():
        parts = line.split(":")
        if len(parts) >= 7 and parts[6] not in ("/bin/false", "/usr/sbin/nologin", "/sbin/nologin"):
            users.append(parts[0])

    if not users:
        return {"status": "error", "message": "未找到可登录的用户"}

    # 2. 选择用户
    username = questionary.select(
        "请选择要修改密码的用户：",
        choices=users,
    ).ask()

    # 3. 输入新密码
    password = ""
    while True:
        password = questionary.password("请输入新密码（6位以上）：").ask()
        if not is_valid_password(password):
            print("❌ 密码长度需至少 6 位")
            continue
        confirm = questionary.password("请再次输入新密码：").ask()
        if confirm != password:
            print("❌ 两次输入不一致，请重试")
            continue
        break

    # 4. 确认操作
    if not confirm_apply(ssh, f"将修改用户 [{username}] 的密码"):
        return {"status": "cancelled", "message": "操作已取消"}

    # 5. 执行
    out = ssh.exec(f'echo "{username}:{password}" | chpasswd -c SHA512 2>&1')

    if "error" in out.lower() or "failed" in out.lower():
        return {"status": "error", "message": f"修改失败: {out}"}

    return {
        "status": "ok",
        "message": f"用户 [{username}] 密码修改成功",
        "username": username,
    }


# ──────────────────────────────────────────────
# 主机名修改
# ──────────────────────────────────────────────

def system_hostname_interactive(ssh):
    """交互式修改系统主机名"""
    # 1. 显示当前主机名
    current = ssh.exec("uci get system.@system[0].hostname 2>/dev/null || hostname").strip()
    print(f"\n当前主机名：{current}")

    # 2. 输入新主机名
    new_hostname = ""
    while True:
        new_hostname = questionary.text(
            "请输入新主机名：",
            default=current,
            validate=lambda x: is_valid_hostname(x) or "主机名格式不正确（参考：my-router、router.home）"
        ).ask()
        if new_hostname == current:
            print("⚠️  新主机名与当前相同，未做修改")
            return {"status": "ok", "message": "主机名未变化", "hostname": current}
        break

    # 3. 确认
    if not confirm_apply(ssh, f"主机名将修改为 [{new_hostname}]"):
        return {"status": "cancelled", "message": "操作已取消"}

    # 4. 执行
    ssh.exec(f"uci set system.@system[0].hostname='{new_hostname}'", timeout=10)
    ssh.exec("uci commit system", timeout=10)
    out = ssh.exec("/etc/init.d/system reload 2>&1", timeout=15)

    # 同步改 /etc/config/system 和 /proc/sys/kernel/hostname
    ssh.exec(f"hostname {new_hostname}")

    return {
        "status": "ok",
        "message": f"主机名已修改为 [{new_hostname}]",
        "old_hostname": current,
        "new_hostname": new_hostname,
    }


# ──────────────────────────────────────────────
# WiFi SSID / 密码修改
# ──────────────────────────────────────────────

def wifi_interactive(ssh):
    """交互式修改 WiFi SSID 和密码"""
    # 1. 获取当前 WiFi 配置
    wireless_raw = ssh.exec("uci show wireless 2>/dev/null")

    # 解析 radio 和 wifi-iface
    radios = {}
    for line in wireless_raw.strip().splitlines():
        if "=wifi-device" in line:
            key = line.split("=")[0].replace("wireless.", "")
            radios[key] = {"device": key}
        if "=wifi-iface" in line:
            # 找到对应的 radio
            pass  # 后续解析

    # 2. 读完整配置
    sections = ssh.exec("uci show wireless 2>/dev/null")

    # 提取所有 wifi-iface section
    iface_sections = []
    current_section = {}
    for line in sections.strip().splitlines():
        if "=wifi-iface" in line:
            if current_section:
                iface_sections.append(current_section)
            current_section = {"_key": line.split("=")[0]}
        elif "=" in line and current_section:
            k, v = line.split("=", 1)
            ck = k.replace("wireless.", "")
            current_section[ck] = v

    if current_section:
        iface_sections.append(current_section)

    if not iface_sections:
        return {"status": "error", "message": "未找到 WiFi 配置，请确认设备支持 WiFi"}

    # 3. 选择要修改的 AP
    choices = []
    for sec in iface_sections:
        dev = sec.get("device", "?")
        ssid = sec.get("ssid", "(未设置)")
        network = sec.get("network", "?")
        choices.append(f"[{dev}] SSID: {ssid}  (network: {network})")

    choice = questionary.select("请选择要修改的 WiFi：", choices=choices).ask()
    idx = choices.index(choice)
    section = iface_sections[idx]
    sec_key = section["_key"]

    current_ssid = section.get("ssid", "")
    current_key = section.get("key", "")

    # 4. 选择修改项
    modify_ssid = questionary.confirm("修改 SSID？", default=True).ask()
    new_ssid = current_ssid
    if modify_ssid:
        new_ssid = questionary.text("新 SSID：", default=current_ssid).ask()

    modify_key = questionary.confirm("修改 WiFi 密码？", default=True).ask()
    new_key = current_key
    if modify_key:
        new_key = ""
        while True:
            new_key = questionary.password("新 WiFi 密码（8位以上）：").ask()
            if len(new_key) < 8:
                print("❌ 密码长度需至少 8 位")
                continue
            break

    # 5. 无变更检查
    if new_ssid == current_ssid and new_key == current_key:
        return {"status": "ok", "message": "未做任何修改"}

    # 6. 确认
    changes = []
    if new_ssid != current_ssid:
        changes.append(f"SSID: {current_ssid} → {new_ssid}")
    if new_key != current_key:
        changes.append(f"密码: {'***' + current_key[-3:] if current_key else '(未设置)'} → {'*' * len(new_key)}")

    if not confirm_apply(ssh, "WiFi 配置将做以下变更：\n  " + "\n  ".join(changes) + "\n⚠️ 修改后 WiFi 会短暂断开"):
        return {"status": "cancelled", "message": "操作已取消"}

    # 7. 执行
    if new_ssid != current_ssid:
        ssh.exec(f"uci set wireless.{sec_key}.ssid='{new_ssid}'", timeout=10)
    if new_key != current_key:
        ssh.exec(f"uci set wireless.{sec_key}.key='{new_key}'", timeout=10)

    ssh.exec("uci commit wireless", timeout=10)
    out = ssh.exec("/etc/init.d/network reload 2>&1", timeout=20)

    return {
        "status": "ok",
        "message": "WiFi 配置已更新",
        "changes": changes,
    }


# ──────────────────────────────────────────────
# 网络接口 IP 修改
# ──────────────────────────────────────────────

def network_lan_interactive(ssh):
    """交互式修改 LAN 口 IP"""
    # 1. 获取当前 LAN 配置
    current_ip = ssh.exec("uci get network.lan.ipaddr 2>/dev/null").strip() or "192.168.1.1"
    current_mask = ssh.exec("uci get network.lan.netmask 2>/dev/null").strip() or "255.255.255.0"
    current_gateway = ssh.exec("uci get network.lan.ipaddr 2>/dev/null").strip()

    print(f"\n当前 LAN IP：{current_ip} / {current_mask}")

    # 2. 输入新 IP
    new_ip = ""
    while True:
        new_ip = questionary.text(
            "请输入新 LAN IP：",
            default=current_ip,
            validate=lambda x: is_valid_ip(x) or "IP 格式不正确"
        ).ask()
        if new_ip == current_ip:
            print("⚠️  新 IP 与当前相同，未做修改")
            return {"status": "ok", "message": "IP 未变化", "ip": current_ip}
        break

    # 3. 确认
    if not confirm_apply(ssh, f"LAN IP 将修改为 [{new_ip}]，之后需用新 IP 访问路由器"):
        return {"status": "cancelled", "message": "操作已取消"}

    # 4. 执行
    ssh.exec(f"uci set network.lan.ipaddr='{new_ip}'", timeout=10)
    out = apply_and_reload(ssh, "network", "network")

    # 验证
    import time; time.sleep(2)
    verified = ssh.exec(f"ping -c 1 -W 2 {new_ip} 2>&1 | head -3")

    return {
        "status": "ok",
        "message": f"LAN IP 已修改为 [{new_ip}]",
        "old_ip": current_ip,
        "new_ip": new_ip,
    }


# ──────────────────────────────────────────────
# 服务启用 / 禁用
# ──────────────────────────────────────────────

def service_toggle_interactive(ssh):
    """交互式启用/禁用服务"""
    # 获取所有 init.d 服务
    raw = ssh.exec("ls /etc/init.d/ 2>/dev/null")
    services = [s.strip() for s in raw.strip().splitlines() if s.strip()]

    if not services:
        return {"status": "error", "message": "未找到任何服务"}

    # 过滤出有 enable 能力的
    enabled = []
    disabled = []
    for svc in services:
        out = ssh.exec(f"/etc/init.d/{svc} enabled 2>/dev/null && echo 'y' || echo 'n'", timeout=5)
        if "y" in out:
            enabled.append(svc)
        else:
            disabled.append(svc)

    # 选择操作
    action = questionary.select(
        "请选择操作：",
        choices=["🔵 禁用一个服务", "🟢 启用一个服务", "❌ 停止运行中的服务", "✅ 启动已停止的服务"]
    ).ask()

    if "禁用" in action:
        target = questionary.select("选择要禁用的服务：", choices=services).ask()
        out = ssh.exec(f"/etc/init.d/{target} disable 2>&1", timeout=10)
        return {"status": "ok", "action": "disable", "service": target, "output": out.strip()}
    elif "启用" in action:
        target = questionary.select("选择要启用的服务：", choices=services).ask()
        out = ssh.exec(f"/etc/init.d/{target} enable 2>&1", timeout=10)
        return {"status": "ok", "action": "enable", "service": target, "output": out.strip()}
    elif "停止" in action:
        if not enabled:
            return {"status": "error", "message": "没有运行中的服务"}
        target = questionary.select("选择要停止的服务：", choices=enabled).ask()
        if not confirm_apply(ssh, f"停止服务 [{target}] 可能影响网络连接"):
            return {"status": "cancelled"}
        out = ssh.exec(f"/etc/init.d/{target} stop 2>&1", timeout=15)
        return {"status": "ok", "action": "stop", "service": target, "output": out.strip()}
    else:
        if not disabled:
            return {"status": "error", "message": "没有已停止的服务"}
        target = questionary.select("选择要启动的服务：", choices=disabled).ask()
        out = ssh.exec(f"/etc/init.d/{target} start 2>&1", timeout=15)
        return {"status": "ok", "action": "start", "service": target, "output": out.strip()}


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def run_interactive(ssh, output, target):
    """
    交互式配置入口
    target: 子命令名（config/user/system/service/network）
    """
    dispatch = {
        "config":  config_menu,
        "user":    user_passwd_interactive,
        "hostname": system_hostname_interactive,
        "wifi":    wifi_interactive,
        "lan":     network_lan_interactive,
        "service": service_toggle_interactive,
    }

    if target not in dispatch:
        # 通用配置菜单（顶层 interactive 或 config）
        return config_menu(ssh)

    result = dispatch[target](ssh)
    return result


def config_menu(ssh):
    """顶层配置菜单"""
    choice = questionary.select(
        "╔══════════════════════════════════════╗\n"
        "║    🔧 OpenWrt 交互式配置             ║\n"
        "╚══════════════════════════════════════╝\n"
        "请选择要配置的项目：",
        choices=[
            "👤 修改用户密码",
            "🖥️  修改主机名",
            "📡 修改 WiFi (SSID / 密码)",
            "🌐 修改 LAN 口 IP",
            "⚙️  服务管理（启用/禁用/启停）",
        ]
    ).ask()

    dispatch = {
        "👤 修改用户密码":     ("user", user_passwd_interactive),
        "🖥️  修改主机名":      ("hostname", system_hostname_interactive),
        "📡 修改 WiFi":        ("wifi", wifi_interactive),
        "🌐 修改 LAN 口 IP":   ("lan", network_lan_interactive),
        "⚙️  服务管理":        ("service", service_toggle_interactive),
    }

    key, func = dispatch[choice]
    result = func(ssh)

    # 打印结果
    if result.get("status") == "ok":
        print(f"\n✅ {result.get('message', '操作成功')}")
    elif result.get("status") == "cancelled":
        print(f"\n↩️  操作已取消")
    else:
        print(f"\n❌ {result.get('message', '操作失败')}")

    return result