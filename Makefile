APPNAME = tokenserver
DEPS = 
VIRTUALENV = virtualenv
PYTHON = $(CURDIR)/bin/python
NOSE = bin/nosetests --with-xunit
FLAKE8 = bin/flake8
COVEROPTS = --cover-html --cover-html-dir=html --with-coverage --cover-package=appsync
TESTS = tokenserver
PKGS = tokenserver
COVERAGE = bin/coverage
PYLINT = bin/pylint
SERVER = dev-auth.services.mozilla.com
SCHEME = https
PYPI = https://pypi.python.org/simple
PYPI2RPM = bin/pypi2rpm.py --index=$(PYPI)
PYPIOPTIONS = -i $(PYPI)
CHANNEL = dev
RPM_CHANNEL = dev
PIP_CACHE = /tmp/pip-cache.${USER}
BUILD_TMP = /tmp/token-build.${USER}
INSTALL = bin/pip install --download-cache=$(PIP_CACHE)
BUILDAPP = bin/buildapp --download-cache=$(PIP_CACHE)
BUILDRPMS = bin/buildrpms --download-cache=$(PIP_CACHE)
INSTALLOPTIONS = -U -i $(PYPI)
TIMEOUT = 300
DURATION = 30
CYCLES = 5:10:20
HOST = http://localhost:5000
BIN = ../bin
RPMDIR= $(CURDIR)/rpms

ifdef PYPIEXTRAS
	PYPIOPTIONS += -e $(PYPIEXTRAS)
	INSTALLOPTIONS += -f $(PYPIEXTRAS)
endif

ifdef PYPISTRICT
	PYPIOPTIONS += -s
	ifdef PYPIEXTRAS
		HOST = `python -c "import urlparse; print urlparse.urlparse('$(PYPI)')[1] + ',' + urlparse.urlparse('$(PYPIEXTRAS)')[1]"`

	else
		HOST = `python -c "import urlparse; print urlparse.urlparse('$(PYPI)')[1]"`
	endif

endif

INSTALL += $(INSTALLOPTIONS)

.PHONY: all build build_rpms test update build_rpms2

all:	build

build:
	$(VIRTUALENV) --no-site-packages --distribute .
	$(INSTALL) --upgrade Distribute
	mkdir -p ${BUILD_TMP}
	$(INSTALL) PasteDeploy
	$(INSTALL) PasteScript
	$(INSTALL) MoPyTools
	$(INSTALL) nose
	$(INSTALL) circus
	$(INSTALL) WebTest
	$(INSTALL) wsgi_intercept
	$(INSTALL) Cython
	$(INSTALL) https://github.com/zeromq/pyzmq/archive/ad78488d2d72beab5915bbc21be7f13e4c347eec.zip
	bin/easy_install `bin/python ezm2c.py`
	$(BUILDAPP) -t $(TIMEOUT) -c $(CHANNEL) $(PYPIOPTIONS) $(DEPS)

update:
	$(BUILDAPP) -t $(TIMEOUT) -c $(CHANNEL) $(PYPIOPTIONS) $(DEPS)

test:
	$(NOSE) $(TESTS)

build_rpms: build_rpms2
	$(BUILDRPMS) -t $(TIMEOUT) -c $(RPM_CHANNEL) $(DEPS)

build_rpms2:
	rm -rf rpms
	mkdir -p rpms ${BUILD_TMP}
	# Install cython so that we can build zmq-related stuff.
	bin/pip install cython
	# PyZMQ sdist bundles don't play nice with pypi2rpm.
	# Build it from a checkout of the tag instead.
	rm -f ${BUILD_TMP}/master.tar.gz
	wget -O ${BUILD_TMP}/master.tar.gz https://github.com/zeromq/pyzmq/tarball/master --no-check-certificate
	bin/pypi2rpm.py ${BUILD_TMP}/master.tar.gz --dist-dir=$(RPMDIR)
	cd ${BUILD_TMP} && wget $(PYPI)/source/M/M2Crypto/M2Crypto-0.21.1.tar.gz#md5=f93d8462ff7646397a9f77a2fe602d17
	cd ${BUILD_TMP} && tar -xzvf M2Crypto-0.21.1.tar.gz && cd M2Crypto-0.21.1 && sed -i -e 's/opensslconf\./opensslconf-x86_64\./' SWIG/_ec.i && sed -i -e 's/opensslconf\./opensslconf-x86_64\./' SWIG/_evp.i && SWIG_FEATURES=-cpperraswarn $(PYTHON) setup.py --command-packages=pypi2rpm.command bdist_rpm2 --binary-only --dist-dir=$(RPMDIR) --name=python26-m2crypto
	rm -rf ${BUILD_TMP}/M2Crypto*
	wget -O $(BUILD_TMP)/certifi-0.0.8.tar.gz http://pypi.python.org/packages/source/c/certifi/certifi-0.0.8.tar.gz
	cd $(BUILD_TMP) && tar xzf certifi-0.0.8.tar.gz
	echo 'include README.rst certifi/cacert.pem' >> $(BUILD_TMP)/certifi-0.0.8/MANIFEST.in
	$(PYPI2RPM) --dist-dir=$(RPMDIR) $(BUILD_TMP)/certifi-0.0.8

mock: build build_rpms
	mock init
	mock --install python26 python26-setuptools openssl
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla-services/gunicorn-0.11.2-1moz.x86_64.rpm
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla/nginx-0.7.65-4.x86_64.rpm
	mock --install rpms/*
	mock --chroot "python2.6 -m tokenserver.run"

protobuf:
	cd tokenserver/crypto && protoc messages.pb --python_out=. && echo "# flake8: noqa" > messages.py && cat messages/pb_pb2.py >> messages.py && rm -rf messages


clean:
	rm -rf bin lib include local docs/build
