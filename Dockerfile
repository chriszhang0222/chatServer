FROM python:3
LABEL maintainer="chris@quantumsds.com"

RUN apt-get update && apt-get install -y python3-pip

RUN pip3 install pipenv
RUN mkdir /app
ADD . /app

WORKDIR /app

RUN pipenv sync

EXPOSE 8888 8889

CMD sh entrypoint.sh
