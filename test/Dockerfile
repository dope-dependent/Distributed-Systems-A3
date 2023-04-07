FROM python:3.10.7-slim-buster

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
COPY ./test/requirements.txt /usr/src/app/requirements.txt
RUN pip install -r requirements.txt

# copy project
ADD PySyncObj /usr/src/app/PySyncObj
COPY test /usr/src/app

WORKDIR /usr/src/app/PySyncObj

RUN python setup.py develop
WORKDIR /usr/src/app/