APPNAME = tokenserver
DEPS =
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
PIP_CACHE = /tmp/pip-cache
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

.PHONY: all build build_rpms test update custom_builds

all:	build

build_mcrypto:
	$(VIRTUALENV) --no-site-packages --distribute .
	$(INSTALL) MoPyTools
	$(INSTALL) nose
	$(INSTALL) WebTest
	$(INSTALL) wsgi_intercept
	cd /tmp; wget $(PYPI2)/source/M/M2Crypto/M2Crypto-0.21.1.tar.gz#md5=f93d8462ff7646397a9f77a2fe602d17
	cd /tmp && tar -xzvf M2Crypto-0.21.1.tar.gz && cd M2Crypto-0.21.1 && sed -i -e 's/opensslconf\./opensslconf-x86_64\./' SWIG/_ec.i && sed -i -e 's/opensslconf\./opensslconf-x86_64\./' SWIG/_evp.i && SWIG_FEATURES=-cpperraswarn $(PYTHON) setup.py install
	rm -rf /tmp/M2Crypto*
	$(BUILDAPP) -t $(TIMEOUT) -c $(CHANNEL) $(PYPIOPTIONS) $(DEPS)

build:
	$(VIRTUALENV) --no-site-packages --distribute .
	$(INSTALL) MoPyTools
	$(INSTALL) nose
	$(INSTALL) WebTest
	$(INSTALL) wsgi_intercept
	$(BUILDAPP) -t $(TIMEOUT) -c $(CHANNEL) $(PYPIOPTIONS) $(DEPS)

update:
	$(BUILDAPP) -t $(TIMEOUT) -c $(CHANNEL) $(PYPIOPTIONS) $(DEPS)

test:
	$(NOSE) $(TESTS)

build_rpms:
	rm -rf rpms
	mkdir rpms
	$(BUILDRPMS) -t $(TIMEOUT) -c $(RPM_CHANNEL) $(DEPS)
	custom_builds

mach: build build_rpms
	mach clean
	mach yum install python26 python26-setuptools
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla-services/gunicorn-0.11.2-1moz.x86_64.rpm
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla/nginx-0.7.65-4.x86_64.rpm
	mach yum install rpms/*
	mach chroot python2.6 -m appsync.run

clean:
	rm -rf bin lib include local docs/build

custom_builds:
	bin/pip install cython
	cd /tmp; rm -f /tmp/master.zip
	cd /tmp; wget https://github.com/zeromq/pyzmq/zipball/master --no-check-certificate
	cd /tmp; mv master master.zip
	bin/pypi2rpm.py /tmp/master.zip --dist-dir=$(CURDIR)
	cd /tmp; rm -f /tmp/master.zip
	cd /tmp; wget https://github.com/mozilla/PyBrowserID/zipball/master --no-check-certificate
	cd /tmp; mv master master.zip
	bin/pypi2rpm.py /tmp/master.zip --dist-dir=$(CURDIR)
	cd /tmp; rm -f /tmp/master.zip
	cd /tmp; wget https://github.com/mozilla-services/powerhose/zipball/master --no-check-certificate
	cd /tmp; mv master master.zip
	bin/pypi2rpm.py /tmp/master.zip --dist-dir=$(CURDIR)
	cd /tmp; rm -f /tmp/master.zip
	cd /tmp; wget https://github.com/tarekziade/gevent-zeromq/zipball/master --no-check-certificate
	cd /tmp; mv master master.zip
	bin/pypi2rpm.py /tmp/master.zip --dist-dir=$(CURDIR)
	cd /tmp; rm -f /tmp/master.zip
	cd /tmp; wget https://github.com/mozilla-services/wimms/zipball/master --no-check-certificate
	cd /tmp; mv master master.zip
	bin/pypi2rpm.py /tmp/master.zip --dist-dir=$(CURDIR)
	cd /tmp; rm -f /tmp/master.zip
	cd /tmp; wget https://github.com/Pylons/pyramid/zipball/master --no-check-certificate
	cd /tmp; mv master master.zip
	bin/pypi2rpm.py /tmp/master.zip --dist-dir=$(CURDIR)

mach: build build_rpms
	mach clean
	mach yum install python26 python26-setuptools
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla-services/gunicorn-0.11.2-1moz.x86_64.rpm
	cd rpms; wget http://mrepo.mozilla.org/mrepo/5-x86_64/RPMS.mozilla/nginx-0.7.65-4.x86_64.rpm
	mach yum install rpms/*
	mach chroot python2.6 -m appsync.run


