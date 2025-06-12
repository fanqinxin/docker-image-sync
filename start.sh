#!/bin/bash

# Docker镜像同步工具启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# 显示标题
show_banner() {
    echo "=================================================="
    echo "        🐳 Docker镜像同步工具 v1.0.0"
    echo "=================================================="
    echo
}

# 检查Python环境
check_python() {
    log_info "检查Python环境..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python3未安装，请先安装Python3.7+"
        exit 1
    fi
    
    python_version=$(python3 --version | awk '{print $2}')
    log_info "Python版本: $python_version"
    
    # 检查Python版本是否大于等于3.7
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 7) else 1)"; then
        log_info "Python版本符合要求"
    else
        log_error "Python版本需要3.7或以上"
        exit 1
    fi
}

# 检查pip
check_pip() {
    log_info "检查pip..."
    
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3未安装，请先安装pip3"
        exit 1
    fi
    
    pip_version=$(pip3 --version | awk '{print $2}')
    log_info "pip版本: $pip_version"
}

# 安装Python依赖
install_dependencies() {
    log_info "安装Python依赖..."
    
    if [[ ! -f requirements.txt ]]; then
        log_error "requirements.txt文件不存在"
        exit 1
    fi
    
    # 创建虚拟环境（可选）
    if [[ "$1" == "--venv" ]]; then
        log_info "创建虚拟环境..."
        python3 -m venv venv
        source venv/bin/activate
        log_info "已激活虚拟环境"
    fi
    
    pip3 install -r requirements.txt
    log_info "依赖安装完成"
}

# 检查Skopeo
check_skopeo() {
    log_info "检查Skopeo工具..."
    
    if command -v skopeo &> /dev/null; then
        skopeo_version=$(skopeo --version | head -1)
        log_info "Skopeo已安装: $skopeo_version"
        return 0
    else
        log_warn "Skopeo未安装"
        return 1
    fi
}

# 安装Skopeo
install_skopeo() {
    log_info "开始安装Skopeo..."
    
    if [[ -x ./install_skopeo.sh ]]; then
        log_info "使用安装脚本安装Skopeo..."
        ./install_skopeo.sh
    else
        log_warn "安装脚本不存在或无执行权限，请手动安装Skopeo"
        log_info "参考: https://github.com/containers/skopeo/blob/main/install.md"
        exit 1
    fi
}

# 检查配置文件
check_config() {
    log_info "检查配置文件..."
    
    if [[ ! -f config/registries.yaml ]]; then
        log_warn "配置文件不存在，将创建默认配置..."
        mkdir -p config
        # 这里会在app.py启动时自动创建默认配置
    else
        log_info "配置文件存在: config/registries.yaml"
    fi
}

# 检查端口
check_port() {
    local port=${1:-5000}
    log_info "检查端口 $port 是否可用..."
    
    if command -v netstat &> /dev/null; then
        if netstat -tuln | grep -q ":$port "; then
            log_warn "端口 $port 已被占用"
            log_info "请修改启动端口或停止占用端口的服务"
            return 1
        fi
    elif command -v ss &> /dev/null; then
        if ss -tuln | grep -q ":$port "; then
            log_warn "端口 $port 已被占用"
            log_info "请修改启动端口或停止占用端口的服务"
            return 1
        fi
    else
        log_warn "无法检查端口占用情况"
    fi
    
    log_info "端口 $port 可用"
    return 0
}

# 启动服务
start_service() {
    local mode=${1:-development}
    local port=${2:-5000}
    local host=${3:-0.0.0.0}
    
    log_info "启动Docker镜像同步服务..."
    log_info "模式: $mode"
    log_info "地址: http://$host:$port"
    
    if [[ "$mode" == "production" ]]; then
        log_info "生产模式启动..."
        
        if command -v gunicorn &> /dev/null; then
            gunicorn --worker-class eventlet -w 1 --bind $host:$port --timeout 300 --max-requests 1000 --max-requests-jitter 100 --preload app:app
        else
            log_warn "Gunicorn未安装，使用开发模式启动..."
            export FLASK_ENV=production
            python3 app.py
        fi
    else
        log_info "开发模式启动..."
        export FLASK_ENV=development
        export FLASK_DEBUG=1
        python3 app.py
    fi
}

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  -h, --help              显示帮助信息"
    echo "  -m, --mode MODE         运行模式 (development|production) [默认: development]"
    echo "  -p, --port PORT         端口号 [默认: 5000]"
    echo "  --host HOST             绑定地址 [默认: 0.0.0.0]"
    echo "  --install-deps          安装Python依赖"
    echo "  --install-skopeo        安装Skopeo工具"
    echo "  --venv                  使用虚拟环境"
    echo "  --check-only            仅检查环境，不启动服务"
    echo
    echo "示例:"
    echo "  $0                      # 开发模式启动"
    echo "  $0 -m production        # 生产模式启动"
    echo "  $0 -p 8080              # 指定端口启动"
    echo "  $0 --install-deps       # 安装依赖"
    echo "  $0 --install-skopeo     # 安装Skopeo"
    echo
}

# 主函数
main() {
    local mode="development"
    local port="5000"
    local host="0.0.0.0"
    local install_deps=false
    local install_skopeo_flag=false
    local use_venv=false
    local check_only=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -m|--mode)
                mode="$2"
                shift 2
                ;;
            -p|--port)
                port="$2"
                shift 2
                ;;
            --host)
                host="$2"
                shift 2
                ;;
            --install-deps)
                install_deps=true
                shift
                ;;
            --install-skopeo)
                install_skopeo_flag=true
                shift
                ;;
            --venv)
                use_venv=true
                shift
                ;;
            --check-only)
                check_only=true
                shift
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    show_banner
    
    # 环境检查
    check_python
    check_pip
    
    # 安装依赖
    if [[ "$install_deps" == true ]]; then
        install_dependencies $([ "$use_venv" == true ] && echo "--venv")
    fi
    
    # 安装Skopeo
    if [[ "$install_skopeo_flag" == true ]]; then
        install_skopeo
    fi
    
    # 检查Skopeo
    if ! check_skopeo; then
        log_warn "Skopeo未安装，部分功能可能无法使用"
        read -p "是否现在安装Skopeo？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_skopeo
        fi
    fi
    
    # 检查配置
    check_config
    
    # 仅检查模式
    if [[ "$check_only" == true ]]; then
        log_info "环境检查完成"
        exit 0
    fi
    
    # 检查端口
    if ! check_port "$port"; then
        exit 1
    fi
    
    # 启动服务
    echo
    log_info "所有检查通过，正在启动服务..."
    echo
    log_info "访问地址:"
    log_info "  主应用: http://$host:$port"
    log_info "  演示页面: http://$host:$port/demo.html"
    echo
    start_service "$mode" "$port" "$host"
}

# 运行主函数
main "$@" 