VIRTUALENV = virtualenv
NOSE = local/bin/nosetests
PYTHON = local/bin/python
PIP = local/bin/pip
FLAKE8 = local/bin/flake8 --ignore=E402
PIP_CACHE = /tmp/pip-cache.${USER}
BUILD_TMP = /tmp/syncstorage-build.${USER}
PYPI = https://pypi.python.org/simple

# Hackety-hack around OSX system python bustage.
# The need for this should go away with a future osx/xcode update.
ARCHFLAGS = -Wno-error=unused-command-line-argument-hard-error-in-future

INSTALL = ARCHFLAGS=$(ARCHFLAGS) $(PIP) install -U -i $(PYPI)


.PHONY: all build test clean

all:	build

build:
	$(VIRTUALENV) ./local
	$(INSTALL) --upgrade pip
	$(INSTALL) -r requirements.txt
	$(PYTHON) setup.py develop

$(PIP): build

test: $(PIP)
	$(PIP) install nose flake8
	$(FLAKE8) tokenserver
	$(NOSE) tokenserver/tests


clean:
	rm -rf local
