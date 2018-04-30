SERVER_URL = https://token.stage.mozaws.net

# Hackety-hack around OSX system python bustage.
# The need for this should go away with a future osx/xcode update.
ARCHFLAGS = -Wno-error=unused-command-line-argument-hard-error-in-future

INSTALL = ARCHFLAGS=$(ARCHFLAGS) ../local/bin/pip install

.PHONY: build test bench

build:
	$(INSTALL) pexpect
	$(INSTALL) https://github.com/mozilla-services/loads/archive/master.zip
	$(INSTALL) -U 'requests<2.13'

# Update https://mock-oauth-stage.dev.lcip.org with latest config.
mock-oauth-stage:
	aws cloudformation deploy --template-file ./mock-oauth-cfn.yml --stack-name mock-oauth-stage --capabilities CAPABILITY_IAM

# Run a quick sanity-check on the server's advertised config.
config-check:
	../local/bin/loads-runner --config=./config/test.ini --server-url=$(SERVER_URL) loadtest.NodeAssignmentTest.test_server_config

# Run a single test from the local machine, for sanity-checking.
test:
	../local/bin/loads-runner --config=./config/test.ini --server-url=$(SERVER_URL) loadtest.NodeAssignmentTest.test_realistic

# Run a fuller bench suite from the local machine.
bench:
	../local/bin/loads-runner --config=./config/bench.ini --server-url=$(SERVER_URL) loadtest.NodeAssignmentTest.test_realistic

# Run a full bench, by submitting to broker in AWS.
megabench:
	../local/bin/loads-runner --config=./config/megabench.ini --user-id=$(USER) --server-url=$(SERVER_URL) loadtest.NodeAssignmentTest.test_realistic

# Purge any currently-running loadtest runs.
purge:
	../local/bin/loads-runner --config=./config/megabench.ini --purge-broker
