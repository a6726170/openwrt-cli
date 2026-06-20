#!/bin/bash
# openwrt-cli 一键安装脚本 (Linux / macOS)
# 使用方法: curl -fsSL https://raw.githubusercontent.com/a6726170/openwrt-cli/main/share/openwrt-cli.sh | bash

set -e

echo "============================================"
echo "  openwrt-cli 一键安装"
echo "  OpenWrt CLI 管理工具"
echo "============================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

# 检查 pip
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "❌ 未找到 pip，请先安装 pip"
    exit 1
fi

PIP_CMD=$(command -v pip3 || command -v pip)
PYTHON_CMD=$(command -v python3)

echo "✅ Python: $($PYTHON_CMD --version)"
echo "✅ pip: $($PIP_CMD --version | head -1)"
echo ""

echo "📦 正在安装 openwrt-cli..."
$PIP_CMD install git+https://github.com/a6726170/openwrt-cli.git

echo ""
echo "============================================"
echo "  安装成功！"
echo "============================================"
echo ""
echo "使用示例："
echo ""
echo "  # 首次配置（保存连接参数）"
echo "  openwrt-cli -H 192.168.1.1 -u root --password 密码 --save-config"
echo ""
echo "  # 路由器体检"
echo "  openwrt-cli doctor"
echo ""
echo "  # 查看在线设备"
echo "  openwrt-cli network leases"
echo ""
echo "  # 系统状态"
echo "  openwrt-cli monitor system"
echo ""
echo "📂 文档: https://github.com/a6726170/openwrt-cli"
