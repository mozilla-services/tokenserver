[![Build Status](https://travis-ci.org/mozilla-services/tokenserver.png?branch=master)](https://travis-ci.org/mozilla-services/tokenserver)
[![Docker Build Status](https://circleci.com/gh/mozilla-services/tokenserver/tree/master.svg?style=shield&circle-token=0fdb6d8d80e18f180132ea25cf9f75a38828591a)](https://circleci.com/gh/mozilla-services/tokenserver)

# Token Server

This application implements the Token Server as defined at
https://wiki.mozilla.org/Services/Sagrada/TokenServer

The following picture describes how the token server integrates with other
pieces of software we developped.

![Token Server diagram](/token-server-diagram.png)

## How to run the tokenserver

To run the tokenserver, you just need to run:

    $ bin/paster serve etc/tokenserver-dev.ini
