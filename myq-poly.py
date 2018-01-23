#!/usr/bin/python3
# Polglot v2 Node Server for Chamberlain LiftMaster Garage Door Openers through MyQ Cloud Service

import sys
import re
import time
from myqapi import MyQ, DEVICE_TYPE_GARAGE_DOOR_OPENER, DEVICE_TYPE_GATEWAY
import polyinterface

_ISY_OPEN_CLOSE_UOM = 79 # 0=Open, 100=Closed
_ISY_BARRIER_STATUS_UOM = 97 # 0=Closed, 100=Open, 101=Unknown, 102=Stopped, 103=Closing, 104=Opening
_ISY_INDEX_UOM = 25 # Index UOM for custom door states below (must match editor/NLS in profile)
_ISY_BOOL_UOM =2 # Used for reporting status values for Controller node
_IX_GDO_ST_CLOSED = 0
_IX_GDO_ST_OPEN = 1
_IX_GDO_ST_STOPPED = 2
_IX_GDO_ST_CLOSING = 3
_IX_GDO_ST_OPENING = 4
_IX_GDO_ST_UNKNOWN = 9

_LOGGER = polyinterface.LOGGER

# Node for a garage door opener
class GarageDoorOpener(polyinterface.Node):

    id = "GARAGE_DOOR_OPENER"

    # Open Door
    def cmd_don(self, command):

        # Place the controller in active polling mode
        self.controller.active = True
        self.controller.last_active = time.time()

        if self.parent.myQConnection.open(self.address):
            self.setDriver("ST", _IX_GDO_ST_OPENING)
        else:
            _LOGGER.warning("Call to open() failed in DON command handler.")

    # Close Door
    def cmd_dof(self, command):

        # Place the controller in active polling mode
        self.controller.active = True
        self.controller.last_active = time.time()

        if self.parent.myQConnection.close(self.address):
            self.setDriver("ST", _IX_GDO_ST_CLOSING)
        else:
            _LOGGER.warning("Call to close() failed in DOF command handler.")

    # Update node states
    def query(self):

        _LOGGER.debug("Updating node states in GarageDoorOpener.query()...")

        # Update the node states and then report all driver values for node
        self.parent.update_node_states()
        self.reportDrivers()

    drivers = [{"driver": "ST", "value": _IX_GDO_ST_UNKNOWN, "uom": _ISY_INDEX_UOM}]
    commands = {
        "DON": cmd_don,
        "DOF": cmd_dof
    }

# Controller class
class Controller(polyinterface.Controller):

    id = "CONTROLLER"

    def __init__(self, poly):
        super(Controller, self).__init__(poly)
        self.name = "MyQ Service"
        self.myQConnection = None
        self.active_poll = 20
        self.inactive_poll = 60
        self.active = False
        self.last_active = 0
        self.last_poll = 0

    # Start the node server
    def start(self):

        _LOGGER.info("Started MyQ Node Server...")

        # get service credentials from custom configuration parameters
        try:
            customParams = self.polyConfig["customParams"]
            userName = customParams["username"]
            password = customParams["password"]
        except KeyError:
            _LOGGER.error("Missing MyQ service credentials in configuration.")
            raise

        # get polling intervals and ttl from custom configuration parameters
        try:
            ttl = int(customParams["tokenttl"])
        except (KeyError, ValueError):
            ttl = 1200
        try:
            self.active_poll = int(customParams["activeupdateinterval"])
        except (KeyError, ValueError):
            self.active_poll = 20
        try:
            self.inactive_poll = int(customParams["inactiveupdateinterval"])
        except (KeyError, ValueError):
            self.inactive_poll = 60

        # create a connection to the MyQ cloud service
        self.myQConnection = MyQ(userName, password, ttl, _LOGGER)

        # startup in active mode polling
        currentTime = time.time()
        self.active = True
        self.last_active = currentTime

    # Override query to perform status update from the MyQ service before reporting driver values
    def query(self):

        _LOGGER.debug("Updating node states in Controller.query()...")

        # Update the node states and force report of all driver values
        self.update_node_states(True)

    # called every longPoll seconds (default 30)
    def longPoll(self):

        pass

    # called every shortPoll seconds (default 10)
    def shortPoll(self):

        # if node server is not setup yet, return
        if self.myQConnection == None:
            return

        currentTime = time.time()

        # reset active flag if 5 minutes has passed
        if self.last_active < (currentTime - 300):
            self.active = False

        # check for elapsed polling interval
        if ((self.active and (currentTime - self.last_poll) >= self.active_poll) or
                (not self.active and (currentTime - self.last_poll) >= self.inactive_poll)):

            # update the node states
            _LOGGER.debug("Updating node states in Controller.shortPoll()...")
            self.update_node_states()

            self.last_poll = currentTime

    # update the state of all nodes from the MyQ service
    # Parameters:
    #   forceReport - force reporting of all driver values (for query)
    def update_node_states(self, forceReport=False):

        # initially set driver values for controller to false to reflect service connection is gone
        serviceStatus = 0
        gatewayOnline = 0

        # get device details from myQ service
        devices = self.myQConnection.get_device_list()
        if devices is None:
            _LOGGER.warning("get_device_list() returned no devices.")

        else:

            # If devices were returned, set the service status to True
            serviceStatus = 1

            for device in devices:

                if device["type"] == DEVICE_TYPE_GATEWAY:

                    # Update controller node state value
                    gatewayOnline = 1 if device["online"] else 0

                elif device["type"] == DEVICE_TYPE_GARAGE_DOOR_OPENER:

                    # if the node doesn't exist, create it
                    if device["id"] in self.nodes:
                        gdoNode = self.nodes[device["id"]]
                    else:
                        gdoNode = GarageDoorOpener(
                            self,
                            self.address,
                            device["id"],
                            get_valid_node_name(device["description"])
                        )
                        self.addNode(gdoNode)

                    # update the state value for the matching node
                    value = get_st_driver_value(device["state"])
                    gdoNode.setDriver("ST", value, True, forceReport)

                    # if a device state has a door in motion, set the active mode flag  (affects polling interval)
                    if value in [_IX_GDO_ST_CLOSING, _IX_GDO_ST_OPENING, _IX_GDO_ST_UNKNOWN]:
                        self.active = True
                        self.last_active = time.time()

        # Update the controller node states
        self.setDriver("GV0", serviceStatus, True, forceReport)
        self.setDriver("GV1", gatewayOnline, True, forceReport)

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV0", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV1", "value": 0, "uom": _ISY_BOOL_UOM}
    ]
    commands = {"QUERY": query}


# Converts state value from MyQ to custom door states setup in editor/NLS in profile:
#   0=Closed, 1=Open, 2=Stopped, 3=Closing, 4=Opening, 9=Unknown
def get_st_driver_value(state):
    if state == "1":    # open
        return _IX_GDO_ST_OPEN
    elif state == "2":  # closed
        return _IX_GDO_ST_CLOSED
    elif state == "3":  # stopped
        return _IX_GDO_ST_STOPPED
    elif state == "4":  # opening
        return _IX_GDO_ST_OPENING
    elif state == "5":  # closing
        return _IX_GDO_ST_CLOSING
    elif state == "8":  # moving
        return _IX_GDO_ST_UNKNOWN
    elif state == "9":  # open
        return _IX_GDO_ST_OPEN
    else:
        return _IX_GDO_ST_UNKNOWN

# Removes invalid charaters for ISY Node description
def get_valid_node_name(name):

    # Remove <>`~!@#$%^&*(){}[]?/\;:"'` characters from names
    return re.sub(r"[<>`~!@#$%^&*(){}[\]?/\\;:\"']+", "", name)

# Main function to establish Polyglot connection
if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface()
        polyglot.start()
        control = Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
