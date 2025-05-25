#!/bin/bash

# Docker镜像同步工具一键部署脚本
# 支持Docker、Docker Compose和Kubernetes部署

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

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 命令未找到，请先安装 $1"
        return 1
    fi
    return 0
}

# 检查Docker环境
check_docker() {
    log_info "检查Docker环境..."
    if ! check_command docker; then
        log_error "请先安装Docker"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker服务未运行，请启动Docker服务"
        exit 1
    fi
    
    log_info "Docker环境检查通过"
}

# 检查Docker Compose环境
check_docker_compose() {
    log_info "检查Docker Compose环境..."
    if ! check_command docker-compose; then
        log_error "请先安装Docker Compose"
        exit 1
    fi
    log_info "Docker Compose环境检查通过"
}

# 检查Kubernetes环境
check_kubernetes() {
    log_info "检查Kubernetes环境..."
    if ! check_command kubectl; then
        log_error "请先安装kubectl"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "无法连接到Kubernetes集群"
        exit 1
    fi
    
    log_info "Kubernetes环境检查通过"
}

# 构建Docker镜像
build_docker_image() {
    log_info "构建Docker镜像..."
    docker build -t docker-image-sync:latest .
    log_info "Docker镜像构建完成"
}

# Docker部署
deploy_docker() {
    log_info "开始Docker部署..."
    check_docker
    build_docker_image
    
    # 创建必要的目录
    mkdir -p logs downloads
    
    # 停止并删除现有容器
    if docker ps -a | grep -q docker-image-sync; then
        log_info "停止现有容器..."
        docker stop docker-image-sync || true
        docker rm docker-image-sync || true
    fi
    
    # 运行新容器
    log_info "启动容器..."
    docker run -d \
        --name docker-image-sync \
        --restart unless-stopped \
        -p 5000:5000 \
        -v $(pwd)/config:/app/config:ro \
        -v $(pwd)/logs:/app/logs \
        -v $(pwd)/downloads:/app/downloads \
        -v /var/run/docker.sock:/var/run/docker.sock:ro \
        -e FLASK_ENV=production \
        -e PYTHONUNBUFFERED=1 \
        docker-image-sync:latest
    
    # 等待容器启动
    log_info "等待容器启动..."
    sleep 10
    
    # 检查容器状态
    if docker ps | grep -q docker-image-sync; then
        log_info "Docker部署成功！"
        log_info "访问地址: http://localhost:5000"
        log_info "查看日志: docker logs -f docker-image-sync"
    else
        log_error "容器启动失败"
        docker logs docker-image-sync
        exit 1
    fi
}

# Docker Compose部署
deploy_docker_compose() {
    log_info "开始Docker Compose部署..."
    check_docker
    check_docker_compose
    
    # 停止现有服务
    if [ -f docker-compose.yml ]; then
        log_info "停止现有服务..."
        docker-compose down || true
    fi
    
    # 启动服务
    log_info "启动服务..."
    docker-compose up -d --build
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 15
    
    # 检查服务状态
    if docker-compose ps | grep -q "Up"; then
        log_info "Docker Compose部署成功！"
        log_info "访问地址: http://localhost:5000"
        log_info "查看日志: docker-compose logs -f"
        log_info "停止服务: docker-compose down"
    else
        log_error "服务启动失败"
        docker-compose logs
        exit 1
    fi
}

# Kubernetes部署
deploy_kubernetes() {
    log_info "开始Kubernetes部署..."
    check_kubernetes
    
    # 检查k8s目录
    if [ ! -d "k8s" ]; then
        log_error "k8s目录不存在"
        exit 1
    fi
    
    # 构建并推送镜像（如果需要）
    if [ "$BUILD_IMAGE" = "true" ]; then
        log_info "构建并推送镜像..."
        build_docker_image
        
        # 如果有镜像仓库配置，推送镜像
        if [ -n "$IMAGE_REGISTRY" ]; then
            docker tag docker-image-sync:latest $IMAGE_REGISTRY/docker-image-sync:latest
            docker push $IMAGE_REGISTRY/docker-image-sync:latest
        fi
    fi
    
    # 应用配置
    log_info "应用Kubernetes配置..."
    
    # 创建命名空间
    kubectl apply -f k8s/namespace.yaml
    
    # 应用配置和密钥
    kubectl apply -f k8s/configmap.yaml
    kubectl apply -f k8s/secret.yaml
    
    # 应用存储
    kubectl apply -f k8s/pvc.yaml
    
    # 应用RBAC
    kubectl apply -f k8s/rbac.yaml
    
    # 应用应用程序
    kubectl apply -f k8s/deployment.yaml
    kubectl apply -f k8s/service.yaml
    
    # 应用Ingress（可选）
    if [ "$ENABLE_INGRESS" = "true" ]; then
        kubectl apply -f k8s/ingress.yaml
    fi
    
    # 等待部署完成
    log_info "等待部署完成..."
    kubectl wait --for=condition=available --timeout=300s deployment/docker-sync -n docker-sync
    
    # 检查部署状态
    log_info "检查部署状态..."
    kubectl get pods -n docker-sync
    kubectl get svc -n docker-sync
    
    # 获取访问地址
    NODE_PORT=$(kubectl get svc docker-sync-nodeport -n docker-sync -o jsonpath='{.spec.ports[0].nodePort}')
    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}')
    if [ -z "$NODE_IP" ]; then
        NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
    fi
    
    log_info "Kubernetes部署成功！"
    log_info "访问地址: http://$NODE_IP:$NODE_PORT"
    log_info "查看日志: kubectl logs -f deployment/docker-sync -n docker-sync"
    log_info "删除部署: kubectl delete -f k8s/"
}

# 清理部署
cleanup() {
    log_info "清理部署..."
    
    case $1 in
        docker)
            if docker ps -a | grep -q docker-image-sync; then
                docker stop docker-image-sync
                docker rm docker-image-sync
            fi
            if docker images | grep -q docker-image-sync; then
                docker rmi docker-image-sync:latest
            fi
            ;;
        docker-compose)
            if [ -f docker-compose.yml ]; then
                docker-compose down -v --rmi all
            fi
            ;;
        kubernetes)
            if [ -d "k8s" ]; then
                kubectl delete -f k8s/ || true
            fi
            ;;
        all)
            cleanup docker
            cleanup docker-compose
            cleanup kubernetes
            ;;
    esac
    
    log_info "清理完成"
}

# 显示帮助信息
show_help() {
    cat << EOF
Docker镜像同步工具部署脚本

用法: $0 [选项] <命令>

命令:
  docker          使用Docker部署
  docker-compose  使用Docker Compose部署
  kubernetes      使用Kubernetes部署
  cleanup         清理部署
  help            显示帮助信息

选项:
  --build-image           构建Docker镜像
  --image-registry=URL    镜像仓库地址
  --enable-ingress        启用Kubernetes Ingress
  --profile=PROFILE       Docker Compose profile

示例:
  $0 docker                                    # Docker部署
  $0 docker-compose --profile=with-redis       # Docker Compose部署（包含Redis）
  $0 kubernetes --build-image --enable-ingress # Kubernetes部署
  $0 cleanup all                               # 清理所有部署

环境变量:
  BUILD_IMAGE=true        构建镜像
  IMAGE_REGISTRY=url      镜像仓库
  ENABLE_INGRESS=true     启用Ingress
  COMPOSE_PROFILE=name    Compose profile

EOF
}

# 主函数
main() {
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --build-image)
                BUILD_IMAGE=true
                shift
                ;;
            --image-registry=*)
                IMAGE_REGISTRY="${1#*=}"
                shift
                ;;
            --enable-ingress)
                ENABLE_INGRESS=true
                shift
                ;;
            --profile=*)
                COMPOSE_PROFILE="${1#*=}"
                shift
                ;;
            docker)
                DEPLOY_TYPE="docker"
                shift
                ;;
            docker-compose)
                DEPLOY_TYPE="docker-compose"
                shift
                ;;
            kubernetes)
                DEPLOY_TYPE="kubernetes"
                shift
                ;;
            cleanup)
                CLEANUP_TYPE="$2"
                shift 2
                ;;
            help|--help|-h)
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
    
    # 执行命令
    if [ -n "$CLEANUP_TYPE" ]; then
        cleanup "$CLEANUP_TYPE"
    elif [ -n "$DEPLOY_TYPE" ]; then
        case $DEPLOY_TYPE in
            docker)
                deploy_docker
                ;;
            docker-compose)
                if [ -n "$COMPOSE_PROFILE" ]; then
                    export COMPOSE_PROFILES="$COMPOSE_PROFILE"
                fi
                deploy_docker_compose
                ;;
            kubernetes)
                deploy_kubernetes
                ;;
        esac
    else
        log_error "请指定部署类型或命令"
        show_help
        exit 1
    fi
}

# 检查是否为root用户（某些操作可能需要）
if [ "$EUID" -eq 0 ]; then
    log_warn "检测到以root用户运行，请确保这是必要的"
fi

# 执行主函数
main "$@" 