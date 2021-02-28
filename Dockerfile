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

# RUN mkdir /root/mybwf/ssl

COPY ./src ./src
COPY ./config.yml .
COPY ./firebase_service_account_key.json .

# WORKDIR /root/src
# CMD ["python", "./bwfbot.py"]