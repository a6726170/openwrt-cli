# OpenWrt CLI — AI-Agent Ready 管理工具

通过 SSH 远程管理 OpenWrt 路由器，支持网络/防火墙/QoS/服务/监控等操作，JSON 输出格式专为 AI Agent 集成优化。

## 安装

**方式一：pip 安装（推荐）**
```bash
pip install git+https://github.com/YOUR_USERNAME/openwrt-cli.git
```

**方式二：从 PyPI（发布后可用）**
```bash
pip install openwrt-cli
```

**方式三：本地安装**
```bash
git clone https://github.com/YOUR_USERNAME/openwrt-cli.git
cd openwrt-cli
pip install -e .
```

## 快速开始

```bash
# 首次配置（保存连接参数）
openwrt-cli -H 192.168.1.1 -u root --password your_password --save-config

# 之后直接用
openwrt-cli -H 192.168.1.1 monitor system
openwrt-cli network leases
openwrt-cli doctor
```

## 功能模块

| 模块 | 子命令 | 说明 |
|------|--------|------|
| `monitor` | system / cpu / memory / processes / uptime | 系统监控 |
| `network` | interfaces / routes / dns / dhcp / leases | 网络管理（含 MAC 厂商识别）|
| `firewall` | rules / nat / zones / redirects / status | 防火墙管理 |
| `qos` | status / rules / classes / stats | 流量 QoS |
| `service` | list / status / start / stop / restart | 服务管理 |
| `user` | list / groups / add / passwd / delete | 用户管理 |
| `backup` | create / restore | 配置备份 |
| `system` | info / board / reboot / hostname | 系统操作 |
| `doctor` | (无参数) / --quick / --json | 路由器一键体检 |
| `interactive` | user / hostname / wifi / lan / service | 交互式配置向导 |

## 输出格式

```bash
# 文本（默认）
openwrt -H 192.168.1.1 network leases

# JSON（支持任意位置）
openwrt -H 192.168.1.1 -f json network leases
openwrt -H 192.168.1.1 network leases -f json

# 紧凑 JSON
openwrt -H 192.168.1.1 -f compact network leases
```

## 配置说明

首次运行后，配置保存在 `~/.openwrt-cli.yaml`，内容示例：

```yaml
host: 192.168.1.1
user: root
port: 22
# password: （加密存储或留空用密钥）
identity_file: ~/.ssh/id_rsa
```

## 依赖

- Python >= 3.8
- paramiko >= 3.0
- pyyaml >= 6.0
- questionary >= 2.0（仅交互模式）

## License

MIT
