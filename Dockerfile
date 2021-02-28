FROM ubuntu:20.04
WORKDIR /root

RUN apt update && apt -y install python3-pip openssl
RUN pip3 install \
    pyTelegramBotAPI \
    firebase-admin \
    jsonpickle \
    pyYaml \
    redis \
    aiohttp

RUN echo "refresh"

RUN mkdir /root/mybwf && mkdir /root/mybwf/ssl
WORKDIR /root/mybwf/ssl
COPY ./ssl/* .
RUN openssl genrsa -out webhook_pkey.pem 2048 && \
openssl req -new -config config.cnf -x509 -days 3650 -key webhook_pkey.pem -out webhook_cert.pem
WORKDIR /root/mybwf
COPY ./src ./src
COPY ./config.yml .
COPY ./firebase_service_account_key.json .

WORKDIR /root/mybwf/src
CMD ["python3", "./bwfbot.py"]