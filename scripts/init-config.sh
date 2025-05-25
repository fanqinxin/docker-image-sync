#!/bin/bash

# Docker镜像同步工具 - 配置初始化脚本
# 用于从示例文件生成实际配置文件

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

# 检查Python是否可用
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python未找到，请先安装Python"
        exit 1
    fi
}

# 生成密码哈希
generate_password_hash() {
    local password="$1"
    $PYTHON_CMD -c "
import bcrypt
password = '$password'.encode('utf-8')
hashed = bcrypt.hashpw(password, bcrypt.gensalt())
print(hashed.decode('utf-8'))
"
}

# 生成随机密钥
generate_secret_key() {
    $PYTHON_CMD -c "
import secrets
print(secrets.token_hex(32))
"
}

# 初始化用户配置
init_users_config() {
    local config_file="config/users.yaml"
    local example_file="config/users.yaml.example"
    
    if [[ -f "$config_file" ]]; then
        log_warn "配置文件 $config_file 已存在"
        read -p "是否覆盖? (y/N): " overwrite
        if [[ ! "$overwrite" =~ ^[Yy] ]]; then
            log_info "跳过用户配置初始化"
            return
        fi
    fi
    
    if [[ ! -f "$example_file" ]]; then
        log_error "示例文件 $example_file 不存在"
        return 1
    fi
    
    log_info "初始化用户配置..."
    
    # 复制示例文件
    cp "$example_file" "$config_file"
    
    # 生成管理员密码
    echo ""
    log_info "设置管理员账户"
    read -p "管理员用户名 (默认: admin): " admin_username
    admin_username=${admin_username:-admin}
    
    read -s -p "管理员密码 (默认: admin123): " admin_password
    echo ""
    admin_password=${admin_password:-admin123}
    
    read -p "管理员邮箱 (默认: admin@example.com): " admin_email
    admin_email=${admin_email:-admin@example.com}
    
    # 生成密码哈希
    log_info "生成密码哈希..."
    password_hash=$(generate_password_hash "$admin_password")
    
    # 生成会话密钥
    log_info "生成会话密钥..."
    secret_key=$(generate_secret_key)
    
    # 替换配置文件中的占位符
    sed -i "s/admin:/$admin_username:/" "$config_file"
    sed -i "s/username: admin/username: $admin_username/" "$config_file"
    sed -i "s|\$2b\$12\$example\.hash\.please\.change\.in\.production|$password_hash|" "$config_file"
    sed -i "s/admin@example.com/$admin_email/" "$config_file"
    sed -i "s/your-secret-key-change-in-production/$secret_key/" "$config_file"
    
    log_info "用户配置初始化完成: $config_file"
    log_info "管理员用户名: $admin_username"
    log_info "管理员密码: $admin_password"
}

# 初始化仓库配置
init_registries_config() {
    local config_file="config/registries.yaml"
    local example_file="config/registries.yaml.example"
    
    if [[ -f "$config_file" ]]; then
        log_warn "配置文件 $config_file 已存在"
        read -p "是否覆盖? (y/N): " overwrite
        if [[ ! "$overwrite" =~ ^[Yy] ]]; then
            log_info "跳过仓库配置初始化"
            return
        fi
    fi
    
    # 检查是否有生成脚本
    if [[ -f "generate_registries_config.py" ]]; then
        log_info "使用配置生成脚本初始化仓库配置..."
        
        # 使用Python脚本生成配置
        if [[ -f "$config_file" ]]; then
            $PYTHON_CMD generate_registries_config.py --backup -o "$config_file"
        else
            $PYTHON_CMD generate_registries_config.py -o "$config_file"
        fi
        
        log_info "已生成默认仓库配置"
        log_warn "请编辑 $config_file 文件，修改为您的实际仓库信息"
        
    elif [[ -f "$example_file" ]]; then
        log_info "从示例文件初始化仓库配置..."
        
        # 复制示例文件
        cp "$example_file" "$config_file"
        
        echo ""
        log_info "配置主要仓库信息"
        read -p "是否配置Harbor私服? (y/N): " config_harbor
        
        if [[ "$config_harbor" =~ ^[Yy] ]]; then
            read -p "Harbor地址 (例如: harbor.example.com): " harbor_url
            read -p "Harbor用户名: " harbor_username
            read -s -p "Harbor密码: " harbor_password
            echo ""
            read -p "Harbor项目名 (默认: library): " harbor_project
            harbor_project=${harbor_project:-library}
            
            if [[ -n "$harbor_url" && -n "$harbor_username" && -n "$harbor_password" ]]; then
                # 替换Harbor配置
                sed -i "s|url: harbor.example.com|url: $harbor_url|" "$config_file"
                sed -i "s|username: admin|username: $harbor_username|" "$config_file"
                sed -i "s|password: your-password|password: $harbor_password|" "$config_file"
                sed -i "s|project: library|project: $harbor_project|" "$config_file"
                
                log_info "Harbor配置完成"
            fi
        fi
        
        echo ""
        read -p "是否配置阿里云ACR? (y/N): " config_acr
        
        if [[ "$config_acr" =~ ^[Yy] ]]; then
            echo "阿里云ACR地域选择:"
            echo "1. 华东1（杭州）: registry.cn-hangzhou.aliyuncs.com"
            echo "2. 华北2（北京）: registry.cn-beijing.aliyuncs.com"
            echo "3. 华东2（上海）: registry.cn-shanghai.aliyuncs.com"
            echo "4. 自定义地址"
            read -p "选择地域 (1-4): " acr_region
            
            case $acr_region in
                1) acr_url="registry.cn-hangzhou.aliyuncs.com" ;;
                2) acr_url="registry.cn-beijing.aliyuncs.com" ;;
                3) acr_url="registry.cn-shanghai.aliyuncs.com" ;;
                4) read -p "请输入ACR地址: " acr_url ;;
                *) acr_url="registry.cn-hangzhou.aliyuncs.com" ;;
            esac
            
            read -p "ACR用户名: " acr_username
            read -s -p "ACR密码: " acr_password
            echo ""
            read -p "ACR命名空间: " acr_namespace
            
            if [[ -n "$acr_url" && -n "$acr_username" && -n "$acr_password" && -n "$acr_namespace" ]]; then
                # 替换ACR配置
                sed -i "s|registry.cn-hangzhou.aliyuncs.com|$acr_url|" "$config_file"
                sed -i "0,/username: your-username/{s|username: your-username|username: $acr_username|}" "$config_file"
                sed -i "0,/password: your-password/{s|password: your-password|password: $acr_password|}" "$config_file"
                sed -i "0,/namespace: your-namespace/{s|namespace: your-namespace|namespace: $acr_namespace|}" "$config_file"
                
                log_info "阿里云ACR配置完成"
            fi
        fi
        
        log_info "仓库配置初始化完成: $config_file"
        log_warn "如需配置其他仓库，请手动编辑配置文件"
        
    else
        log_error "示例文件 $example_file 不存在，且未找到生成脚本"
        log_info "请手动创建配置文件或使用 generate_registries_config.py 脚本"
        return 1
    fi
}

# 初始化Kubernetes配置
init_k8s_config() {
    log_info "初始化Kubernetes配置..."
    
    if [[ ! -f "config/users.yaml" ]]; then
        log_error "请先初始化用户配置"
        return 1
    fi
    
    # 生成base64编码的用户配置
    users_config_b64=$(cat config/users.yaml | base64 -w 0)
    
    # 更新secret.yaml
    sed -i "s/<BASE64_ENCODED_USERS_CONFIG>/$users_config_b64/" k8s/secret.yaml
    
    log_info "Kubernetes Secret已更新"
    log_warn "请手动配置 k8s/secret.yaml 中的 Docker 配置"
}

# 显示帮助信息
show_help() {
    cat << EOF
Docker镜像同步工具 - 配置初始化脚本

用法: $0 [选项]

选项:
  --users-only       仅初始化用户配置
  --registries-only  仅初始化仓库配置
  --k8s-only         仅初始化Kubernetes配置
  --all              初始化所有配置 (默认)
  --help             显示此帮助信息

示例:
  $0                 # 初始化所有配置
  $0 --users-only    # 仅初始化用户配置
  $0 --k8s-only      # 仅初始化Kubernetes配置

EOF
}

# 主函数
main() {
    local init_users=false
    local init_registries=false
    local init_k8s=false
    local init_all=true
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --users-only)
                init_users=true
                init_all=false
                shift
                ;;
            --registries-only)
                init_registries=true
                init_all=false
                shift
                ;;
            --k8s-only)
                init_k8s=true
                init_all=false
                shift
                ;;
            --all)
                init_all=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 检查Python环境
    check_python
    
    # 确保配置目录存在
    mkdir -p config
    
    log_info "=== Docker镜像同步工具配置初始化 ==="
    echo ""
    
    # 执行初始化
    if [[ "$init_all" == "true" ]]; then
        init_users_config
        echo ""
        init_registries_config
        echo ""
        read -p "是否初始化Kubernetes配置? (y/N): " init_k8s_choice
        if [[ "$init_k8s_choice" =~ ^[Yy] ]]; then
            init_k8s_config
        fi
    else
        if [[ "$init_users" == "true" ]]; then
            init_users_config
        fi
        if [[ "$init_registries" == "true" ]]; then
            init_registries_config
        fi
        if [[ "$init_k8s" == "true" ]]; then
            init_k8s_config
        fi
    fi
    
    echo ""
    log_info "=== 配置初始化完成 ==="
    log_info "现在可以启动应用了:"
    log_info "  python app.py"
    log_info "或使用Docker:"
    log_info "  docker-compose up -d"
}

# 执行主函数
main "$@" 