# 认证功能使用说明

## 概述

Docker镜像同步工具现在已经集成了完整的用户认证系统，确保只有授权用户才能执行镜像同步操作。

## 功能特性

### 🔐 安全认证
- **用户名/密码登录**：支持传统的用户名密码认证
- **密码加密存储**：使用bcrypt算法安全存储密码哈希
- **会话管理**：支持会话超时和"记住我"功能
- **登录保护**：防止暴力破解，支持账户锁定机制

### 👤 用户管理
- **角色权限**：支持管理员和普通用户角色
- **用户信息**：显示用户名、角色、登录时间等信息
- **密码修改**：用户可以自行修改密码
- **账户状态**：支持启用/禁用用户账户

### 🛡️ 安全特性
- **会话超时**：默认1小时会话超时
- **登录尝试限制**：最多5次失败尝试后锁定账户
- **账户锁定**：失败登录后锁定5分钟
- **安全日志**：记录所有登录尝试和操作日志

## 默认账户

系统提供一个默认管理员账户：

- **用户名**：`admin`
- **密码**：`admin123`
- **角色**：管理员

> ⚠️ **安全提醒**：首次登录后请立即修改默认密码！

## 使用流程

### 1. 访问系统
打开浏览器访问：`http://your-server:5000`

系统会自动重定向到登录页面。

### 2. 登录
1. 输入用户名和密码
2. 可选择"记住我"（7天内免登录）
3. 点击"登录"按钮

### 3. 使用系统
登录成功后可以：
- 查看用户信息（右上角用户菜单）
- 执行镜像同步操作
- 修改个人密码
- 安全退出登录

### 4. 修改密码
1. 点击右上角用户菜单
2. 选择"修改密码"
3. 输入当前密码和新密码
4. 确认修改

### 5. 退出登录
点击右上角用户菜单中的"退出登录"

## 配置文件

用户配置文件位于：`config/users.yaml`

### 配置结构

```yaml
# 用户配置
users:
  admin:
    username: "admin"
    password_hash: "$2b$12$..."  # bcrypt哈希
    role: "admin"
    display_name: "管理员"
    email: "admin@example.com"
    active: true

# 会话配置
session:
  secret_key: "your-secret-key"  # 生产环境请更换
  session_timeout: 3600          # 会话超时（秒）
  remember_me_duration: 604800   # 记住我持续时间（秒）

# 安全配置
security:
  max_login_attempts: 5    # 最大登录尝试次数
  lockout_duration: 300    # 账户锁定时间（秒）
  password_min_length: 6   # 密码最小长度
```

## 添加新用户

### 方法1：手动编辑配置文件

1. 生成密码哈希：
```bash
python3 generate_password.py
```

2. 编辑 `config/users.yaml`：
```yaml
users:
  newuser:
    username: "newuser"
    password_hash: "$2b$12$..."  # 使用生成的哈希
    role: "user"
    display_name: "新用户"
    email: "newuser@example.com"
    active: true
```

3. 重启应用使配置生效

### 方法2：通过API（需要管理员权限）

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"username":"newuser","password":"password123","role":"user"}' \
  http://localhost:5000/api/admin/users
```

## 安全建议

### 🔒 密码安全
- 使用强密码（至少8位，包含大小写字母、数字、特殊字符）
- 定期更换密码
- 不要使用默认密码

### 🛡️ 系统安全
- 更换默认的session secret_key
- 启用HTTPS（生产环境）
- 定期备份用户配置文件
- 监控登录日志

### 🌐 网络安全
- 使用防火墙限制访问
- 配置反向代理（如Nginx）
- 启用访问日志记录

## 故障排除

### 登录失败
1. **密码错误**：检查用户名和密码是否正确
2. **账户锁定**：等待5分钟后重试，或联系管理员
3. **账户禁用**：联系管理员启用账户

### 会话问题
1. **会话过期**：重新登录
2. **Cookie问题**：清除浏览器Cookie后重试

### 配置问题
1. **配置文件错误**：检查YAML语法是否正确
2. **密码哈希错误**：使用generate_password.py重新生成

## API接口

### 登录
```bash
POST /api/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123",
  "remember_me": false
}
```

### 登出
```bash
POST /api/logout
```

### 获取用户信息
```bash
GET /api/user/info
```

### 修改密码
```bash
POST /api/user/change-password
Content-Type: application/json

{
  "old_password": "old123",
  "new_password": "new123"
}
```

## 日志记录

系统会记录以下安全相关事件：
- 登录成功/失败
- 密码修改
- 账户锁定/解锁
- 会话创建/销毁
- 同步任务操作

日志格式：
```
INFO:__main__:用户 admin 登录成功，IP: 192.168.1.100
WARNING:__main__:用户 admin 登录失败: 密码错误, IP: 192.168.1.100
INFO:__main__:用户 admin 修改密码成功
INFO:__main__:用户 admin 启动同步任务 sync_1234567890
```

## 技术实现

- **后端框架**：Flask + Flask-SocketIO
- **密码加密**：bcrypt
- **会话管理**：Flask Session
- **前端框架**：Bootstrap 5 + JavaScript
- **配置格式**：YAML

## 更新日志

### v1.0.0 (2025-01-24)
- ✅ 初始认证系统实现
- ✅ 用户登录/登出功能
- ✅ 密码修改功能
- ✅ 会话管理
- ✅ 安全防护机制
- ✅ 用户界面集成 