#!/bin/bash
# workers.sh [-n] worker_count
#
# spawns $worker_count loadtest jobs
# if -n is specified, will create new users (that hit stoken)

TEST="test_single_token_exchange"
if [ "$1" = "-n" ]; then
    TEST="test_single_token_exchange_new_user"
    shift
fi

workers=${1:-5}
tmpdir=$(mktemp -d)
trap "rm -rf $tmpdir" EXIT

ulimit -s 2048

xapply -xP$workers '
    mkdir -p %1
    cp loadtest.py NodeAssignmentTest.conf %1
    cd %1
    ../../bin/fl-run-bench -f loadtest.py NodeAssignmentTest.'"$TEST"'
' $(seq 1 $workers)
