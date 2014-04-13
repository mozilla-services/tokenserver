# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""
    Table schema for Sqlite
"""
from tokenserver.assignment.sqlnode.schemas import (_UsersBase,
                                                    _NodesBase,
                                                    Integer,
                                                    Column,
                                                    _add,
                                                    declared_attr)

from tokenserver.assignment.sqlnode.schemas import get_cls   # NOQA


class _SQLITENodesBase(_NodesBase):
    id = Column(Integer, primary_key=True)

    @declared_attr
    def __table_args__(cls):
        return ()

_add('nodes', _SQLITENodesBase)


class _SQLITEUsersBase(_UsersBase):
    uid = Column(Integer, primary_key=True)

    @declared_attr
    def __table_args__(cls):
        return ()

_add('users', _SQLITEUsersBase)
