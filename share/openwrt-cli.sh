#!/bin/bash
# openwrt-cli 一键安装脚本 (Linux / macOS)
# 使用方法: curl -fsSL https://raw.githubusercontent.com/a6726170/openwrt-cli/main/share/openwrt-cli.sh | bash

set -e

echo ""
echo "============================================"
echo "  openwrt-cli 一键安装"
echo "  OpenWrt CLI 管理工具"
echo "============================================"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo ""
    echo "❌ 未找到 python3，请先安装 Python 3.8+"
    echo "   Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "   macOS: brew install python3"
    exit 1
fi

# 检查 pip
PIP_CMD=""
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
else
    echo ""
    echo "❌ 未找到 pip，请先安装"
    exit 1
fi

PYTHON_CMD=$(command -v python3)
echo ""
echo "✅ Python:  $($PYTHON_CMD --version)"
echo "✅ pip:     $($PIP_CMD --version | head -1)"

# 安装
echo ""
echo "📦 正在安装 openwrt-cli..."
$PIP_CMD install git+https://github.com/a6726170/openwrt-cli.git --quiet

echo "✅ 安装完成！"
echo ""

# 自动进入配置向导（首次配置）
echo "============================================"
echo "  首次配置 — 连接路由器"
echo "============================================"
echo ""
$PYTHON_CMD -m openwrt_cli config
