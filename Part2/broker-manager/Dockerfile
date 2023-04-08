FROM python:3.10.7-slim-buster

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
COPY ./Part2/broker-manager/requirements.txt /usr/src/app/requirements.txt
RUN pip install -r requirements.txt
COPY ./Part2/broker-manager/responses.py /usr/src/app/responses.py

ADD PySyncObj /usr/src/app/PySyncObj

WORKDIR /usr/src/app/PySyncObj

RUN python setup.py develop
WORKDIR /usr/src/app/

ADD ./Part2/broker-manager /usr/src/app/