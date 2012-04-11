.. _installation:

Installing the Token Server
===========================

The basic instructions to install the Token Server is to run `make build`::


    $ git clone https://github.com/mozilla-services/tokenserver
    $ cd tokenserver
    $ make build

This set of instruction should work out of the box under RHEL6.

Once this is done, you can run the server with Paster::

    $ bin/paster serve etc/tokenserver-dev.ini


Specific instructions on other platforms
----------------------------------------

XXX

