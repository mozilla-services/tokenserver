# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import math
import os
import time
import unittest
import uuid
from collections import defaultdict
from sqlalchemy.sql import text as sqltext
from mozsvc.exceptions import BackendError
from tokenserver.assignment.sqlnode.sql import (SQLNodeAssignment,
                                                MAX_GENERATION,
                                                get_timestamp)


TEMP_ID = uuid.uuid4().hex
DEFAULT_SQLURI = 'sqlite:////tmp/tokenserver.' + TEMP_ID


class NodeAssignmentTests(object):

    backend = None  # subclasses must define this on the instance

    def setUp(self):
        super(NodeAssignmentTests, self).setUp()
        self.backend.add_service('sync-1.0', '{node}/1.0/{uid}')
        self.backend.add_service('sync-1.5', '{node}/1.5/{uid}')
        self.backend.add_service('queuey-1.0', '{node}/{service}/{uid}')
        self.backend.add_node('sync-1.0', 'https://phx12', 100)

    def test_node_allocation(self):
        user = self.backend.get_user("sync-1.0", "test1@example.com")
        self.assertEquals(user, None)

        user = self.backend.allocate_user("sync-1.0", "test1@example.com")
        wanted = 'https://phx12'
        self.assertEqual(user['node'], wanted)

        user = self.backend.get_user("sync-1.0", "test1@example.com")
        self.assertEqual(user['node'], wanted)

    def test_allocation_to_least_loaded_node(self):
        self.backend.add_node('sync-1.0', 'https://phx13', 100)
        user1 = self.backend.allocate_user("sync-1.0", "test1@mozilla.com")
        user2 = self.backend.allocate_user("sync-1.0", "test2@mozilla.com")
        self.assertNotEqual(user1['node'], user2['node'])

    def test_allocation_is_not_allowed_to_downed_nodes(self):
        self.backend.update_node('sync-1.0', 'https://phx12', downed=True)
        with self.assertRaises(BackendError):
            self.backend.allocate_user("sync-1.0", "test1@mozilla.com")

    def test_allocation_is_not_allowed_to_backof_nodes(self):
        self.backend.update_node('sync-1.0', 'https://phx12', backoff=True)
        with self.assertRaises(BackendError):
            self.backend.allocate_user("sync-1.0", "test1@mozilla.com")

    def test_update_generation_number(self):
        user = self.backend.allocate_user("sync-1.0", "test1@example.com")
        self.assertEqual(user['generation'], 0)
        self.assertEqual(user['client_state'], '')
        orig_uid = user['uid']
        orig_node = user['node']

        # Changing generation should leave other properties unchanged.
        self.backend.update_user("sync-1.0", user, generation=42)
        self.assertEqual(user['uid'], orig_uid)
        self.assertEqual(user['node'], orig_node)
        self.assertEqual(user['generation'], 42)
        self.assertEqual(user['client_state'], '')

        user = self.backend.get_user("sync-1.0", "test1@example.com")
        self.assertEqual(user['uid'], orig_uid)
        self.assertEqual(user['node'], orig_node)
        self.assertEqual(user['generation'], 42)
        self.assertEqual(user['client_state'], '')

        # It's not possible to move generation number backwards.
        self.backend.update_user("sync-1.0", user, generation=17)
        self.assertEqual(user['uid'], orig_uid)
        self.assertEqual(user['node'], orig_node)
        self.assertEqual(user['generation'], 42)
        self.assertEqual(user['client_state'], '')

        user = self.backend.get_user("sync-1.0", "test1@example.com")
        self.assertEqual(user['uid'], orig_uid)
        self.assertEqual(user['node'], orig_node)
        self.assertEqual(user['generation'], 42)
        self.assertEqual(user['client_state'], '')

    def test_update_client_state(self):
        user = self.backend.allocate_user("sync-1.0", "test1@example.com")
        self.assertEqual(user['generation'], 0)
        self.assertEqual(user['client_state'], '')
        self.assertEqual(set(user['old_client_states']), set(()))
        seen_uids = set((user['uid'],))
        orig_node = user['node']

        # Changing client-state allocates a new userid.
        self.backend.update_user("sync-1.0", user, client_state="aaa")
        self.assertTrue(user['uid'] not in seen_uids)
        self.assertEqual(user['node'], orig_node)
        self.assertEqual(user['generation'], 0)
        self.assertEqual(user['client_state'], 'aaa')
        self.assertEqual(set(user['old_client_states']), set(("",)))

        user = self.backend.get_user("sync-1.0", "test1@example.com")
        self.assertTrue(user['uid'] not in seen_uids)
        self.assertEqual(user['node'], orig_node)
        self.assertEqual(user['generation'], 0)
        self.assertEqual(user['client_state'], 'aaa')
        self.assertEqual(set(user['old_client_states']), set(("",)))

        seen_uids.add(user['uid'])

        # It's possible to change client-state and generation at once.
        self.backend.update_user("sync-1.0", user,
                                 client_state="bbb", generation=12)
        self.assertTrue(user['uid'] not in seen_uids)
        self.assertEqual(user['node'], orig_node)
        self.assertEqual(user['generation'], 12)
        self.assertEqual(user['client_state'], 'bbb')
        self.assertEqual(set(user['old_client_states']), set(("", "aaa")))

        user = self.backend.get_user("sync-1.0", "test1@example.com")
        self.assertTrue(user['uid'] not in seen_uids)
        self.assertEqual(user['node'], orig_node)
        self.assertEqual(user['generation'], 12)
        self.assertEqual(user['client_state'], 'bbb')
        self.assertEqual(set(user['old_client_states']), set(("", "aaa")))

        # You can't got back to an old client_state.
        orig_uid = user['uid']
        with self.assertRaises(BackendError):
            self.backend.update_user("sync-1.0", user, client_state="aaa")

        user = self.backend.get_user("sync-1.0", "test1@example.com")
        self.assertEqual(user['uid'], orig_uid)
        self.assertEqual(user['node'], orig_node)
        self.assertEqual(user['generation'], 12)
        self.assertEqual(user['client_state'], 'bbb')
        self.assertEqual(set(user['old_client_states']), set(("", "aaa")))

    def test_user_retirement(self):
        self.backend.allocate_user("sync-1.0", "test@mozilla.com")
        user1 = self.backend.get_user("sync-1.0", "test@mozilla.com")
        self.backend.retire_user("test@mozilla.com")
        user2 = self.backend.get_user("sync-1.0", "test@mozilla.com")
        self.assertTrue(user2["generation"] > user1["generation"])

    def test_cleanup_of_old_records(self):
        service = "sync-1.0"
        # Create 6 user records for the first user.
        # Do a sleep halfway through so we can test use of grace period.
        email1 = "test1@mozilla.com"
        user1 = self.backend.allocate_user(service, email1)
        self.backend.update_user(service, user1, client_state="a")
        self.backend.update_user(service, user1, client_state="b")
        self.backend.update_user(service, user1, client_state="c")
        break_time = time.time()
        time.sleep(0.1)
        self.backend.update_user(service, user1, client_state="d")
        self.backend.update_user(service, user1, client_state="e")
        records = list(self.backend.get_user_records(service, email1))
        self.assertEqual(len(records), 6)
        # Create 3 user records for the second user.
        email2 = "test2@mozilla.com"
        user2 = self.backend.allocate_user(service, email2)
        self.backend.update_user(service, user2, client_state="a")
        self.backend.update_user(service, user2, client_state="b")
        records = list(self.backend.get_user_records(service, email2))
        self.assertEqual(len(records), 3)
        # That should be a total of 7 old records.
        old_records = list(self.backend.get_old_user_records(service, 0))
        self.assertEqual(len(old_records), 7)
        # The 'limit' parameter should be respected.
        old_records = list(self.backend.get_old_user_records(service, 0, 2))
        self.assertEqual(len(old_records), 2)
        # The default grace period is too big to pick them up.
        old_records = list(self.backend.get_old_user_records(service))
        self.assertEqual(len(old_records), 0)
        # The grace period can select a subset of the records.
        grace = time.time() - break_time
        old_records = list(self.backend.get_old_user_records(service, grace))
        self.assertEqual(len(old_records), 3)
        # Old records can be successfully deleted:
        for record in old_records:
            self.backend.delete_user_record(service, record.uid)
        old_records = list(self.backend.get_old_user_records(service, 0))
        self.assertEqual(len(old_records), 4)

    def test_node_reassignment_when_records_are_replaced(self):
        self.backend.allocate_user("sync-1.0", "test@mozilla.com",
                                   generation=42, client_state="aaa")
        user1 = self.backend.get_user("sync-1.0", "test@mozilla.com")
        self.backend.replace_user_records("sync-1.0", "test@mozilla.com")
        user2 = self.backend.get_user("sync-1.0", "test@mozilla.com")
        self.assertNotEqual(user2["uid"], user1["uid"])
        self.assertEqual(user2["generation"], user1["generation"])
        self.assertEqual(user2["client_state"], user1["client_state"])

    def test_node_reassignment_not_done_for_retired_users(self):
        self.backend.allocate_user("sync-1.0", "test@mozilla.com",
                                   generation=42, client_state="aaa")
        user1 = self.backend.get_user("sync-1.0", "test@mozilla.com")
        self.backend.retire_user("test@mozilla.com")
        user2 = self.backend.get_user("sync-1.0", "test@mozilla.com")
        self.assertEqual(user2["uid"], user1["uid"])
        self.assertEqual(user2["generation"], MAX_GENERATION)
        self.assertEqual(user2["client_state"], user2["client_state"])

    def test_recovery_from_racy_record_creation(self):
        timestamp = get_timestamp()
        # Simulate race for forcing creation of two rows with same timestamp.
        user1 = self.backend.allocate_user("sync-1.0", "test@mozilla.com",
                                           timestamp=timestamp)
        user2 = self.backend.allocate_user("sync-1.0", "test@mozilla.com",
                                           timestamp=timestamp)
        self.assertNotEqual(user1["uid"], user2["uid"])
        # Neither is marked replaced initially.
        old_records = list(self.backend.get_old_user_records("sync-1.0", 0))
        self.assertEqual(len(old_records), 0)
        # Reading current details will detect the problem and fix it.
        self.backend.get_user("sync-1.0", "test@mozilla.com")
        old_records = list(self.backend.get_old_user_records("sync-1.0", 0))
        self.assertEqual(len(old_records), 1)

    def test_that_race_recovery_respects_generation_number_monotonicity(self):
        timestamp = get_timestamp()
        # Simulate race between clients with different generation numbers,
        # in which the out-of-date client gets a higher timestamp.
        user1 = self.backend.allocate_user("sync-1.0", "test@mozilla.com",
                                           generation=1, timestamp=timestamp)
        user2 = self.backend.allocate_user("sync-1.0", "test@mozilla.com",
                                           generation=2,
                                           timestamp=timestamp - 1)
        self.assertNotEqual(user1["uid"], user2["uid"])
        # Reading current details should promote the higher-generation one.
        user = self.backend.get_user("sync-1.0", "test@mozilla.com")
        self.assertEqual(user["generation"], 2)
        self.assertEqual(user["uid"], user2["uid"])
        # And the other record should get marked as replaced.
        old_records = list(self.backend.get_old_user_records("sync-1.0", 0))
        self.assertEqual(len(old_records), 1)

    def test_node_reassignment_and_removal(self):
        NODE1 = "https://phx12"
        NODE2 = "https://phx13"
        # note that NODE1 is created by default for all tests.
        self.backend.add_node("sync-1.0", NODE2, 100)
        # Assign four users, we should get two on each node.
        user1 = self.backend.allocate_user("sync-1.0", "test1@mozilla.com")
        user2 = self.backend.allocate_user("sync-1.0", "test2@mozilla.com")
        user3 = self.backend.allocate_user("sync-1.0", "test3@mozilla.com")
        user4 = self.backend.allocate_user("sync-1.0", "test4@mozilla.com")
        node_counts = defaultdict(lambda: 0)
        for user in (user1, user2, user3, user4):
            node_counts[user["node"]] += 1
        self.assertEqual(node_counts[NODE1], 2)
        self.assertEqual(node_counts[NODE2], 2)
        # Clear the assignments for NODE1, and re-assign.
        # The users previously on NODE1 should balance across both nodes,
        # giving 1 on NODE1 and 3 on NODE2.
        self.backend.unassign_node("sync-1.0", NODE1)
        node_counts = defaultdict(lambda: 0)
        for user in (user1, user2, user3, user4):
            new_user = self.backend.get_user("sync-1.0", user["email"])
            if user["node"] == NODE2:
                self.assertEqual(new_user["node"], NODE2)
            node_counts[new_user["node"]] += 1
        self.assertEqual(node_counts[NODE1], 1)
        self.assertEqual(node_counts[NODE2], 3)
        # Remove NODE2.  Everyone should wind up on NODE1.
        self.backend.remove_node("sync-1.0", NODE2)
        for user in (user1, user2, user3, user4):
            new_user = self.backend.get_user("sync-1.0", user["email"])
            self.assertEqual(new_user["node"], NODE1)
        # The old users records pointing to NODE2 should have a NULL 'node'
        # property since it has been removed from the db.
        null_node_count = 0
        for row in self.backend.get_old_user_records("sync-1.0", 0):
            if row.node is None:
                null_node_count += 1
            else:
                self.assertEqual(row.node, NODE1)
        self.assertEqual(null_node_count, 3)

    def test_that_race_recovery_respects_generation_after_reassignment(self):
        timestamp = get_timestamp()
        # Simulate race between clients with different generation numbers,
        # in which the out-of-date client gets a higher timestamp.
        user1 = self.backend.allocate_user("sync-1.0", "test@mozilla.com",
                                           generation=1, timestamp=timestamp)
        user2 = self.backend.allocate_user("sync-1.0", "test@mozilla.com",
                                           generation=2,
                                           timestamp=timestamp - 1)
        self.assertNotEqual(user1["uid"], user2["uid"])
        # Force node re-assignment by marking all records as replaced.
        self.backend.replace_user_records("sync-1.0", "test@mozilla.com",
                                          timestamp=timestamp + 1)
        # The next client to show up should get a new assignment, marked
        # with the correct generation number.
        user = self.backend.get_user("sync-1.0", "test@mozilla.com")
        self.assertEqual(user["generation"], 2)
        self.assertNotEqual(user["uid"], user1["uid"])
        self.assertNotEqual(user["uid"], user2["uid"])

    def test_that_we_can_allocate_users_to_a_specific_node(self):
        node = "https://phx13"
        self.backend.add_node('sync-1.0', node, 50)
        # The new node is not selected by default, because of lower capacity.
        user = self.backend.allocate_user("sync-1.0", "test1@mozilla.com")
        self.assertNotEqual(user["node"], node)
        # But we can force it using keyword argument.
        user = self.backend.allocate_user("sync-1.0", "test2@mozilla.com",
                                          node=node)
        self.assertEqual(user["node"], node)

    def test_that_we_can_move_users_to_a_specific_node(self):
        node = "https://phx13"
        self.backend.add_node('sync-1.0', node, 50)
        # The new node is not selected by default, because of lower capacity.
        user = self.backend.allocate_user("sync-1.0", "test@mozilla.com")
        self.assertNotEqual(user["node"], node)
        # But we can move them there explicitly using keyword argument.
        self.backend.update_user("sync-1.0", user, node=node)
        self.assertEqual(user["node"], node)
        # Sanity-check by re-reading it from the db.
        user = self.backend.get_user("sync-1.0", "test@mozilla.com")
        self.assertEqual(user["node"], node)
        # Check that it properly respects client-state and generation.
        self.backend.update_user("sync-1.0", user, generation=12)
        self.backend.update_user("sync-1.0", user, client_state="XXX")
        self.backend.update_user("sync-1.0", user, generation=42,
                                 client_state="YYY", node="https://phx12")
        self.assertEqual(user["node"], "https://phx12")
        self.assertEqual(user["generation"], 42)
        self.assertEqual(user["client_state"], "YYY")
        self.assertEqual(sorted(user["old_client_states"]), ["", "XXX"])
        # Sanity-check by re-reading it from the db.
        user = self.backend.get_user("sync-1.0", "test@mozilla.com")
        self.assertEqual(user["node"], "https://phx12")
        self.assertEqual(user["generation"], 42)
        self.assertEqual(user["client_state"], "YYY")
        self.assertEqual(sorted(user["old_client_states"]), ["", "XXX"])

    def test_that_record_cleanup_frees_slots_on_the_node(self):
        service = "sync-1.0"
        node = "https://phx12"
        self.backend.update_node(service, node, capacity=10, available=1,
                                 current_load=9)
        # We should only be able to allocate one more user to that node.
        user = self.backend.allocate_user(service, "test1@mozilla.com")
        self.assertEqual(user["node"], node)
        with self.assertRaises(BackendError):
            self.backend.allocate_user(service, "test2@mozilla.com")
        # But when we clean up the user's record, it frees up the slot.
        self.backend.retire_user("test1@mozilla.com")
        self.backend.delete_user_record(service, user["uid"])
        user = self.backend.allocate_user(service, "test2@mozilla.com")
        self.assertEqual(user["node"], node)

    def test_gradual_release_of_node_capacity(self):
        service = "sync-1.0"
        node1 = "https://phx12"
        self.backend.update_node(service, node1, capacity=8, available=1,
                                 current_load=4)
        node2 = "https://phx13"
        self.backend.add_node(service, node2, capacity=6, available=1,
                              current_load=4)
        # Two allocations should succeed without update, one on each node.
        user = self.backend.allocate_user(service, "test1@mozilla.com")
        self.assertEqual(user["node"], node1)
        user = self.backend.allocate_user(service, "test2@mozilla.com")
        self.assertEqual(user["node"], node2)
        # The next allocation attempt will release 10% more capacity,
        # which is one more slot for each node.
        user = self.backend.allocate_user(service, "test3@mozilla.com")
        self.assertEqual(user["node"], node1)
        user = self.backend.allocate_user(service, "test4@mozilla.com")
        self.assertEqual(user["node"], node2)
        # Now node2 is full, so further allocations all go to node1.
        user = self.backend.allocate_user(service, "test5@mozilla.com")
        self.assertEqual(user["node"], node1)
        user = self.backend.allocate_user(service, "test6@mozilla.com")
        self.assertEqual(user["node"], node1)
        # Until it finally reaches capacity.
        with self.assertRaises(BackendError):
            self.backend.allocate_user(service, "test7@mozilla.com")

    def test_count_users(self):
        user = self.backend.allocate_user("sync-1.0", "test1@example.com")
        self.assertEqual(self.backend.count_users(), 1)
        old_timestamp = get_timestamp()
        time.sleep(0.01)
        # Adding users increases the count.
        user = self.backend.allocate_user("sync-1.0", "rfkelly@mozilla.com")
        self.assertEqual(self.backend.count_users(), 2)
        # Updating a user doesn't change the count.
        self.backend.update_user("sync-1.0", user, client_state="aaa")
        self.assertEqual(self.backend.count_users(), 2)
        # Looking back in time doesn't count newer users.
        self.assertEqual(self.backend.count_users(old_timestamp), 1)
        # Retiring a user decreases the count.
        self.backend.retire_user("test1@example.com")
        self.assertEqual(self.backend.count_users(), 1)

    def test_first_seen_at(self):
        SERVICE = "sync-1.0"
        EMAIL = "test1@example.com"
        user0 = self.backend.allocate_user(SERVICE, EMAIL)
        user1 = self.backend.get_user(SERVICE, EMAIL)
        self.assertEqual(user1["uid"], user0["uid"])
        self.assertEqual(user1["first_seen_at"], user0["first_seen_at"])
        # It should stay consistent if we re-allocate the user's node.
        time.sleep(0.1)
        self.backend.update_user(SERVICE, user1, client_state="aaa")
        user2 = self.backend.get_user(SERVICE, EMAIL)
        self.assertNotEqual(user2["uid"], user0["uid"])
        self.assertEqual(user2["first_seen_at"], user0["first_seen_at"])
        # Until we purge their old node-assignment records.
        self.backend.delete_user_record(SERVICE, user0["uid"])
        user3 = self.backend.get_user(SERVICE, EMAIL)
        self.assertEqual(user3["uid"], user2["uid"])
        self.assertNotEqual(user3["first_seen_at"], user2["first_seen_at"])


class TestSQLDB(NodeAssignmentTests, unittest.TestCase):

    _SQLURI = os.environ.get('MOZSVC_SQLURI', DEFAULT_SQLURI)

    def setUp(self):
        self.backend = SQLNodeAssignment(self._SQLURI, create_tables=True)
        super(TestSQLDB, self).setUp()

    def tearDown(self):
        super(TestSQLDB, self).tearDown()
        if self.backend._engine.driver == 'pysqlite':
            filename = self.backend.sqluri.split('sqlite://')[-1]
            if os.path.exists(filename):
                os.remove(filename)
        else:
            self.backend._safe_execute('drop table services;')
            self.backend._safe_execute('drop table nodes;')
            self.backend._safe_execute('drop table users;')

    def test_default_node_available_capacity(self):
        node = "https://phx13"
        self.backend.add_node("sync-1.0", node, capacity=100)
        available = int(math.ceil(self.backend.capacity_release_rate * 100))
        query = sqltext("SELECT * FROM nodes WHERE node=:node")
        res = self.backend._safe_execute(query, node=node)
        row = res.fetchone()
        res.close()
        self.assertEqual(row["available"], available)


if os.environ.get('MOZSVC_MYSQLURI', None) is not None:
    class TestMySQLDB(TestSQLDB):
        _SQLURI = os.environ.get('MOZSVC_MYSQLURI')
