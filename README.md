# Token Server

This application implements the Token Server as defined at
https://wiki.mozilla.org/Services/Sagrada/TokenServer

The following picture describes how the token server integrates with other
pieces of software we developped.

![Token Server diagram](http://ziade.org/token-org.png)

## How to run the tokenserver

To run the tokenserver, you just need to run:

    $ bin/paster serve etc/tokenserver-dev.ini
