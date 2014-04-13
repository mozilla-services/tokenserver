from zope.interface import Interface


class INodeAssignment(Interface):
    """Interface definition for backend node-assignment db."""

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

        """

    def allocate_user(self, service, email, generation=0, client_state=''):
        """Create a new user record for the given service and email.

        The newly-created user record is returned in the format described
        for the get_user() method.
        """

    def update_user(self, service, user, generation=None, client_state=None):
        """Update the user record for the given service.

        This method can be used to update the last-seen generation number
        and/or client-state string for a user.  Changing the client-state
        string will also result in a new uid being generated.

        The given user object is modified in-place to reflect the changes
        stored on the backend.
        """
