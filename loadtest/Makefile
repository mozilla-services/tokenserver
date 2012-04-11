.PHONY: bench test report createdb

build:
	../bin/easy_install funkload

test:
	../bin/fl-run-test loadtest.py

bench:
	../bin/fl-run-bench loadtest.py NodeAssignmentTest

report:
	../bin/fl-build-report --html -o html simple-bench.xml
