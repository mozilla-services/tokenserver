from zope.interface import Interface


class INodeAssignment(Interface):
    """Interface definition for backend node-assignment db."""

    def lucky_user(self):
        """Determine if this is one of the lucky users to get routed to spanner

        """

    def get_user(self, service, email):
        """Returns the user record for the given service and email.

        The returned object will be None if no service record exists for that
        email, otherwise it will be an object with the following fields:

          * email:  the email address, as given to this method
          * uid:  integer userid assigned to that email
          * node:  service node assigned to that email, or None
          * generation:  the last-seen generation number for that email
          * client_state:  the last-seen client state string for that email
          * old_client_states:  any previously--seen client state strings
          * migration_state: one of None, "MIGRATING", "MIGRATED", where
            a state of "MIGRATING" should cause a 501 return. 

        """

    def allocate_user(self, service, email, generation=0, client_state='',
                      keys_changed_at=0, node=None):
        """Create a new user record for the given service and email.

        The newly-created user record is returned in the format described
        for the get_user() method.
        """

    def update_user(self, service, user, generation=None, client_state=None,
                    keys_changed_at=None, node=None):
        """Update the user record for the given service.

        This method can be used to update the last-seen generation number,
        client-state string or node assignment for a user.  Changing the
        client-state or node will result in a new uid being generated.

        The given user object is modified in-place to reflect the changes
        stored on the backend.
        """
