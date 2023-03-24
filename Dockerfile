FROM python:3.9-slim
WORKDIR /QChatGPT

RUN sed -i "s/deb.debian.org/mirrors.tencent.com/g" /etc/apt/sources.list \
    && sed -i 's|security.debian.org/debian-security|mirrors.tencent.com/debian-security|g' /etc/apt/sources.list \
    && apt-get clean \
    && apt-get update \
    && apt-get -y upgrade \
    && apt-get install -y git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /QChatGPT/

RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

CMD [ "python", "main.py" ] 