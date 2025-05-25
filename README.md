# Docker镜像同步工具

> ⚠️ **重要安全说明**：本项目已进行完整的数据脱敏处理，所有敏感信息已被移除。首次使用前请参考 [SECURITY.md](SECURITY.md) 文档进行配置初始化。

一个功能强大的Docker镜像同步工具，支持将镜像从公共仓库同步到私有仓库，提供现代化的Web界面和完整的管理功能。

## 🌟 功能特性

### 核心功能
- 🐳 **多私服支持**：Harbor、阿里云ACR、Nexus、华为云SWR、腾讯云TCR等
- 🚀 **高效同步**：基于Skopeo工具，支持增量同步和并发处理
- 📊 **实时监控**：WebSocket实时进度显示，详细日志记录
- 🎯 **灵活配置**：多种替换级别，自定义目标项目/命名空间
- 💻 **现代界面**：纯平面设计，响应式布局，支持暗色主题

### 管理功能
- 👥 **用户管理**：完整的用户认证和权限控制系统
- 🏢 **仓库管理**：私服配置管理，支持多种仓库类型
- 📝 **批量操作**：批量镜像同步，脚本生成和下载
- 🔍 **搜索过滤**：强大的搜索和过滤功能
- 📈 **统计分析**：同步统计和性能分析

## 🛠️ 系统要求

### 必需软件
- Python 3.9+
- Skopeo 1.9+
- Docker (可选，用于容器化部署)
- Kubernetes (可选，用于K8s部署)

### 安装Skopeo

#### CentOS/RHEL 7/8
```bash
# 安装EPEL仓库
sudo yum install -y epel-release

# 安装Skopeo
sudo yum install -y skopeo

# 验证安装
skopeo --version
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y skopeo

# 验证安装
skopeo --version
```

#### 使用项目提供的安装脚本
```bash
# 自动安装最新版本Skopeo
chmod +x install_skopeo.sh
./install_skopeo.sh
```

## 🚀 快速开始

### 前置准备：配置初始化

**重要：本项目出于安全考虑已进行数据脱敏，首次使用需要初始化配置文件。**

#### 方法一：使用配置初始化脚本（推荐）
```bash
# 初始化所有配置（推荐）
./scripts/init-config.sh

# 或分别初始化
./scripts/init-config.sh --users-only
./scripts/init-config.sh --registries-only
```

#### 方法二：手动配置
```bash
# 复制示例配置文件
cp config/users.yaml.example config/users.yaml
cp config/registries.yaml.example config/registries.yaml

# 编辑配置文件
vim config/users.yaml      # 配置用户认证
vim config/registries.yaml # 配置私服信息
```

### 方式一：直接运行

1. **克隆项目**
```bash
git clone <repository-url>
cd docker-image-sync
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **初始化配置**
```bash
# 使用配置初始化脚本
./scripts/init-config.sh
```

4. **启动服务**
```bash
python app.py
```

5. **访问界面**
打开浏览器访问：http://localhost:5000

### 方式二：Docker部署

1. **初始化配置**
```bash
# 确保配置文件存在
./scripts/init-config.sh
```

2. **使用Docker Compose（推荐）**
```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

3. **单独使用Docker**
```bash
# 构建镜像
docker build -t docker-image-sync:latest .

# 运行容器
docker run -d \
  --name docker-sync \
  -p 5000:5000 \
  -v $(pwd)/config:/app/config:ro \
  -v docker_sync_logs:/app/logs \
  -v docker_sync_downloads:/app/downloads \
  docker-image-sync:latest
```

### 方式三：Kubernetes部署

1. **初始化配置**
```bash
# 生成Kubernetes配置
./scripts/init-config.sh --k8s-only
```

2. **应用所有配置**
```bash
# 创建命名空间和所有资源
kubectl apply -f k8s/

# 或使用Kustomize
kubectl apply -k k8s/
```

3. **检查部署状态**
```bash
# 查看Pod状态
kubectl get pods -n docker-sync

# 查看服务状态
kubectl get svc -n docker-sync

# 查看日志
kubectl logs -f deployment/docker-sync -n docker-sync
```

4. **访问服务**
```bash
# 通过NodePort访问
curl http://<node-ip>:30500

# 通过Ingress访问（需要配置域名）
curl https://docker-sync.yourdomain.com
```

## 📖 使用指南

### 基本同步操作

1. **登录系统**
   - 默认用户名：`admin`
   - 默认密码：`admin123` ⚠️ **请立即修改默认密码**

2. **配置私服**
   - 进入"仓库管理"页面
   - 添加或编辑私服配置
   - 测试连接确保配置正确

3. **同步镜像**
   - 在主页面输入镜像列表（每行一个）
   - 选择目标私服
   - 选择替换级别
   - 可选：指定自定义目标项目/命名空间
   - 点击"开始同步"

### 替换级别说明

| 级别 | 说明 | 示例 |
|------|------|------|
| 跳过 | 保持原始路径 | `a/b/c/img` → `ns/a/b/c/img` |
| 替换所有级 | 只保留镜像名 | `a/b/c/img` → `ns/img` |
| 替换1级 | 去除第1级路径 | `a/b/c/img` → `ns/b/c/img` |
| 替换2级 | 去除前2级路径 | `a/b/c/img` → `ns/c/img` |
| 替换3级 | 去除前3级路径 | `a/b/c/img` → `ns/img` |

### 批量操作

1. **生成批量脚本**
   - 输入镜像列表
   - 选择配置
   - 点击"生成批量脚本"
   - 下载生成的shell脚本

2. **执行批量脚本**
```bash
chmod +x downloaded_script.sh
./downloaded_script.sh
```

### 管理功能

#### 用户管理
- 添加/删除用户
- 修改用户权限
- 重置密码
- 查看登录历史

#### 仓库管理
- 添加私服配置
- 测试连接
- 编辑配置
- 删除仓库

## ⚙️ 配置详解

### 📋 配置快速参考

| 配置类型 | 文件位置 | 主要用途 | 关键配置项 |
|----------|----------|----------|------------|
| **用户配置** | `config/users.yaml` | 用户认证和权限 | `username`, `password_hash`, `role` |
| **仓库配置** | `config/registries.yaml` | 私服连接信息 | `url`, `username`, `password`, `namespace` |
| **镜像过滤** | `config/registries.yaml` | 控制同步范围 | `include_patterns`, `exclude_patterns` |
| **同步设置** | `config/registries.yaml` | 同步行为控制 | `batch_size`, `retry_count`, `timeout` |
| **日志配置** | `config/registries.yaml` | 日志输出控制 | `level`, `max_size`, `backup_count` |

### 🔑 重要配置项说明

#### 镜像过滤器优先级
1. **exclude_patterns** (排除) - 最高优先级
2. **include_patterns** (包含) - 次优先级  
3. **默认行为** - 如果都没匹配，通常允许同步

#### 私服类型支持
| 私服类型 | URL示例 | 特殊配置 |
|----------|---------|----------|
| **Docker Hub** | `docker.io` | 无需认证（公共镜像） |
| **Harbor** | `harbor.example.com` | 需要 `project` 配置 |
| **阿里云ACR** | `registry.cn-hangzhou.aliyuncs.com` | 需要 `namespace` 配置 |
| **Nexus** | `nexus.example.com:8082` | 需要 `repository` 配置 |
| **华为云SWR** | `swr.cn-north-4.myhuaweicloud.com` | 需要 `namespace` 配置 |
| **腾讯云TCR** | `your-instance.tencentcloudcr.com` | 需要 `namespace` 配置 |

### 配置文件结构

```
config/
├── users.yaml.example       # 用户配置示例
├── registries.yaml.example  # 仓库配置示例
├── users.yaml              # 实际用户配置（需要创建）
└── registries.yaml         # 实际仓库配置（需要创建）
```

### 用户配置文件

`config/users.yaml` 示例配置：

```yaml
users:
  admin:
    username: admin
    password_hash: "$2b$12$..."  # bcrypt哈希
    display_name: "管理员"
    role: "admin"
    email: "admin@example.com"
    active: true

session:
  secret_key: "your-32-byte-secret-key"  # 32字节随机密钥
  session_timeout: 3600
  remember_me_duration: 604800

security:
  max_login_attempts: 5
  lockout_duration: 300
  password_min_length: 6
```

### 仓库配置文件

`config/registries.yaml` 完整配置说明：

#### 基本配置结构

```yaml
registries:
  # 源仓库配置（通常是公共仓库）
  source:
    url: "docker.io"
    username: ""           # 可选：私有仓库用户名
    password: ""           # 可选：私有仓库密码
    namespace: "library"   # 默认命名空间
    
  # 目标仓库配置（您的私有仓库）
  target:
    url: "harbor.example.com"
    username: "admin"
    password: "Harbor12345"
    namespace: "library"
```

#### 同步配置

```yaml
sync_config:
  batch_size: 5              # 批量处理大小
  retry_count: 3             # 失败重试次数
  timeout: 300               # 超时时间（秒）
  parallel_downloads: 2      # 并行下载数量
```

#### 镜像过滤器配置

```yaml
image_filters:
  # 包含模式：只同步匹配的镜像
  include_patterns:
    - "nginx:*"              # 所有nginx镜像
    - "redis:*"              # 所有redis镜像
    - "mysql:*"              # 所有mysql镜像
    - "node:18.*"            # node 18.x版本
    - "python:3.9*"          # python 3.9版本
    
  # 排除模式：不同步匹配的镜像
  exclude_patterns:
    - "*:debug"              # 排除debug标签
    - "*:test"               # 排除test标签
    - "*:experimental"       # 排除实验版本
    - "*:nightly"            # 排除每日构建
    - "*:rc*"                # 排除候选版本
```

#### 日志配置

```yaml
logging:
  level: "INFO"              # 日志级别：DEBUG, INFO, WARNING, ERROR
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "/app/logs/sync.log" # 日志文件路径
  max_size: "100MB"          # 单个日志文件最大大小
  backup_count: 5            # 保留的日志文件数量
```

#### 支持的私服类型配置

##### 1. Harbor私服
```yaml
harbor_example:
  name: "Harbor私服"
  type: "harbor"
  url: "harbor.example.com"
  username: "admin"
  password: "Harbor12345"
  project: "library"         # Harbor项目名
  description: "Harbor私有仓库"
```

##### 2. 阿里云ACR
```yaml
aliyun_acr_example:
  name: "阿里云ACR"
  type: "acr"
  url: "registry.cn-hangzhou.aliyuncs.com"
  username: "your-username"
  password: "your-password"
  namespace: "your-namespace"  # ACR命名空间
  description: "阿里云容器镜像服务"
```

##### 3. Nexus Repository
```yaml
nexus_example:
  name: "Nexus私服"
  type: "nexus"
  url: "nexus.example.com:8082"
  username: "nexus-user"
  password: "nexus-password"
  repository: "docker-hosted"  # Nexus仓库名
  description: "Nexus Repository Manager"
```

##### 4. 华为云SWR
```yaml
huawei_swr_example:
  name: "华为云SWR"
  type: "swr"
  url: "swr.cn-north-4.myhuaweicloud.com"
  username: "your-username"
  password: "your-password"
  namespace: "your-namespace"
  description: "华为云容器镜像服务"
```

##### 5. 腾讯云TCR
```yaml
tencent_tcr_example:
  name: "腾讯云TCR"
  type: "tcr"
  url: "your-instance.tencentcloudcr.com"
  username: "your-username"
  password: "your-password"
  namespace: "your-namespace"
  description: "腾讯云容器镜像服务"
```

#### 镜像过滤器详细说明

| 过滤模式 | 含义 | 示例匹配 |
|----------|------|----------|
| `nginx:*` | nginx镜像的所有标签 | `nginx:latest`, `nginx:1.21`, `nginx:alpine` |
| `*:debug` | 任何镜像的debug标签 | `nginx:debug`, `redis:debug`, `app:debug` |
| `redis:6.*` | redis 6.x版本 | `redis:6.0`, `redis:6.2.7` |
| `mysql:8*` | mysql 8开头的版本 | `mysql:8.0`, `mysql:8.0.33` |
| `node:18.*` | node 18.x版本 | `node:18.0`, `node:18.16.0` |
| `python:3.9*` | python 3.9版本 | `python:3.9`, `python:3.9.16` |

#### 常用配置示例

##### 生产环境配置
```yaml
image_filters:
  include_patterns:
    - "nginx:stable"
    - "redis:alpine"
    - "mysql:8.0.*"
    - "node:18-alpine"
  exclude_patterns:
    - "*:debug"
    - "*:test"
    - "*:dev"
    - "*:experimental"
    - "*:nightly"
```

##### 开发环境配置
```yaml
image_filters:
  include_patterns:
    - "nginx:*"
    - "redis:*"
    - "mysql:*"
    - "node:*"
    - "python:*"
  exclude_patterns:
    - "*:windows*"          # 排除Windows镜像
    - "*:windowsservercore" # 排除Windows Server Core
```

##### 特定项目配置
```yaml
image_filters:
  include_patterns:
    - "mycompany/*:*"       # 公司内部镜像
    - "nginx:1.21.*"        # 特定nginx版本
    - "redis:6.2.*"         # 特定redis版本
  exclude_patterns:
    - "*:snapshot"          # 排除快照版本
    - "*:SNAPSHOT"          # 排除Maven风格快照
```

#### 配置验证

配置文件修改后，可以通过以下方式验证：

1. **语法检查**
```bash
# 检查YAML语法
python -c "import yaml; yaml.safe_load(open('config/registries.yaml'))"
```

2. **配置测试**
```bash
# 启动应用并检查日志
python app.py
# 查看是否有配置错误信息
```

3. **连接测试**
在管理界面中使用"测试连接"功能验证仓库配置是否正确。

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `FLASK_ENV` | `production` | Flask运行环境 |
| `PYTHONUNBUFFERED` | `1` | Python输出缓冲 |
| `SKOPEO_DISABLE_SSL_VERIFY` | `false` | 是否禁用SSL验证 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## 🐳 容器化部署

### Docker Compose配置

完整的 `docker-compose.yml` 包含以下服务：

- **docker-sync**: 主应用服务
- **redis**: 缓存服务（可选）
- **nginx**: 反向代理（可选）

#### 启动完整服务栈
```bash
# 启动主服务
docker-compose up -d

# 启动包含Redis的服务
docker-compose --profile with-redis up -d

# 启动包含Nginx的服务
docker-compose --profile with-nginx up -d

# 启动所有服务
docker-compose --profile with-redis --profile with-nginx up -d
```

#### 服务配置

```yaml
# 资源限制
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '1.0'
    reservations:
      memory: 512M
      cpus: '0.5'

# 健康检查
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s

# 日志配置
logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "3"
```

### Kubernetes部署

#### 部署架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Ingress       │    │   Service       │    │   Deployment    │
│                 │────│                 │────│                 │
│ SSL Termination │    │ Load Balancing  │    │ App Container   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   ConfigMap     │    │   Secret        │
                       │                 │────│                 │
                       │ App Config      │    │ Sensitive Data  │
                       └─────────────────┘    └─────────────────┘
                                                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   PVC (Logs)    │    │   PVC (Downloads)│
                       │                 │────│                 │
                       │ Persistent      │    │ Persistent      │
                       │ Storage         │    │ Storage         │
                       └─────────────────┘    └─────────────────┘
```

#### 部署步骤

1. **准备配置**
```bash
# 编辑Secret中的用户配置
kubectl edit secret docker-sync-secret -n docker-sync

# 编辑ConfigMap中的仓库配置
kubectl edit configmap docker-sync-registries -n docker-sync

# 更新Ingress域名
kubectl edit ingress docker-sync-ingress -n docker-sync
```

2. **部署应用**
```bash
# 创建命名空间
kubectl apply -f k8s/namespace.yaml

# 部署配置
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# 部署存储
kubectl apply -f k8s/pvc.yaml

# 部署RBAC
kubectl apply -f k8s/rbac.yaml

# 部署应用
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

3. **验证部署**
```bash
# 检查所有资源
kubectl get all -n docker-sync

# 查看Pod日志
kubectl logs -f deployment/docker-sync -n docker-sync

# 检查服务端点
kubectl get endpoints -n docker-sync

# 测试服务连通性
kubectl port-forward svc/docker-sync-service 8080:80 -n docker-sync
```

#### 扩展配置

**自动扩缩容（HPA）**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: docker-sync-hpa
  namespace: docker-sync
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: docker-sync
  minReplicas: 1
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**网络策略**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: docker-sync-netpol
  namespace: docker-sync
spec:
  podSelector:
    matchLabels:
      app: docker-sync
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 5000
```

## 🔧 故障排除

### 常见问题

#### 1. 配置文件问题
```bash
# 检查配置文件语法
python -c "import yaml; yaml.safe_load(open('config/registries.yaml'))"
python -c "import yaml; yaml.safe_load(open('config/users.yaml'))"

# 验证配置文件权限
ls -la config/
# 应该显示：
# -rw------- 1 user user xxx config/users.yaml
# -rw------- 1 user user xxx config/registries.yaml

# 检查配置文件是否存在
if [[ ! -f "config/users.yaml" ]]; then
    echo "用户配置文件不存在，请运行: ./scripts/init-config.sh --users-only"
fi

if [[ ! -f "config/registries.yaml" ]]; then
    echo "仓库配置文件不存在，请运行: ./scripts/init-config.sh --registries-only"
fi
```

#### 2. 仓库连接问题
```bash
# 测试仓库连接
curl -I https://your-registry.com/v2/

# 测试Harbor仓库
curl -u "username:password" https://harbor.example.com/v2/_catalog

# 测试阿里云ACR
curl -u "username:password" https://registry.cn-hangzhou.aliyuncs.com/v2/

# 检查skopeo连接
skopeo inspect docker://your-registry.com/library/nginx:latest \
  --creds username:password
```

#### 3. 镜像过滤器问题
```bash
# 调试镜像过滤规则
# 在日志中查看过滤结果
tail -f logs/sync.log | grep -E "(include|exclude|filter)"

# 测试过滤模式匹配
python -c "
import fnmatch
image = 'nginx:1.21-alpine'
patterns = ['nginx:*', 'redis:*']
for pattern in patterns:
    if fnmatch.fnmatch(image, pattern):
        print(f'✅ {image} 匹配模式 {pattern}')
    else:
        print(f'❌ {image} 不匹配模式 {pattern}')
"
```

#### 4. 认证问题
```bash
# 检查密码哈希是否正确
python -c "
import bcrypt
password = 'your-password'
hash_from_config = '\$2b\$12\$your-hash-here'
result = bcrypt.checkpw(password.encode('utf-8'), hash_from_config.encode('utf-8'))
print('密码验证:', '✅ 正确' if result else '❌ 错误')
"

# 重新生成密码哈希
python -c "
import bcrypt
password = 'your-new-password'
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print('新密码哈希:', hashed.decode('utf-8'))
"
```

#### 5. Skopeo命令失败
```bash
# 检查Skopeo版本
skopeo --version

# 测试连接
skopeo inspect docker://docker.io/library/nginx:latest

# 检查认证
skopeo login your-registry.com
```

#### 6. 权限问题
```bash
# 检查文件权限
ls -la config/
ls -la logs/

# 修复权限
chmod 600 config/users.yaml
chmod 600 config/registries.yaml
chmod 755 logs/
chmod 755 downloads/
```

#### 7. 容器启动失败
```bash
# 查看容器日志
docker logs docker-image-sync

# 检查容器状态
docker ps -a

# 进入容器调试
docker exec -it docker-image-sync /bin/bash
```

#### 8. Kubernetes部署问题
```bash
# 查看Pod事件
kubectl describe pod <pod-name> -n docker-sync

# 查看资源状态
kubectl get events -n docker-sync --sort-by='.lastTimestamp'

# 检查存储
kubectl get pvc -n docker-sync
kubectl describe pvc docker-sync-logs -n docker-sync
```

### 配置问题解决方案

#### 🔧 常见配置错误

| 错误现象 | 可能原因 | 解决方法 |
|----------|----------|----------|
| 登录失败 | 密码哈希错误 | 重新生成密码哈希 |
| 仓库连接失败 | URL或认证信息错误 | 检查仓库配置 |
| 镜像同步失败 | 过滤规则过于严格 | 调整过滤模式 |
| 配置文件不生效 | YAML语法错误 | 验证YAML格式 |
| 权限被拒绝 | 文件权限不正确 | 修复文件权限 |

#### 🚨 错误日志关键词

| 关键词 | 含义 | 检查项目 |
|--------|------|----------|
| `YAML syntax error` | YAML格式错误 | 检查配置文件格式 |
| `Authentication failed` | 认证失败 | 检查用户名密码 |
| `Permission denied` | 权限不足 | 检查文件和用户权限 |
| `Connection refused` | 连接被拒绝 | 检查网络和防火墙 |
| `No such file` | 文件不存在 | 检查配置文件路径 |

### 日志分析

#### 应用日志位置
- 容器内：`/app/logs/`
- 主机挂载：`./logs/`
- Kubernetes：`kubectl logs`

#### 日志级别
- `DEBUG`: 详细调试信息
- `INFO`: 一般信息
- `WARNING`: 警告信息
- `ERROR`: 错误信息
- `CRITICAL`: 严重错误

#### 常见错误码
- `401`: 认证失败，检查用户名密码
- `403`: 权限不足，检查用户权限
- `404`: 镜像不存在，检查镜像名称
- `500`: 服务器内部错误，查看详细日志

## 🔒 安全建议

### 生产环境安全配置

1. **更改默认密码**
```bash
# 生成新的密码哈希
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-new-password'))"
```

2. **使用HTTPS**
```yaml
# nginx.conf
server {
    listen 443 ssl;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://docker-sync:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

3. **网络隔离**
```yaml
# docker-compose.yml
networks:
  docker-sync-network:
    driver: bridge
    internal: true  # 内部网络
```

4. **资源限制**
```yaml
# 限制容器资源使用
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '1.0'
```

5. **定期备份**
```bash
# 备份配置文件
tar -czf backup-$(date +%Y%m%d).tar.gz config/ logs/

# 备份数据库（如果使用）
kubectl exec -n docker-sync deployment/docker-sync -- pg_dump > backup.sql
```

## 📊 监控和指标

### Prometheus监控

```yaml
# prometheus配置
scrape_configs:
  - job_name: 'docker-sync'
    static_configs:
      - targets: ['docker-sync:5000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### 关键指标

- `sync_total`: 总同步次数
- `sync_success`: 成功同步次数
- `sync_failed`: 失败同步次数
- `sync_duration`: 同步耗时
- `active_connections`: 活跃连接数

### Grafana仪表板

导入提供的Grafana仪表板模板，监控：
- 同步成功率
- 平均同步时间
- 错误率趋势
- 系统资源使用

## 🤝 贡献指南

### 开发环境设置

1. **Fork项目**
2. **创建开发分支**
```bash
git checkout -b feature/your-feature
```

3. **安装开发依赖**
```bash
pip install -r requirements-dev.txt
```

4. **运行测试**
```bash
python -m pytest tests/
```

5. **提交更改**
```bash
git commit -m "Add your feature"
git push origin feature/your-feature
```

6. **创建Pull Request**

### 代码规范

- 遵循PEP 8代码风格
- 添加适当的注释和文档
- 编写单元测试
- 更新相关文档

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 支持

- 📧 邮箱：support@example.com
- 💬 讨论：[GitHub Discussions](https://github.com/your-repo/discussions)
- 🐛 问题报告：[GitHub Issues](https://github.com/your-repo/issues)
- 📖 文档：[项目Wiki](https://github.com/your-repo/wiki)

## 🎯 路线图

### v1.1.0 (计划中)
- [ ] 支持镜像签名验证
- [ ] 添加镜像漏洞扫描
- [ ] 支持多集群部署
- [ ] 增强监控和告警

### v1.2.0 (计划中)
- [ ] 支持镜像缓存策略
- [ ] 添加API接口
- [ ] 支持Webhook通知
- [ ] 增加镜像生命周期管理

---

**感谢使用Docker镜像同步工具！** 🚀 