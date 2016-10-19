FROM python:2.7-slim

RUN groupadd --gid 1001 app && \
    useradd --uid 1001 --gid 1001 --shell /usr/sbin/nologin app

WORKDIR /app
COPY ./requirements.txt /app/requirements.txt

# install tokenserver dependencies
RUN apt-get -q update \
    && apt-get -q --yes install g++ \
    && pip install --upgrade --no-cache-dir -r requirements.txt \
         gunicorn nose flake8 \
    && apt-get -q --yes remove g++ \
    && apt-get -q --yes autoremove \
    && apt-get clean

COPY . /app
RUN python ./setup.py develop

# run as non priviledged user
USER app
