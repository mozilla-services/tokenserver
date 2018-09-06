FROM python:2.7-alpine

WORKDIR /app

RUN addgroup -g 1001 app \
    && adduser -u 1001 -S -D -G app -s /usr/sbin/nologin app

# run the server by default
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["server"]

COPY ./requirements.txt /app/requirements.txt
COPY ./dev-requirements.txt /app/dev-requirements.txt

# install dependencies, cleanup and add libstdc++ back in since
# we the app needs to link to it
RUN apk add --update build-base ca-certificates libffi-dev openssl-dev && \
    pip install -r requirements.txt gunicorn gevent && \
    pip install -r dev-requirements.txt && \
    apk del --purge build-base gcc && \
    apk add libstdc++

# Copy in the whole app after dependencies have been installed & cached
COPY . /app
RUN python ./setup.py develop

# run as non priviledged user
USER app
