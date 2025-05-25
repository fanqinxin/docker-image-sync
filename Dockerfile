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

# 安装Python依赖到临时目录
RUN pip install --no-cache-dir --user -r requirements.txt

# 生产阶段
FROM 192.168.0.25:8888/flydiy-base/python:3.10-slim_fly-1.0.0

# 创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 安装运行时依赖
RUN apt-get update && \
    apt-get install -y \
    skopeo \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 设置工作目录
WORKDIR /app

# 从构建阶段复制Python包
COPY --from=builder /root/.local /home/appuser/.local

# 复制应用代码
COPY . .

# 创建必要的目录并设置权限
RUN mkdir -p config templates static/css static/js logs downloads \
    && chown -R appuser:appuser /app \
    && chmod +x install_skopeo.sh start.sh

# 设置PATH以包含用户本地Python包
ENV PATH=/home/appuser/.local/bin:$PATH

# 切换到非root用户
USER appuser

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

# 启动命令
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "app:app"] 
