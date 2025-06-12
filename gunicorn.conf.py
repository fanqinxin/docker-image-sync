# Gunicorn配置文件 - 优化大文件批量下载
import multiprocessing
import os

# 绑定地址和端口
bind = "0.0.0.0:5000"

# Worker进程数（使用eventlet时建议为1）
workers = 1

# Worker类型
worker_class = "eventlet"

# Worker超时时间（秒）- 设置为5分钟以支持大文件压缩
timeout = 300

# 最大请求数（防止内存泄漏）
max_requests = 1000
max_requests_jitter = 100

# 预加载应用
preload_app = True

# 内存限制（MB）
worker_memory_limit = 2048

# 临时文件目录
worker_tmp_dir = "/tmp"

# 日志配置
loglevel = "info"
accesslog = "-"
errorlog = "-"

# 进程名
proc_name = "docker-image-sync"

# 用户和组
# user = "root"
# group = "root"

# 守护进程模式
daemon = False

# PID文件
pidfile = "/tmp/gunicorn.pid"

# 保持连接时间
keepalive = 5

# 最大并发连接数
worker_connections = 1000

# 限制请求行大小
limit_request_line = 8192

# 限制请求头大小
limit_request_fields = 200
limit_request_field_size = 8192

# SSL配置（如果需要）
# keyfile = None
# certfile = None

# 重启配置
max_worker_life_time = 3600  # 1小时后重启worker 