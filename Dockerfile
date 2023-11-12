FROM python:3.10.13-bullseye
WORKDIR /QChatGPT

COPY . /QChatGPT/

RUN ls

RUN python -m pip install -r requirements.txt && \
    python -m pip install -U websockets==10.0 && \
    python -m pip install -U httpcore httpx openai

# 生成配置文件
RUN python main.py

CMD [ "python", "main.py" ]