.. _library:

Token Server Library
--------------------

.. _verifiers:

Verifiers
=========

This backend is used to verify a BrowserID assertion.

.. autofunction:: tokenserver.verifiers.get_verifier

.. autoclass:: tokenserver.verifiers.LocalVerifier
   :members: verify,verify_certificate_chain,check_token_signature

.. autoclass:: tokenserver.verifiers.PowerHoseVerifier
   :members: verify, verify_certificate_chain,check_token_signature


.. _nodeassign:

Node assigners
==============

This backend is used to allocate or get a node for a service to a given user.


.. autoclass:: tokenserver.assignment.fixednode.DefaultNodeAssignmentBackend
   :members: get_node,allocate_node

.. autoclass:: tokenserver.assignment.sqlnode.SQLNodeAssignment
   :members: get_node,allocate_node

.. autoclass:: tokenserver.assignment.sqlnode.ShardedSQLNodeAssignment
   :members: get_node,allocate_node

.. autoclass:: tokenserver.assignment.sqlnode.SecuredShardedSQLNodeAssignment
   :members: get_node,allocate_node

