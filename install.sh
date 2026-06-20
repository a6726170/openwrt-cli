#!/bin/bash
#============================================
# OpenWrt CLI 一键安装脚本（跨平台通用）
# 用法: curl -fsSL https://raw.githubusercontent.com/ikuaidev/openwrt-cli/main/install.sh | sh
# 或:   bash <(curl -fsSL https://raw.githubusercontent.com/ikuaidev/openwrt-cli/main/install.sh)
#============================================

set -e

REPO="ikuaidev/openwrt-cli"
INSTALL_DIR="${HOME}/.openwrt-cli"
BIN_DIR="${HOME}/.local/bin"
RELEASE_URL="https://github.com/${REPO}/releases/latest"
GITHUB_RAW="https://raw.githubusercontent.com/${REPO}/main"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }
done_msg(){ echo -e "${GREEN}[DONE]${NC} $1"; }

detect_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        MINGW*|MSYS*|CYGWIN*) echo "windows";;
        *)          echo "unknown";;
    esac
}

detect_python() {
    if command -v python3 &>/dev/null; then
        echo "python3"
    elif command -v python &>/dev/null; then
        echo "python"
    elif command -v py &>/dev/null; then
        echo "py"
    else
        echo ""
    fi
}

install_deps() {
    PYTHON=$(detect_python)
    if [ -z "$PYTHON" ]; then
        error "未找到 Python，请先安装 Python 3.8+"
        echo "  Linux/macOS: sudo apt install python3 python3-pip"
        echo "  Windows:     https://www.python.org/downloads/"
        exit 1
    fi

    info "检查依赖..."
    if ! $PYTHON -c "import paramiko" 2>/dev/null; then
        info "安装 Python 依赖: paramiko, pyyaml"
        if command -v pip3 &>/dev/null; then
            pip3 install paramiko pyyaml -q
        elif $PYTHON -m pip --version &>/dev/null; then
            $PYTHON -m pip install paramiko pyyaml -q
        else
            error "pip 未找到，请安装 pip"
            exit 1
        fi
    fi
    done_msg "依赖就绪"
}

install_cli() {
    OS=$(detect_os)
    PYTHON=$(detect_python)

    info "检测到系统: $OS"

    # 克隆或更新仓库
    if [ -d "${INSTALL_DIR}/.git" ]; then
        info "更新 openwrt-cli..."
        cd "${INSTALL_DIR}" && git pull
    else
        info "克隆 openwrt-cli 仓库..."
        mkdir -p "${INSTALL_DIR}"
        if command -v git &>/dev/null; then
            git clone --depth=1 "https://github.com/${REPO}.git" "${INSTALL_DIR}"
        else
            # 无 git，用 release zip
            warn "未安装 git，尝试下载 release 包..."
            TAG=$(curl -sL "https://api.github.com/repos/${REPO}/releases/latest" | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])" 2>/dev/null || echo "v1.0.0")
            curl -fsSL "https://github.com/${REPO}/archive/refs/tags/${TAG}.zip" -o "/tmp/openwrt-cli.zip"
            unzip -q "/tmp/openwrt-cli.zip" -d "${INSTALL_DIR}"
            mv "${INSTALL_DIR}/openwrt-cli-${TAG#v}"/* "${INSTALL_DIR}/"
            rm -rf "/tmp/openwrt-cli.zip"
        fi
    fi

    # 尝试 pip install（推荐）
    if $PYTHON -m pip --version &>/dev/null; then
        info "以开发模式安装..."
        cd "${INSTALL_DIR}"
        $PYTHON -m pip install -e . -q
        done_msg "安装完成！运行: openwrt -H <IP> -u root --password <密码> monitor system"
        return
    fi

    # 备选：直接加 PATH
    warn "pip 不可用，添加 ${INSTALL_DIR} 到 PATH 即可运行"
    SHELL_RC="${HOME}/.bashrc"
    if [ -f "${HOME}/.zshrc" ]; then SHELL_RC="${HOME}/.zshrc"; fi
    if ! grep -q "openwrt-cli" "${SHELL_RC}" 2>/dev/null; then
        echo '' >> "${SHELL_RC}"
        echo '# openwrt-cli' >> "${SHELL_RC}"
        echo "export PATH=\"\${HOME}/.openwrt-cli:\${PATH}\"" >> "${SHELL_RC}"
        done_msg "已写入 PATH 到 ${SHELL_RC}，运行: source ${SHELL_RC}"
    fi

    done_msg "安装完成！运行: python3 ${INSTALL_DIR}/main.py -H <IP> -u root --password <密码> monitor system"
}

quick_test() {
    info "快速测试（可选）..."
    read -p "请输入 OpenWrt 设备 IP [默认: 192.168.1.1]: " TEST_IP
    TEST_IP="${TEST_IP:-192.168.1.1}"
    read -p "用户名 [默认: root]: " TEST_USER
    TEST_USER="${TEST_USER:-root}"
    echo ""
    info "测试连接: ${TEST_USER}@${TEST_IP}"
    $PYTHON "${INSTALL_DIR}/main.py" -H "${TEST_IP}" -u "${TEST_USER}" --password "" monitor system 2>/dev/null && done_msg "连接成功！" || warn "连接失败，请检查参数"
}

# ---- 交互式引导安装 ----
main() {
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║   OpenWrt CLI 一键安装 (AI-Agent Ready)  ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""

    install_deps
    install_cli

    echo ""
    echo "─────────────────────────────"
    echo "安装完成！使用示例："
    echo ""
    echo "  # 首次配置（保存连接）"
    echo "  openwrt -H 192.168.1.1 -u root --password your_pass --save-config"
    echo ""
    echo "  # 之后直接用（无需再传参数）"
    echo "  openwrt monitor system"
    echo "  openwrt network leases"
    echo "  openwrt -f json network interfaces"
    echo ""
    echo "  # 获取完整帮助"
    echo "  openwrt --help"
    echo ""

    if [ -t 0 ]; then
        read -p "是否运行快速测试？[y/N]: " TRY_TEST
        if [ "$TRY_TEST" = "y" ] || [ "$TRY_TEST" = "Y" ]; then
            quick_test
        fi
    fi
}

main "$@"