FROM python:3.8-slim
WORKDIR /root

RUN pip install pyTelegramBotAPI firebase-admin jsonpickle pyyaml redis

COPY ./src ./src
COPY ./config.yml .
COPY ./firebase_service_account_key_SECRET.json .

WORKDIR /root/src

CMD ["python", "./bwfbot.py"]