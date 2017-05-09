# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import json
import os
import unittest

from pyramid import testing
from testfixtures import LogCapture

from mozsvc.config import load_into_settings
from mozsvc.plugin import load_and_register

from tokenserver.scripts.process_account_events import process_account_event
from tokenserver.assignment import INodeAssignment


SERVICE = "sync-1.0"
EMAIL = "test@example.com"
UID = "test"
ISS = "example.com"


def message_body(**kwds):
    return json.dumps({
        "Message": json.dumps(kwds)
    })


class TestProcessAccountEvents(unittest.TestCase):

    def get_ini(self):
        return os.path.join(os.path.dirname(__file__),
                            'test_sql.ini')

    def setUp(self):
        self.config = testing.setUp()
        settings = {}
        load_into_settings(self.get_ini(), settings)
        self.config.add_settings(settings)
        self.config.include("tokenserver")
        load_and_register("tokenserver", self.config)
        self.backend = self.config.registry.getUtility(INodeAssignment)
        self.backend.add_service(SERVICE, "{node}/{version}/{uid}")
        self.backend.add_node(SERVICE, "https://phx12", 100)
        self.logs = LogCapture()

    def tearDown(self):
        self.logs.uninstall()
        testing.tearDown()
        if self.backend._engine.driver == 'pysqlite':
            filename = self.backend.sqluri.split('sqlite://')[-1]
            if os.path.exists(filename):
                os.remove(filename)
        else:
            self.backend._safe_execute('delete from services')
            self.backend._safe_execute('delete from nodes')
            self.backend._safe_execute('delete from users')

    def assertMessageWasLogged(self, msg):
        """Check that a metric was logged during the request."""
        for r in self.logs.records:
            if msg in r.getMessage():
                break
        else:
            assert False, "message %r was not logged" % (msg,)

    def clearLogs(self):
        del self.logs.records[:]

    def test_delete_user(self):
        self.backend.allocate_user(SERVICE, EMAIL)
        user = self.backend.get_user(SERVICE, EMAIL)
        self.backend.update_user(SERVICE, user, client_state="abcdef")
        records = list(self.backend.get_user_records(SERVICE, EMAIL))
        self.assertEquals(len(records), 2)
        self.assertTrue(records[0]["replaced_at"] is not None)

        process_account_event(self.config, message_body(
            event="delete",
            uid=UID,
            iss=ISS,
        ))

        records = list(self.backend.get_user_records(SERVICE, EMAIL))
        self.assertEquals(len(records), 2)
        for row in records:
            self.assertTrue(row["replaced_at"] is not None)

    def test_delete_user_by_legacy_uid_format(self):
        self.backend.allocate_user(SERVICE, EMAIL)
        user = self.backend.get_user(SERVICE, EMAIL)
        self.backend.update_user(SERVICE, user, client_state="abcdef")
        records = list(self.backend.get_user_records(SERVICE, EMAIL))
        self.assertEquals(len(records), 2)
        self.assertTrue(records[0]["replaced_at"] is not None)

        process_account_event(self.config, message_body(
            event="delete",
            uid=EMAIL,
        ))

        records = list(self.backend.get_user_records(SERVICE, EMAIL))
        self.assertEquals(len(records), 2)
        for row in records:
            self.assertTrue(row["replaced_at"] is not None)

    def test_delete_user_who_is_not_in_the_db(self):
        records = list(self.backend.get_user_records(SERVICE, EMAIL))
        self.assertEquals(len(records), 0)

        process_account_event(self.config, message_body(
            event="delete",
            uid=UID,
            iss=ISS
        ))

        records = list(self.backend.get_user_records(SERVICE, EMAIL))
        self.assertEquals(len(records), 0)

    def test_reset_user(self):
        self.backend.allocate_user(SERVICE, EMAIL, generation=12)

        process_account_event(self.config, message_body(
            event="reset",
            uid=UID,
            iss=ISS,
            generation=43,
        ))

        user = self.backend.get_user(SERVICE, EMAIL)
        self.assertEquals(user["generation"], 42)

    def test_reset_user_by_legacy_uid_format(self):
        self.backend.allocate_user(SERVICE, EMAIL, generation=12)

        process_account_event(self.config, message_body(
            event="reset",
            uid=EMAIL,
            generation=43,
        ))

        user = self.backend.get_user(SERVICE, EMAIL)
        self.assertEquals(user["generation"], 42)

    def test_reset_user_who_is_not_in_the_db(self):
        records = list(self.backend.get_user_records(SERVICE, EMAIL))
        self.assertEquals(len(records), 0)

        process_account_event(self.config, message_body(
            event="reset",
            uid=UID,
            iss=ISS,
            generation=43,
        ))

        records = list(self.backend.get_user_records(SERVICE, EMAIL))
        self.assertEquals(len(records), 0)

    def test_malformed_events(self):

        # Unknown event type.
        process_account_event(self.config, message_body(
            event="party",
            uid=UID,
            iss=ISS,
            generation=43,
        ))
        self.assertMessageWasLogged("Dropping unknown event type")
        self.clearLogs()

        # Missing event type.
        process_account_event(self.config, message_body(
            uid=UID,
            iss=ISS,
            generation=43,
        ))
        self.assertMessageWasLogged("Invalid account message")
        self.clearLogs()

        # Missing uid.
        process_account_event(self.config, message_body(
            event="delete",
            iss=ISS,
        ))
        self.assertMessageWasLogged("Invalid account message")
        self.clearLogs()

        # Missing generation for reset events.
        process_account_event(self.config, message_body(
            event="reset",
            uid=UID,
            iss=ISS,
        ))
        self.assertMessageWasLogged("Invalid account message")
        self.clearLogs()

        # Missing issuer with nonemail uid
        process_account_event(self.config, message_body(
            event="delete",
            uid=UID,
        ))
        self.assertMessageWasLogged("Invalid account message")
        self.clearLogs()

        # Non-JSON garbage.
        process_account_event(self.config, "wat")
        self.assertMessageWasLogged("Invalid account message")
        self.clearLogs()

        # Non-JSON garbage in Message field.
        process_account_event(self.config, '{ "Message": "wat" }')
        self.assertMessageWasLogged("Invalid account message")
        self.clearLogs()

        # Badly-typed JSON value in Message field.
        process_account_event(self.config, '{ "Message": "[1, 2, 3"] }')
        self.assertMessageWasLogged("Invalid account message")
        self.clearLogs()
