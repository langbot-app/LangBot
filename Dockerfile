# ========== 前端构建阶段 ==========
FROM node:22-alpine AS node

WORKDIR /app

COPY web ./web

RUN cd web && npm install && npm run build

FROM python:3.12.7-slim

WORKDIR /app

# 先复制依赖文件和后端运行必需源代码，尽量利用 Docker 层缓存
COPY pyproject.toml uv.lock README.md LICENSE main.py ./
COPY src ./src

# 安装系统依赖和 Python 依赖（排除开发依赖）
RUN apt update \
    && apt install gcc -y \
    && python -m pip install --no-cache-dir uv \
    && uv sync --no-dev \
    && apt-get purge -y gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && touch /.dockerenv

COPY --from=node /app/web/out ./web/out

CMD [ "uv", "run", "--no-sync", "main.py" ]
