from zope.interface import Interface


class INodeAssignment(Interface):

    def get_node(self, email, service):
        """Returns the node for the given email and user.

        If no mapping is found, return None.
        """

    def allocate_node(self, email, service):
        """Sets the node for the given email, service and node"""
