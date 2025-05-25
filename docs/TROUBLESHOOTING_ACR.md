# 阿里云ACR（Container Registry）故障排除指南

## 常见错误及解决方案

### 1. `unexpected EOF` 错误

**错误特征：**
```
Error trying to reuse blob sha256:xxx at destination: Get https://dockerauth.cn-hangzhou.aliyuncs.com/auth?account=xxx&scope=repository%3Axxx%3Apull%2Cpush&service=registry.aliyuncs.com%3Axxx: unexpected EOF
```

**原因分析：**
- 网络连接在OAuth认证过程中意外中断
- 阿里云ACR服务暂时不稳定
- 镜像层过大，传输超时
- 代理服务器配置问题

**解决方案：**

#### 方案1：检查网络连接
```bash
# 测试阿里云ACR连接
ping registry.cn-shenzhen.aliyuncs.com
curl -I https://registry.cn-shenzhen.aliyuncs.com/v2/

# 测试认证服务器连接
curl -I https://dockerauth.cn-hangzhou.aliyuncs.com/
```

#### 方案2：使用更稳定的区域
在 `config/registries.yaml` 中切换到就近的区域：
```yaml
- name: 阿里云ACR
  type: acr
  # 根据您的地理位置选择最近的区域
  url: registry.cn-shenzhen.aliyuncs.com   # 深圳
  # url: registry.cn-hangzhou.aliyuncs.com # 杭州  
  # url: registry.cn-beijing.aliyuncs.com  # 北京
  username: your-username
  password: your-password
  namespace: your-namespace
```

#### 方案3：检查认证信息
确保阿里云ACR的认证信息正确：
1. **用户名**：阿里云账号名称
2. **密码**：
   - 如果使用子账号：使用访问密钥（AccessKey Secret）
   - 如果使用主账号：使用临时Token或固定密码

#### 方案4：调整代理配置
如果使用代理，确保阿里云ACR域名在排除列表中：
```
no_proxy: localhost,127.0.0.1,*.aliyuncs.com
```

#### 方案5：分批同步大镜像
对于大型镜像，建议：
1. 单独同步大镜像
2. 分多次执行，避免超时
3. 使用阿里云内网进行同步

### 2. 权限错误

**错误特征：**
```
unauthorized: authentication required
```

**解决方案：**
1. 检查阿里云ACR命名空间权限
2. 确认账号有推送（push）权限
3. 验证用户名和密码是否正确

### 3. 命名空间不存在

**错误特征：**
```
repository does not exist
```

**解决方案：**
1. 在阿里云控制台创建命名空间
2. 确认配置文件中的命名空间名称正确
3. 检查命名空间的访问权限

### 4. 网络优化建议

#### 使用阿里云ECS内网
如果在阿里云ECS上运行：
```yaml
# 使用内网域名，速度更快，不消耗公网流量
url: registry-vpc.cn-shenzhen.aliyuncs.com
```

#### 网络稳定性优化
```bash
# 增加TCP连接超时时间
echo 'net.ipv4.tcp_keepalive_time = 600' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_keepalive_intvl = 60' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_keepalive_probes = 3' >> /etc/sysctl.conf
sysctl -p
```

### 5. 最佳实践

#### 选择合适的区域
- **就近原则**：选择物理距离最近的区域
- **网络质量**：测试不同区域的网络延迟
- **内网优先**：阿里云ECS优先使用VPC内网

#### 认证配置
```yaml
- name: 阿里云ACR
  type: acr
  url: registry.cn-shenzhen.aliyuncs.com
  username: your-aliyun-account
  password: your-access-key-secret  # 或临时Token
  namespace: your-namespace
```

#### 批量同步策略
1. **小镜像批量**：小于100MB的镜像可以批量同步
2. **大镜像单独**：大于500MB的镜像建议单独同步
3. **错峰执行**：避开网络高峰期

### 6. 监控和诊断

#### 日志分析
```bash
# 查看详细的skopeo日志
skopeo copy --debug docker://source-image docker://target-image

# 检查网络连接
tcpdump -i any host registry.cn-shenzhen.aliyuncs.com
```

#### 性能监控
```bash
# 监控网络带宽
iftop -i eth0

# 监控磁盘IO
iotop
```

## 联系支持

如果问题仍未解决：
1. 收集完整的错误日志
2. 记录网络环境信息
3. 联系阿里云技术支持
4. 或在项目Issues中反馈 