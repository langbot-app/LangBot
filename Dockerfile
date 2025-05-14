FROM node:22-alpine AS node

WORKDIR /app

COPY web ./web

RUN cd web && npm install && npm run build

FROM python:3.12.7-slim

WORKDIR /app

COPY . .

COPY --from=node /app/web/out ./web/out

RUN apt update \
    && apt install gcc -y \
    && python -m pip install --no-cache-dir uv \
    && uv sync \
    && touch /.dockerenv

CMD [ "uv", "run", "main.py" ]