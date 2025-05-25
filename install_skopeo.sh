#!/bin/bash

# Skopeo 安装脚本
# 支持 CentOS/RHEL, Ubuntu/Debian, Fedora 等发行版

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否以root权限运行
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要以root权限运行"
        log_info "请使用: sudo $0"
        exit 1
    fi
}

# 检测操作系统
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    elif [[ -f /etc/redhat-release ]]; then
        OS="centos"
        VERSION=$(cat /etc/redhat-release | grep -oE '[0-9]+\.[0-9]+' | head -1)
    elif [[ -f /etc/debian_version ]]; then
        OS="debian"
        VERSION=$(cat /etc/debian_version)
    else
        log_error "无法检测操作系统类型"
        exit 1
    fi
    
    log_info "检测到操作系统: $OS $VERSION"
}

# 检查Skopeo是否已安装
check_skopeo() {
    if command -v skopeo &> /dev/null; then
        local version=$(skopeo --version | head -1)
        log_info "Skopeo已安装: $version"
        return 0
    else
        log_warn "Skopeo未安装"
        return 1
    fi
}

# CentOS/RHEL 安装
install_centos() {
    log_info "在CentOS/RHEL上安装Skopeo..."
    
    # 安装EPEL仓库
    if ! rpm -qa | grep -q epel-release; then
        log_info "安装EPEL仓库..."
        yum install -y epel-release
    fi
    
    # 更新yum缓存
    yum makecache fast
    
    # 安装Skopeo
    log_info "安装Skopeo..."
    yum install -y skopeo
}

# Ubuntu/Debian 安装
install_ubuntu() {
    log_info "在Ubuntu/Debian上安装Skopeo..."
    
    # 更新包列表
    apt-get update
    
    # 安装Skopeo
    log_info "安装Skopeo..."
    apt-get install -y skopeo
}

# Fedora 安装
install_fedora() {
    log_info "在Fedora上安装Skopeo..."
    
    # 安装Skopeo
    log_info "安装Skopeo..."
    dnf install -y skopeo
}

# openSUSE 安装
install_opensuse() {
    log_info "在openSUSE上安装Skopeo..."
    
    # 安装Skopeo
    log_info "安装Skopeo..."
    zypper install -y skopeo
}

# Alpine Linux 安装
install_alpine() {
    log_info "在Alpine Linux上安装Skopeo..."
    
    # 更新包索引
    apk update
    
    # 安装Skopeo
    log_info "安装Skopeo..."
    apk add skopeo
}

# 从源码编译安装
install_from_source() {
    log_warn "将从源码编译安装Skopeo..."
    log_warn "这可能需要较长时间..."
    
    # 安装依赖
    case $OS in
        "centos"|"rhel")
            yum groupinstall -y "Development Tools"
            yum install -y git golang gpgme-devel libassuan-devel btrfs-progs-devel device-mapper-devel
            ;;
        "ubuntu"|"debian")
            apt-get update
            apt-get install -y git golang-go libgpgme11-dev libassuan-dev libbtrfs-dev libdevmapper-dev
            ;;
        "fedora")
            dnf groupinstall -y "Development Tools"
            dnf install -y git golang gpgme-devel libassuan-devel btrfs-progs-devel device-mapper-devel
            ;;
        *)
            log_error "不支持在此系统上从源码编译"
            exit 1
            ;;
    esac
    
    # 克隆源码
    cd /tmp
    git clone https://github.com/containers/skopeo
    cd skopeo
    
    # 编译
    make bin/skopeo
    
    # 安装
    make install
    
    # 清理
    cd /
    rm -rf /tmp/skopeo
}

# 主安装函数
install_skopeo() {
    case $OS in
        "centos"|"rhel")
            install_centos
            ;;
        "ubuntu"|"debian")
            install_ubuntu
            ;;
        "fedora")
            install_fedora
            ;;
        "opensuse"*)
            install_opensuse
            ;;
        "alpine")
            install_alpine
            ;;
        *)
            log_warn "不支持的操作系统: $OS"
            log_info "尝试从源码编译安装..."
            install_from_source
            ;;
    esac
}

# 验证安装
verify_installation() {
    log_info "验证Skopeo安装..."
    
    if command -v skopeo &> /dev/null; then
        local version=$(skopeo --version)
        log_info "Skopeo安装成功!"
        log_info "版本信息: $version"
        
        # 测试基本功能
        log_info "测试Skopeo基本功能..."
        if skopeo inspect docker://alpine:latest > /dev/null 2>&1; then
            log_info "Skopeo功能测试通过!"
        else
            log_warn "Skopeo功能测试失败，可能需要网络连接"
        fi
    else
        log_error "Skopeo安装失败!"
        exit 1
    fi
}

# 显示使用说明
show_usage() {
    log_info "Skopeo安装完成！"
    echo
    echo "常用命令示例:"
    echo "1. 查看镜像信息:"
    echo "   skopeo inspect docker://nginx:latest"
    echo
    echo "2. 复制镜像:"
    echo "   skopeo copy docker://nginx:latest docker://your-registry.com/nginx:latest"
    echo
    echo "3. 删除镜像:"
    echo "   skopeo delete docker://your-registry.com/nginx:latest"
    echo
    echo "更多信息请访问: https://github.com/containers/skopeo"
}

# 主函数
main() {
    echo "==============================================="
    echo "            Skopeo 自动安装脚本"
    echo "==============================================="
    echo
    
    check_root
    detect_os
    
    if check_skopeo; then
        echo
        read -p "Skopeo已安装，是否重新安装？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "安装取消"
            exit 0
        fi
    fi
    
    echo
    log_info "开始安装Skopeo..."
    install_skopeo
    
    echo
    verify_installation
    
    echo
    show_usage
}

# 运行主函数
main "$@" 