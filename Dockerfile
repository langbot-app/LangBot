FROM node:22-alpine AS node

WORKDIR /app

COPY web ./web

RUN cd web && npm install && npm run build

FROM python:3.12.7-slim

WORKDIR /app

# 先复制依赖文件，利用 Docker 层缓存
COPY pyproject.toml uv.lock ./

# 安装系统依赖和 Python 依赖（排除开发依赖）
RUN apt update \
    && apt install gcc -y \
    && python -m pip install --no-cache-dir uv \
    && uv sync --no-dev \
    && apt-get purge -y gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && touch /.dockerenv

# 再复制源代码，代码变化不会触发依赖重装
COPY . .

COPY --from=node /app/web/out ./web/out

CMD [ "uv", "run", "--no-sync", "main.py" ]
