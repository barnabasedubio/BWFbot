FROM ubuntu:20.04
WORKDIR /root

RUN pip install \
    pyTelegramBotAPI \
    firebase-admin \
    jsonpickle \
    pyYaml \
    redis \
    aiohttp \
    openssl

# RUN mkdir /root/mybwf/ssl

COPY ./src ./src
COPY ./config.yml .
COPY ./firebase_service_account_key.json .

# WORKDIR /root/src
# CMD ["python", "./bwfbot.py"]