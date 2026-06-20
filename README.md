# OpenWrt CLI

通过 SSH 远程管理 OpenWrt 路由器，一条命令搞定日常运维。专为 AI Agent 集成优化，支持 JSON 输出。

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 功能亮点

- 🔍 **10 项路由器体检**（doctor 命令）—— 一键诊断 SSH/固件/负载/内存/WiFi/DHCP/防火墙/ZeroTier/WAN/QoS，发现问题给出修复建议
- 📡 **MAC 厂商识别** —— 自动识别在线设备品牌（Microsoft/Apple/Xiaomi/Samsung...）
- 🤖 **AI-Agent Ready** —— JSON 输出格式，AI 可直接解析
- 🔧 **交互式配置向导** —— 修改密码/主机名/WiFi/LAN/服务，无需记忆 UCI 命令
- 🔒 **连接故障诊断** —— SSH 连不上时给出具体原因和修复步骤
- 📦 **跨平台** —— Linux / macOS / Windows 均可使用

---

## 安装

**pip 安装（推荐）**
```bash
pip install git+https://github.com/a6726170/openwrt-cli.git
```

**从源码安装**
```bash
git clone https://github.com/a6726170/openwrt-cli.git
cd openwrt-cli
pip install -e .
```

**Windows 一键安装**
```cmd
install.bat
```

**依赖：** Python >= 3.8，paramiko >= 3.0，pyyaml >= 6.0，questionary >= 2.0

---

## 快速开始

```bash
# 首次配置（保存连接参数，只需一次）
openwrt-cli -H 192.168.1.1 -u root --password your_password --save-config

# 之后直接用（无需重复输入 IP）
openwrt-cli network leases
openwrt-cli monitor system
```

---

## 命令概览

### 体检
```bash
openwrt-cli doctor          # 完整体检（10项）
openwrt-cli doctor --quick   # 快速检查
openwrt-cli doctor --json    # JSON 快速结果
```

### 监控
```bash
openwrt-cli monitor system     # 系统概况（CPU/内存/uptime/负载）
openwrt-cli monitor memory     # 内存详情
openwrt-cli monitor processes  # 进程列表
openwrt-cli monitor uptime     # 运行时间
```

### 网络
```bash
openwrt-cli network interfaces  # 所有网络接口
openwrt-cli network routes       # 路由表
openwrt-cli network leases        # DHCP 在线设备（含 MAC 厂商）
openwrt-cli network dns           # DNS 服务器
openwrt-cli network reload       # 重启网络服务
```

### 服务
```bash
openwrt-cli service list              # 所有服务状态
openwrt-cli service restart network   # 重启网络服务
openwrt-cli service stop firewall     # 停止防火墙
```

### 系统
```bash
openwrt-cli system info       # 固件/内核/型号
openwrt-cli system reboot      # 重启路由器
openwrt-cli system hostname    # 查询主机名
openwrt-cli system hostname NewName  # 修改主机名
```

### 配置
```bash
openwrt-cli -I                     # 交互式配置向导（全菜单）
openwrt-cli interactive hostname   # 修改主机名
openwrt-cli interactive wifi      # 修改 WiFi
openwrt-cli interactive service   # 服务管理
```

### 备份
```bash
openwrt-cli backup create              # 备份配置
openwrt-cli backup create -o /tmp/bak.tar.gz  # 指定输出路径
openwrt-cli backup restore /tmp/bak.tar.gz    # 恢复备份
```

---

## 输出格式

```bash
# 文本（默认）
openwrt-cli network leases

# JSON（-f json 可放在子命令前或后）
openwrt-cli -f json network leases
openwrt-cli network leases -f json

# 紧凑 JSON
openwrt-cli -f compact network leases
```

---

## 配置文件

首次使用 `--save-config` 后，连接参数保存在 `~/.openwrt-cli.yaml`：

```yaml
host: 192.168.1.1
user: root
port: 22
# password: 建议使用 SSH 密钥或环境变量
identity_file: ~/.ssh/id_rsa
```

---

## 目录结构

```
openwrt-cli/
├── main.py              # CLI 入口（argparse）
├── setup.py              # pip 安装配置
├── requirements.txt      # Python 依赖
├── LICENSE               # MIT 开源协议
├── commands/             # 子命令模块
│   ├── doctor.py         # 路由器体检
│   ├── monitor.py        # 系统监控
│   ├── network.py        # 网络管理
│   ├── firewall.py      # 防火墙
│   ├── qos.py           # 流量控制
│   ├── service.py       # 服务管理
│   ├── system.py        # 系统操作
│   ├── user.py          # 用户管理
│   ├── backup.py        # 配置备份
│   └── interactive.py   # 交互式向导
├── core/
│   ├── ssh_client.py    # SSH 连接（含诊断）
│   ├── mac_vendor.py    # MAC 厂商库（200+ OUI）
│   ├── config.py        # YAML 配置管理
│   └── output.py        # text/json/compact 输出
└── install.sh / install.bat  # 跨平台安装脚本
```

---

## 常见问题

**Q: SSH 连接失败？**
```bash
# 先诊断问题
ssh -v -p 22 root@192.168.1.1

# 检查密码是否正确
# 检查路由器 SSH 服务是否开启
# 检查防火墙是否放行
```

**Q: 想用密钥登录？**
```bash
# 先生成 SSH 密钥
ssh-keygen -t rsa

# 把公钥传到路由器
ssh-copy-id root@192.168.1.1

# 之后连接无需密码
openwrt-cli -H 192.168.1.1 -i ~/.ssh/id_rsa network leases
```

**Q: 路由器在 NAT 后面，无法从本地直连？**
通过 ZeroTier 内网穿透连接：
```bash
openwrt-cli -H 192.168.192.7  # ZeroTier 分配的 IP
```

---

## License

MIT License — 详见 [LICENSE](LICENSE) 文件
