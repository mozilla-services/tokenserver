SERVER_URL = https://token.services.mozilla.com

.PHONY: build test bench

build:
	../bin/pip install https://github.com/mozilla-services/loads/archive/master.zip

# Run a single test from the local machine, for sanity-checking.
test:
	../bin/loads-runner --config=./config/test.ini --server-url=$(SERVER_URL) loadtest.NodeAssignmentTest.test_realistic

# Run a fuller bench suite from the local machine.
bench:
	../bin/loads-runner --config=./config/bench.ini --server-url=$(SERVER_URL) loadtest.NodeAssignmentTest.test_realistic

# Run a full bench, by submitting to broker in AWS.
megabench:
	../bin/loads-runner --config=./config/megabench.ini --user-id=$(USER) --server-url=$(SERVER_URL) loadtest.NodeAssignmentTest.test_realistic

# Purge any currently-running loadtest runs.
purge:
	../bin/loads-runner --config=./config/megabench.ini --purge-broker
