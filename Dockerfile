FROM python:2.7

WORKDIR /app
COPY . /app

# install tokenserver dependencies
RUN pip install --upgrade --no-cache-dir -r requirements.txt \
        gunicorn nose flake8 && \
    python ./setup.py develop
