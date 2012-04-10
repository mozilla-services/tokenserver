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


endpoint
~~~~~~~~
    List of patterns for the api endpoints. The variable is the application name,
    the value is the pattern. When this section is not provided, and an SQL
    backend is provided, fall backs to using the patterns table in the SQL DB.

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
