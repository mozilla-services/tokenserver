FROM python:2.7.10

WORKDIR /app
COPY ./requirements.txt /app/requirements.txt

# install tokenserver dependencies
RUN pip install --upgrade --no-cache-dir -r requirements.txt \
        gunicorn nose flake8 && \

python ./setup.py develop
COPY . /app
