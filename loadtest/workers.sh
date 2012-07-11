#!/bin/bash

workers=${1:-5}
tmpdir=$(mktemp -d)
trap "rm -rf $tmpdir" EXIT

ulimit -s 2048

xapply -xP$workers '
    mkdir -p %1
    cp loadtest.py NodeAssignmentTest.conf %1
    cd %1
    ../../bin/fl-run-bench -f loadtest.py NodeAssignmentTest.test_single_token_exchange
' $(seq 1 $workers)
