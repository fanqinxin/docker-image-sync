# 本地文件导出功能说明

## 功能概述

Docker镜像同步工具现已支持将镜像导出为tar包文件，方便在离线环境中使用`docker load`命令导入镜像。

## 主要特性

### 1. 镜像导出
- 使用`skopeo`工具将Docker镜像导出为tar包格式
- 支持从任何可访问的镜像仓库导出镜像
- 自动生成带时间戳的安全文件名
- 支持私有仓库认证和网络代理

### 2. 文件管理
- 实时显示导出文件列表
- 显示文件大小、创建时间等信息
- 提供下载链接和使用说明
- 支持文件删除和批量清理

### 3. 使用便利性
- 一键复制`docker load`命令
- 自动文件清理功能
- 完整的操作日志记录

## 使用方法

### 1. 选择本地文件导出
在同步配置中，选择"本地文件"作为目标私服：
```
目标私服: 本地文件 (local_file) - downloads
```

### 2. 配置镜像列表
输入要导出的镜像，例如：
```
nginx:latest
redis:6.2-alpine
mysql:8.0
ubuntu:20.04
```

### 3. 可选配置
- **私有镜像认证**: 如果源镜像需要认证，勾选相应选项并填写认证信息
- **网络代理**: 如果需要通过代理访问镜像仓库，配置代理设置

### 4. 开始导出
点击"开始同步"按钮，系统将：
1. 逐个处理镜像列表
2. 使用skopeo导出为tar包
3. 保存到downloads目录
4. 提供下载链接

## 文件管理功能

### 文件列表
- 显示所有导出的tar文件
- 文件名格式：`镜像名_标签_时间戳.tar`
- 显示文件大小（MB）和创建时间

### 操作功能
1. **下载**: 直接下载tar包文件
2. **复制命令**: 一键复制`docker load < filename.tar`命令
3. **删除**: 删除不需要的文件
4. **清理**: 批量清理旧文件（按天数和数量）

## 技术实现

### 导出命令
```bash
# 新版本 - 保留镜像名称和标签
skopeo copy --src-tls-verify=false docker://镜像名 docker-archive:文件路径:镜像名:标签

# 旧版本 - 基本导出（可能丢失标签）
skopeo copy --src-tls-verify=false docker://镜像名 docker-archive:文件路径
```

### 文件格式
- 格式：Docker Archive (tar)
- 兼容：`docker load`命令
- 压缩：自动压缩
- **新增**：自动生成标记脚本解决`<none>`标签问题

### 安全特性
- 文件路径安全检查
- 用户认证保护
- 操作日志记录

## 解决&lt;none&gt;标签问题

### 问题描述
使用`docker load`导入镜像后，可能出现：
```
REPOSITORY    TAG       IMAGE ID       CREATED      SIZE
<none>        <none>    1fbec694a894   11 days ago  438MB
```

### 自动解决方案
系统现在会自动生成标记脚本来解决这个问题：

1. **自动生成脚本**：每次导出镜像时，系统会生成对应的标记脚本
2. **一键修复**：使用脚本可以自动导入镜像并设置正确的标签
3. **智能识别**：脚本会自动识别镜像ID并应用正确的标签

### 使用标记脚本
```bash
# 1. 下载tar包和标记脚本
wget http://server/downloads/nginx_latest_20250524_161349.tar
wget http://server/downloads/tag_nginx_latest_20250524_161349.sh

# 2. 执行标记脚本（推荐方式）
bash tag_nginx_latest_20250524_161349.sh

# 脚本会自动：
# - 导入镜像文件
# - 检测镜像ID
# - 应用正确的标签
# - 验证结果
```

### 手动修复方法
如果没有标记脚本，可以手动修复：

```bash
# 1. 导入镜像
docker load < nginx_latest_20250524_161349.tar

# 2. 查看导入的镜像
docker images

# 3. 为<none>镜像添加标签
docker tag <IMAGE_ID> nginx:latest

# 4. 验证结果
docker images | grep nginx
```

## 使用场景

### 1. 离线环境部署
```bash
# 在有网络的环境导出
选择"本地文件" -> 导出镜像 -> 下载tar包

# 在离线环境导入
docker load < nginx_latest_20250524_161349.tar
```

### 2. 镜像备份
- 定期导出重要镜像
- 创建镜像快照
- 版本归档管理

### 3. 跨环境迁移
- 开发环境 -> 测试环境
- 测试环境 -> 生产环境
- 云环境 -> 本地环境

## 配置示例

### registries.yaml配置
```yaml
registries:
  - name: 本地文件
    type: local_file
    url: downloads
    username: ""
    password: ""
    description: 导出镜像为tar包文件，可用于docker load导入
```

### 导出示例
```json
{
  "images": ["nginx:latest", "redis:alpine"],
  "target_registry": "本地文件",
  "replace_level": "1",
  "source_auth": {
    "username": "your-username",
    "password": "your-password"
  },
  "proxy_config": {
    "http_proxy": "http://proxy.company.com:8080",
    "https_proxy": "http://proxy.company.com:8080"
  }
}
```

## 注意事项

1. **网络要求**: 需要能够访问源镜像仓库
2. **存储空间**: 确保有足够的磁盘空间存储tar包
3. **权限要求**: 需要对downloads目录的读写权限
4. **skopeo版本**: 需要安装skopeo工具（当前支持0.1.40版本）

## 故障排除

### 常见问题

1. **网络超时**
   - 检查网络连接
   - 配置代理设置
   - 使用国内镜像源

2. **认证失败**
   - 验证用户名密码
   - 检查Token有效性
   - 确认仓库访问权限

3. **文件大小为0**
   - 检查skopeo命令执行结果
   - 查看同步日志详情
   - 验证源镜像是否存在

### 日志查看
系统提供详细的操作日志，包括：
- 命令执行过程
- 错误信息详情
- 网络连接状态
- 文件生成结果

## API接口

### 文件列表
```
GET /api/files
```

### 文件下载
```
GET /downloads/<filename>
```

### 文件删除
```
DELETE /api/files/<filename>
```

### 文件清理
```
POST /api/files/cleanup
{
  "max_age_days": 7,
  "max_files": 50
}
```

## 总结

本地文件导出功能为Docker镜像同步工具增加了重要的离线部署能力，通过简单的Web界面操作，用户可以轻松导出镜像并在任何环境中使用。该功能特别适合：

- 离线环境部署
- 镜像备份归档
- 跨网络环境迁移
- 开发测试流程

结合现有的私服同步功能，形成了完整的镜像管理解决方案。 