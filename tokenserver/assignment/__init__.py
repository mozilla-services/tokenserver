from zope.interface import Interface


class INodeAssignment(Interface):

    def get_node(self, email, service):
        """Returns the node for the given email and user.

        If no mapping is found, return None.
        """

    def allocate_node(email, service):
        """Sets the node for the given email, service and node"""

    def set_metadata(service, name, value, needs_acceptance=False):
        """ """

    def get_metadata(service, name=None, needs_acceptance=None):
        """ """

    def set_accepted_conditions_flag(service, value, email=None):
        """ """
