FROM python:3.10.13-slim
WORKDIR /app

COPY . .

RUN apt update \
    && apt install gcc -y \
    && python -m pip install -r requirements.txt  
                        
CMD [ "python", "main.py" ]