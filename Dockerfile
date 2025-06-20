# 多阶段构建 - 构建阶段
FROM 192.168.0.25:8888/flydiy-base/python:3.10-slim_fly-1.0.0 as builder

# 设置工作目录
WORKDIR /app

# 安装构建依赖
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    curl \
    gnupg2 \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 生产阶段
FROM 192.168.0.25:8888/flydiy-base/python:3.10-slim_fly-1.0.0

# 安装运行时依赖
RUN apt-get update && \
    apt-get install -y \
    skopeo \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 设置时区为上海
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 设置工作目录
WORKDIR /app

# 从构建阶段复制Python包
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY . .

# 创建必要的目录并设置权限
RUN mkdir -p config templates static/css static/js logs downloads \
    && mkdir -p /tmp/docker-sync \
    && chmod -R 755 /app \
    && chmod -R 777 /tmp/docker-sync \
    && chmod +x install_skopeo.sh start.sh \
    && chmod 755 /app/config \
    && chmod 755 /app/logs \
    && chmod 755 /app/downloads \
    && chmod 644 /app/config/* 2>/dev/null || true

# 设置环境变量
ENV HOME=/root
ENV USER=root
ENV TMPDIR=/tmp/docker-sync

# 暴露端口
EXPOSE 5000

# 设置环境变量
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# 启动命令（以root用户运行）
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"] 
