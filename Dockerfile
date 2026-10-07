# 使用官方Python镜像作为构建阶段基础
FROM docker.io/library/python:3.11-slim AS builder

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 升级pip并安装依赖
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

# 暴露端口（根据需要修改）
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]