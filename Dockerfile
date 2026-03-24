FROM node:22-alpine AS node

WORKDIR /app

COPY web ./web

RUN cd web && npm install && npm run build

FROM python:3.12.7-slim

WORKDIR /app

# Use Chinese mirror for faster and more reliable package downloads
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true

COPY . .

COPY --from=node /app/web/out ./web/out

RUN apt update \
    && apt install gcc -y \
    && python -m pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple uv \
    && uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && touch /.dockerenv

CMD [ "uv", "run", "--no-sync", "main.py" ]