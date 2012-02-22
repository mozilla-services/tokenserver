.PHONY: bench test report createdb

build:
	virtualenv --no-site-packages --distribute .
	bin/easy_install funkload
	bin/easy_install PyVEP

test:
	bin/fl-run-test simple.py

bench:
	bin/fl-run-bench simple.py SimpleTest.test_simple

report:
	bin/fl-build-report --html -o html simple-bench.xml
