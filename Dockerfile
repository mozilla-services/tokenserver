FROM python:2.7

COPY . /app
WORKDIR /app

# install tokenserver dependencies
RUN pip install --upgrade -r requirements.txt && \
    pip install gunicorn nose flake8 && \
    python ./setup.py develop
