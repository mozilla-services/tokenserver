from zope.interface import Interface


class INodeAssignment(Interface):

    def get_node(email, service):
        """Returns the node for the given email and user.

        If no mapping is found, return None.
        """

    def create_node(email, service, node):
        """Sets the node for the given email, service and node"""
