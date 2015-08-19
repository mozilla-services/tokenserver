FROM centos:6

COPY . /app
WORKDIR /app

# install pip
RUN yum install -y epel-release && \
    yum install -y python-pip

# install tokenserver dependencies
RUN yum install -y gcc-c++ python-devel && \
    pip install -r requirements.txt && \
    pip install gunicorn && \
    python ./setup.py develop && \
    yum clean all
