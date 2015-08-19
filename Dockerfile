FROM centos:6

COPY . /app
WORKDIR /app

# supporting old school python 2.6 apps is *fun*
RUN yum install -y epel-release && \
    yum install -y python-pip gcc-c++ python-devel && \
    pip install -r requirements.txt && \
    pip install gunicorn && \
    python ./setup.py develop && \
    yum clean all
