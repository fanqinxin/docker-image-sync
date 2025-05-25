# Skopeo兼容性修复说明

## 问题描述

在使用阿里云ACR进行镜像同步时，可能会遇到以下错误：

```
错误: time="2025-05-24T01:45:20+08:00" level=fatal msg="flag provided but not defined: -retry-times"
```

## 原因分析

这个错误是由于代码中使用了当前Skopeo版本不支持的参数`--retry-times`导致的。不同版本的Skopeo支持的参数有所不同。

## 修复方案

### 已修复的问题

1. **移除不支持的参数**：
   - 移除了`--retry-times`参数
   - 移除了`--command-timeout`参数

2. **保留兼容的参数**：
   - `--dest-tls-verify=false` ✅
   - `--src-tls-verify=false` ✅  
   - `--format v2s2` ✅
   - `--dest-compress-format gzip` ✅ (仅阿里云ACR)
   - `--dest-creds` ✅
   - `--src-creds` ✅

### 修复前的命令

```bash
skopeo copy \
  --dest-tls-verify=false \
  --src-tls-verify=false \
  --retry-times 3 \          # ❌ 不支持
  --format v2s2 \
  --dest-compress-format gzip \
  --dest-creds user:pass \
  docker://source \
  docker://target
```

### 修复后的命令

```bash
skopeo copy \
  --dest-tls-verify=false \
  --src-tls-verify=false \
  --format v2s2 \
  --dest-compress-format gzip \
  --dest-creds user:pass \
  docker://source \
  docker://target
```

## 验证修复

可以使用测试脚本验证修复是否成功：

```bash
python3 test_acr_fix.py
```

预期输出应该显示所有测试通过。

## 支持的Skopeo版本

当前已测试的版本：
- Skopeo 0.1.40 ✅

对于其他版本，如果遇到参数不支持的问题，可以参考这个修复方法。

## 如何查看Skopeo支持的参数

```bash
# 查看版本
skopeo --version

# 查看copy命令支持的参数
skopeo copy --help
```

## 阿里云ACR特殊优化

对于阿里云ACR，代码会自动：
1. 启用gzip压缩格式
2. 使用较长的超时时间（10分钟）
3. 自动将阿里云域名添加到代理排除列表

## 故障排除

如果仍有问题：

1. **检查Skopeo版本**：
   ```bash
   skopeo --version
   ```

2. **测试基本连接**：
   ```bash
   skopeo inspect docker://alpine:latest
   ```

3. **查看详细日志**：
   在Web界面中，同步过程的详细日志会实时显示错误信息。

4. **手动测试命令**：
   ```bash
   skopeo copy \
     --dest-tls-verify=false \
     --src-tls-verify=false \
     --dest-creds 用户名:密码 \
     docker://alpine:latest \
     docker://registry.cn-shenzhen.aliyuncs.com/命名空间/alpine:latest
   ```

## 更新记录

- **2025-05-24**: 修复`--retry-times`参数不支持的问题
- **2025-05-24**: 优化阿里云ACR兼容性 