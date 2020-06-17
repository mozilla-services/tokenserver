FROM pypy:2.7-jessie

WORKDIR /app

RUN addgroup -gid 1001 app && useradd -g app --shell /usr/sbin/nologin --uid 1001 app
# run the server by default
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["server"]

COPY ./requirements.txt /app/requirements.txt
COPY ./dev-requirements.txt /app/dev-requirements.txt

# install dependencies, cleanup and add libstdc++ back in since
# we the app needs to link to it
RUN apk add --update build-base ca-certificates libffi-dev libssl-dev mariadb-dev && \
    pip install -r requirements.txt gunicorn gevent && \
    pip install -r dev-requirements.txt && \
    apt-get remove -y build-essential gcc

# Copy in the whole app after dependencies have been installed & cached
COPY . /app
RUN pypy ./setup.py develop

# run as non priviledged user
USER app
