FROM node:22-alpine AS node

WORKDIR /app

COPY web ./web

RUN cd web && npm install && npm run build

FROM python:3.12.7-slim

WORKDIR /app

# 先复制依赖文件和后端运行必需源代码，尽量利用 Docker 层缓存
COPY pyproject.toml uv.lock README.md LICENSE main.py ./
COPY src ./src

RUN apt update \
    && apt install gcc -y \
    && python -m pip install --no-cache-dir uv \
    && uv sync --no-dev \
    && apt-get purge -y gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && touch /.dockerenv

# 再复制其余运行时文件，避免无关文件变更导致依赖重装
COPY . .

COPY --from=node /app/web/out ./web/out

CMD [ "uv", "run", "--no-sync", "main.py" ]
