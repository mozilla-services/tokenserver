VIRTUALENV = virtualenv
NOSE = bin/nosetests
PYTHON = bin/python
PIP = bin/pip
FLAKE8 = bin/flake8
PIP_CACHE = /tmp/pip-cache.${USER}
BUILD_TMP = /tmp/syncstorage-build.${USER}
PYPI = https://pypi.python.org/simple
INSTALL = $(PIP) install -U -i $(PYPI)


.PHONY: all build test protobuf

all:	build

build:
	$(VIRTUALENV) --no-site-packages --distribute .
	$(INSTALL) --upgrade Distribute
	$(INSTALL) Cython
	$(INSTALL) nose
	$(INSTALL) flake8
	$(INSTALL) https://github.com/zeromq/pyzmq/archive/ad78488d2d72beab5915bbc21be7f13e4c347eec.zip
	bin/easy_install `bin/python ezm2c.py`
	$(INSTALL) -r requirements.txt
	$(PYTHON) ./setup.py develop


test:
	$(FLAKE8) --exclude=messages.py,test_remote_verifier.py tokenserver
	$(NOSE) tokenserver/tests


protobuf:
	cd tokenserver/crypto && protoc messages.pb --python_out=. && echo "# flake8: noqa" > messages.py && cat messages/pb_pb2.py >> messages.py && rm -rf messages


clean:
	rm -rf bin lib include local docs/build
