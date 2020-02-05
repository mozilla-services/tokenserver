# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""
    Table schema for Sqlite
"""
from tokenserver.assignment.sqlnode.schemas import (_UsersBase,
                                                    _NodesBase,
                                                    _SettingsBase,
                                                    Integer,
                                                    Column,
                                                    String,
                                                    _add,
                                                    declared_attr)

from tokenserver.assignment.sqlnode.schemas import get_cls   # NOQA


__all__ = (get_cls,)


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


class _SQLITESettingsBase(_SettingsBase):
    setting = Column(String(100), primary_key=True)

    @declared_attr
    def __table_args__(cls):
        return()


_add('dynamic_settings', _SQLITESettingsBase)
