Configuration
=============

The token server comes with a main configuration file that's used to
run it. It's located at :file:`etc/tokenserver-dev.ini` and is a
typical Paste configuration file.

Relevant sections:

- tokenserver
- endpoints
- browserid
- powerhose

Example::

    [tokenserver]
    backend = tokenserver.assignment.fixednode.DefaultNodeAssignmentBackend
    service_entry = example.com
    applications = sync-1.0, aitc-1.0
    secrets_file = tokenserver/tests/secrets

    [endpoints]
    aitc-1.0 = {node}/1.0/{uid}

    [browserid]
    backend = tokenserver.verifiers.LocalVerifier
    audiences = *

    [powerhose]
    backend = tokenserver.tests.support.PowerHoseVerifier
    worker.memory_ttl = 1800

tokenserver
~~~~~~~~~~~
    **backend**
        The class used to assign a node to the user.

        Possible values:

        - :class:`tokenserver.assignment.fixednode.DefaultNodeAssignmentBackend`
        - :class:`tokenserver.assignment.sqlnode.SQLNodeAssignment`
        - :class:`tokenserver.assignment.sqlnode.ShardedSQLNodeAssignment`
        - :class:`tokenserver.assignment.sqlnode.SecuredShardedSQLNodeAssignment`

        See :ref:`nodeassign` for more information.

    **service_entry**
        The node returned for all users when using :class:`DefaultNodeAssignmentBackend`

    **applications**
        The list of supported services, separated by commas. A service is composed
        of a name and a version.

    **secrets_file**
        The path to the secrets files. Can be one to multiple files - one per line.

    **sqluri** -- for SQL backends only
        The SQL URI for the User DB

    **databases** -- for sharded SQL backends only --  **Overrides sqluri***
        A list of column separated databases SQLURI. Each database is a name of
        a service with its version, followed by a semi-column amd the SQLURI.

        Example: aitc-1.0;sqluri://aitc.db,sync-1.1;sqluri://sync.db

    **proxy_uri** -- for secured SQL backends only
        The url to the stoken server to delegate writes on the User DB.

    **create_tables** -- for SQL backends only
        If True, creates the tables in the DB when they don't exist

    **pool_size** -- for MySQL only
        The size of the pool to be maintained, defaults to 5. This is the largest
        number of connections that will be kept persistently in the pool. Note
        that the pool begins with no connections; once this number of connections
        is requested, that number of connections will remain. pool_size can be
        set to 0 to indicate no size limit

    **pool_recycle** -- for MySQL only
        If set to non -1, number of seconds between connection recycling, which
        means upon checkout, if this timeout is surpassed the connection will be
        closed and replaced with a newly opened connection. Defaults to -1.

    **pool_timeout** -- for MySQL only
        The number of seconds to wait before giving up on returning a connection.
        Defaults to 30.

    **max_overflow** -- for MySQL only
        The maximum overflow size of the pool. When the number of checked-out
        connections reaches the size set in pool_size, additional connections will
        be returned up to this limit. When those additional connections are returned
        to the pool, they are disconnected and discarded. It follows then that the
        total number of simultaneous connections the pool will allow is pool_size +
        max_overflow, and the total number of "sleeping" connections the pool will
        allow is pool_size. max_overflow can be set to -1 to indicate no overflow
        limit; no limit will be placed on the total number of concurrent connections.
        Defaults to 10.


endpoint
~~~~~~~~
    List of patterns for the api endpoints. The variable is the application name,
    the value is the pattern. When this section is not provided, and an SQL
    backend is provided, fall backs to using the patterns table in the SQL DB.

    Patterns are used to find the api endpoint for a given user for a given service.

    For example, *aitc-1.0 = {node}/1.0/{uid}* means that the api end point for the
    user of id **1** for the aitc service will be something like:

    http://some.node/1.0/1

    Variables that gets replaced:

    - node: the service node root url
    - uid: the user id for that service
    - service: the service name (name+version)


browserid
~~~~~~~~~
     **backend**
        The class used to verify a Browser-ID assertion

        Possible values:

        - :class:`tokenserver.verifiers.LocalVerifier`
        - :class:`tokenserver.verifiers.PowerHoseVerifier`

        See :ref:`verifiers` for more information.

    **audience**
        A whitelist of supported audience. "*" for all
