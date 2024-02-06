FROM python:3.10.13-bullseye
WORKDIR /app

COPY . .

RUN python -m pip install -r requirements.txt

CMD [ "python", "start.py" ]