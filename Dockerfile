FROM python:3.10.13-alpine3.18
WORKDIR /QChatGPT

COPY . /QChatGPT/

RUN ls

RUN pip install -r requirements.txt && \
    pip install -U websockets==10.0 && \
    pip install -U httpcore httpx openai

# 生成配置文件
RUN python main.py

CMD [ "python", "main.py" ]