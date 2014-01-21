SERVER_URL = https://token.services.mozilla.com

.PHONY: build test bench

build:
	../bin/pip install https://github.com/mozilla-services/loads/archive/master.zip

test:
	../bin/loads-runner --hits=1 --users=1 loadtest.NodeAssignmentTest.test_realistic --server-url=$(SERVER_URL)

bench:
	../bin/loads-runner --users=20 --duration=1800 --include-file=./loadtest.py loadtest.NodeAssignmentTest.test_realistic --server-url=$(SERVER_URL)
