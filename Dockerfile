FROM pypy:2.7-7.3.3-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup -gid 1001 app && useradd -g app --shell /usr/sbin/nologin --uid 1001 app

# run the server by default
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["server"]

# install dependencies, cleanup and add libstdc++ back in since
# we the app needs to link to it
RUN apt-get update && \
    apt-get install -y build-essential ca-certificates libffi-dev libssl-dev default-libmysqlclient-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt dev-requirements.txt /app/

RUN pip install --upgrade -r dev-requirements.txt && \
    apt-get remove -y build-essential gcc libffi-dev libssl-dev default-libmysqlclient-dev

COPY . /app

RUN pypy ./setup.py develop

# run as non priviledged user
USER app
