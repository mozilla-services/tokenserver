APPNAME = tokenserver
DEPS = https://github.com/mozilla-services/powerhose,https://github.com/mozilla-services/wimms,https://github.com/mozilla-services/mozservices,https://github.com/mozilla-services/tokenlib,https://github.com/mozilla-services/circus
VIRTUALENV = virtualenv
PYTHON = $(CURDIR)/bin/python
NOSE = bin/nosetests -s --with-xunit
FLAKE8 = bin/flake8
COVEROPTS = --cover-html --cover-html-dir=html --with-coverage --cover-package=appsync
TESTS = tokenserver
PKGS = tokenserver
COVERAGE = bin/coverage
PYLINT = bin/pylint
SERVER = dev-auth.services.mozilla.com
SCHEME = https
PYPI = http://c.pypi.python.org/simple
PYPI2 = http://c.pypi.python.org/packages
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
	mkdir -p ${BUILD_TMP}
	$(INSTALL) MoPyTools
	$(INSTALL) Distribute
	$(INSTALL) nose
	$(INSTALL) WebTest
	$(INSTALL) wsgi_intercept
	cd ${BUILD_TMP} && wget $(PYPI2)/source/M/M2Crypto/M2Crypto-0.21.1.tar.gz#md5=f93d8462ff7646397a9f77a2fe602d17
	cd ${BUILD_TMP} && tar -xzvf M2Crypto-0.21.1.tar.gz && cd M2Crypto-0.21.1 && sed -i -e 's/opensslconf\./opensslconf-x86_64\./' SWIG/_ec.i && sed -i -e 's/opensslconf\./opensslconf-x86_64\./' SWIG/_evp.i && SWIG_FEATURES=-cpperraswarn $(PYTHON) setup.py install
	rm -rf ${BUILD_TMP}/M2Crypto*
	$(INSTALL) pyzmq
	bin/pip install cython
	bin/pip install https://bitbucket.org/tarek/gevent/get/48b7c5262cca.tar.gz
	bin/pip install https://github.com/mozilla/PyBrowserID/zipball/master
	cd ${BUILD_TMP} && wget https://github.com/tarekziade/gevent-zeromq/zipball/master
	cd ${BUILD_TMP} && unzip master; cd tarekziade-gevent-*; $(PYTHON) setup.py install
	$(BUILDAPP) -t $(TIMEOUT) -c $(CHANNEL) $(PYPIOPTIONS) $(DEPS)

build_no_crypto:
	$(VIRTUALENV) --no-site-packages --distribute .
	$(INSTALL) MoPyTools
	$(INSTALL) nose
	$(INSTALL) WebTest
	$(INSTALL) wsgi_intercept
	$(INSTALL) pyzmq
	$(INSTALL) https://github.com/mozilla/PyBrowserID/zipball/master
	cd ${PIP_CACHE} && wget https://github.com/tarekziade/gevent-zeromq/zipball/master --no-check-certificate
	cd ${PIP_CACHE} && unzip master; cd tarekziade-gevent-*; $(PYTHON) setup.py install
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
	bin/pip install cython
	rm -f ${BUILD_TMP}/master.zip
	wget -O ${BUILD_TMP}/master.zip https://github.com/zeromq/pyzmq/zipball/master --no-check-certificate
	bin/pypi2rpm.py ${BUILD_TMP}/master.zip --dist-dir=$(RPMDIR)
	wget -O ${BUILD_TMP}/master.zip https://github.com/mozilla/PyBrowserID/zipball/master --no-check-certificate
	bin/pypi2rpm.py ${BUILD_TMP}/master.zip --dist-dir=$(RPMDIR)
	wget -O ${BUILD_TMP}/master.zip https://github.com/tarekziade/gevent-zeromq/zipball/master --no-check-certificate
	bin/pypi2rpm.py ${BUILD_TMP}/master.zip --dist-dir=$(RPMDIR)
	wget -O ${BUILD_TMP}/master.zip https://github.com/Pylons/pyramid/zipball/master --no-check-certificate
	bin/pypi2rpm.py ${BUILD_TMP}/master.zip --dist-dir=$(RPMDIR)
	bin/pypi2rpm.py http://pypi.python.org/packages/source/n/nose/nose-0.11.4.tar.gz --dist-dir=$(RPMDIR)
	cd ${BUILD_TMP} && wget $(PYPI2)/source/M/M2Crypto/M2Crypto-0.21.1.tar.gz#md5=f93d8462ff7646397a9f77a2fe602d17
	cd ${BUILD_TMP} && tar -xzvf M2Crypto-0.21.1.tar.gz && cd M2Crypto-0.21.1 && sed -i -e 's/opensslconf\./opensslconf-x86_64\./' SWIG/_ec.i && sed -i -e 's/opensslconf\./opensslconf-x86_64\./' SWIG/_evp.i && SWIG_FEATURES=-cpperraswarn $(PYTHON) setup.py --command-packages=pypi2rpm.command bdist_rpm2 --binary-only --dist-dir=$(RPMDIR) --name=python26-m2crypto
	rm -rf ${BUILD_TMP}/M2Crypto*

mock: build build_rpms
	mock init
	mock --install python26 python26-setuptools openssl python26-m2crypto
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla-services/gunicorn-0.11.2-1moz.x86_64.rpm
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla/nginx-0.7.65-4.x86_64.rpm
	mock --install rpms/*
	mock --chroot "python2.6 -m tokenserver.run"

clean:
	rm -rf bin lib include local docs/build
