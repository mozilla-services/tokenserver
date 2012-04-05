.PHONY: bench test report createdb

build:
	virtualenv --no-site-packages --distribute .
	bin/easy_install funkload
	../bin/python generate_assertions.py

test:
	bin/fl-run-test loadtest.py

bench:
	bin/fl-run-bench loadtest.py NodeAssignmentTest

report:
	bin/fl-build-report --html -o html simple-bench.xml
