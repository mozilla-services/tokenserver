SERVER_URL = https://token.services.mozilla.com

.PHONY: build test bench

build:
	../bin/pip install https://github.com/mozilla-services/loads/archive/master.zip

# Run a single test from the local machine, for sanity-checking.
test:
	../bin/loads-runner --hits=1 --users=1 loadtest.NodeAssignmentTest.test_realistic --server-url=$(SERVER_URL)

# Run a fuller bench suite from the local machine.
bench:
	../bin/loads-runner --users=20 --duration=300 loadtest.NodeAssignmentTest.test_realistic --server-url=$(SERVER_URL)

# Run a full bench, by submitting to broker in AWS.
megabench:
	../bin/loads-runner --broker=tcp://loads.services.mozilla.com:7780 --users=20 --duration=1800 --agents=5 --include-file=./loadtest.py --python-dep=PyBrowserID loadtest.NodeAssignmentTest.test_realistic --server-url=$(SERVER_URL)
