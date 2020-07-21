#!/usr/bin/python3
"""
Polglot v2 NodeServer for Chamberlain LiftMaster Garage Door Openers through MyQ Cloud Service
by Goose66 (W. Randy King) kingwrandy@gmail.com
"""
try:
    import polyinterface
except ImportError:
    import pgc_interface as polyinterface
import sys
import re
import time
from myqapi import MyQ, API_DEVICE_TYPE_GATEWAY, API_DEVICE_TYPE_OPENER, API_DEVICE_TYPE_LAMP, API_DEVICE_STATE_OPEN, API_DEVICE_STATE_CLOSED, API_DEVICE_STATE_STOPPED, API_DEVICE_STATE_OPENING, API_DEVICE_STATE_CLOSING, API_DEVICE_STATE_ON, API_DEVICE_STATE_OFF, API_LOGIN_BAD_AUTHENTICATION, API_LOGIN_ERROR, API_LOGIN_SUCCESS

LOGGER = polyinterface.LOGGER

ISY_OPEN_CLOSE_UOM = 79 # 0=Open, 100=Closed
ISY_BARRIER_STATUS_UOM = 97 # 0=Closed, 100=Open, 101=Unknown, 102=Stopped, 103=Closing, 104=Opening
ISY_INDEX_UOM = 25 # Index UOM for custom door states below (must match editor/NLS in profile)
ISY_BOOL_UOM = 2 # Used for reporting status values for Controller and Gateway nodes
ISY_SECONDS_UOM = 58 # Used for incrementally reporting state timer
ISY_MINUTES_UOM = 45 # Used for incrementally reporting state timer
ISY_HOURS_UOM = 45 # Used for incrementally reporting state timer
ISY_ON_OFF_UOM = 78 # For non-dimmable light: 0-Off 100-On
IX_GDO_ST_CLOSED = 0
IX_GDO_ST_OPEN = 1
IX_GDO_ST_STOPPED = 2
IX_GDO_ST_CLOSING = 3
IX_GDO_ST_OPENING = 4
IX_GDO_ST_UNKNOWN = 9
IX_LIGHT_ON = 100
IX_LIGHT_OFF = 0
IX_LIGHT_UNKNOWN = -1

# custom parameter values for this nodeserver
PARAM_USERNAME = "username"
PARAM_PASSWORD = "password"
PARAM_TOKEN_TTL = "tokenTTL"
DEFAULT_TOKEN_TTL = 1200
PARAM_ACTIVE_UPDATE_INTERVAL = "activeupdateinterval"
DEFAULT_ACTIVE_UPDATE_INTERVAL = 10
PARAM_INACTIVE_UPDATE_INTERVAL = "inactiveupdateinterval"
DEFAULT_INACTIVE_UPDATE_INTERVAL = 60

ACTIVE_UPDATE_DURATION = 300 # 5 minutes of active polling and then switch to inactive

# Node for MyQ device - wrapper device to handle device ID
class MyQ_Device(polyinterface.Node):

    _deviceID = ""

    def __init__(self, controller, primary, addr, name, deviceID=None):
        super(MyQ_Device, self).__init__(controller, primary, addr, name)
    
        # override the parent node with the primary (gateway) node (defaults to controller)
        self.parent = self.controller.nodes[self.primary]

        if deviceID is None:

            # retrieve the deviceID from polyglot custom data
            cData = controller.getCustomData(addr)
            self._deviceID = cData

        else:
            self._deviceID = deviceID

            # store instance variables in polyglot custom data
            cData = self._deviceID
            controller.addCustomData(addr, cData)

# Node for a garage door opener
class Gateway(MyQ_Device):

    id = "GATEWAY"
    hint = [0x01, 0x0e, 0x10, 0x00] # Residential/Gateway

    drivers = [
        {"driver": "ST", "value": 0, "uom": ISY_BOOL_UOM}
    ]

# Node for a garage door opener
class GarageDoorOpener(MyQ_Device):

    id = "GARAGE_DOOR_OPENER"
    hint = [0x01, 0x12, 0x01, 0x00] # Residential/Barrier/Garage Door Opener

    # Open Door
    def cmd_don(self, command):

        LOGGER.info("Opening door for %s in DON command handler.", self.name)

        # Place the controller in active polling mode
        self.controller.setActiveMode()

        if self.parent.myQConnection.open(self._deviceID):
            self.setDriver("ST", IX_GDO_ST_OPENING)
        else:
            LOGGER.warning("Call to open() failed in DON command handler.")

    # Close Door
    def cmd_dof(self, command):

        LOGGER.info("Closing door for %s in DOF command handler.", self.name)

        # Place the controller in active polling mode
        self.controller.setActiveMode()

        if self.parent.myQConnection.close(self._deviceID):
            self.setDriver("ST", IX_GDO_ST_CLOSING)
        else:
            LOGGER.warning("Call to close() failed in DOF command handler.")

    drivers = [
        {"driver": "ST", "value": IX_GDO_ST_UNKNOWN, "uom": ISY_INDEX_UOM},
        {"driver": "GV0", "value": 0, "uom": ISY_SECONDS_UOM},
    ]
    commands = {
        "DON": cmd_don,
        "DOF": cmd_dof
    }

# Node for a non-dimming light module
class Light(MyQ_Device):

    id = "LIGHT" 
    hint = [0x01, 0x02, 0x10, 0x00] # Residential/Controller/Non-Dimming Light

    # Turn on the light
    def cmd_don(self, command):

        LOGGER.infor("Turn on light %s in DON command handler.", self.name)

        # Place the controller in active polling mode
        self.controller.setActiveMode()

        if self.parent.myQConnection.turnOn(self._deviceID):
            self.setDriver("ST", IX_LIGHT_ON)
        else:
            LOGGER.warning("Call to turnOn() failed in DON command handler.")


    # Turn off the light
    def cmd_dof(self, command):

        LOGGER.infor("Turn off light %s in DOF command handler.", self.name)

        # Place the controller in active polling mode
        self.controller.setActiveMode()

        if self.parent.myQConnection.turnOff(self._deviceID):
            self.setDriver("ST", IX_LIGHT_OFF)
        else:
            LOGGER.warning("Call to turnOff() failed in DOF command handler.")

    drivers = [
        {"driver": "ST", "value": 0, "uom": ISY_ON_OFF_UOM}
    ]
    commands = {
        "DON": cmd_don,
        "DFON": cmd_don,
        "DOF": cmd_dof,
        "DFOF": cmd_dof
    }

# Controller class
class Controller(polyinterface.Controller):

    id = "CONTROLLER"
    _customData = {}
    _active_poll = 0
    _inactive_poll = 0
    _activePolling = False
    _last_active = 0
    _last_poll = 0
    myQConnection = None

    def __init__(self, poly):
        super(Controller, self).__init__(poly)
        self.name = "MyQ Service"

    # Start the node server
    def start(self):

        LOGGER.info("Started MyQ Node Server...")

        # load custom data from polyglot
        self._customData = self.polyConfig["customData"]
        
        # If a logger level was stored for the controller, then use to set the logger level
        level = self.getCustomData("loggerlevel")
        if level is not None:
            LOGGER.setLevel(int(level))
        
        # remove all existing notices for the nodeserver
        self.removeNoticesAll()

        # get the MyQ account credentials from custom configuration parameters
        try:
            customParams = self.polyConfig["customParams"]
            userName = customParams[PARAM_USERNAME]
            password = customParams[PARAM_PASSWORD]
        except KeyError:
            LOGGER.warning("Missing MyQ service credentials in configuration.")
            self.addNotice("The MyQ account credentials are missing in the configuration. Please check that both the 'username' and 'password' parameter values are specified in the Custom Configuration Parameters and restart the nodeserver.")
            self.addCustomParam({PARAM_USERNAME: "<email address>", PARAM_PASSWORD: "<password>"})
            return

        # get remaining optional custom parameters 
        ttl = int(customParams.get(PARAM_TOKEN_TTL, DEFAULT_TOKEN_TTL))
        self._active_poll = int(customParams.get(PARAM_ACTIVE_UPDATE_INTERVAL, DEFAULT_ACTIVE_UPDATE_INTERVAL))
        self._inactive_poll = int(customParams.get(PARAM_INACTIVE_UPDATE_INTERVAL, DEFAULT_INACTIVE_UPDATE_INTERVAL))

        # create a connection to the MyQ cloud service
        conn = MyQ(ttl, LOGGER)

        # login using the provided credentials
        rc = conn.loginToService(userName, password)
        if rc == API_LOGIN_BAD_AUTHENTICATION:
            LOGGER.warning("Bad username or password specified.")
            self.addNotice("Could not login to the MyQ service with the specified credentials. Please check the 'username' and 'password' parameter values in the Custom Configuration Parameters and restart the nodeserver.")
            return
        elif rc == API_LOGIN_ERROR:
            LOGGER.error("Error logging into MyQ service.")
            return

        # load nodes previously saved to the polyglot database
        # Note: has to be done in two passes to ensure system (primary/parent) nodes exist
        # before device nodes
        # first pass for gateway nodes
        for addr in self._nodes:           
            node = self._nodes[addr]
            if node["node_def_id"] == "GATEWAY":
                
                LOGGER.info("Adding previously saved node - addr: %s, name: %s, type: %s", addr, node["name"], node["node_def_id"])
                self.addNode(Gateway(self, node["primary"], addr, node["name"]))

        # second pass for device nodes
        for addr in self._nodes:         
            node = self._nodes[addr]    
            if node["node_def_id"] not in ("CONTROLLER", "GATEWAY"):

                LOGGER.info("Adding previously saved node - addr: %s, name: %s, type: %s", addr, node["name"], node["node_def_id"])

                # add device and temperature controller nodes
                if node["node_def_id"] == "GARAGE_DOOR_OPENER":
                    self.addNode(GarageDoorOpener(self, self.address, addr, node["name"]))
                if node["node_def_id"] == "LIGHT":
                    self.addNode(Light(self, self.address, addr, node["name"]))

        # set the object level connection variable
        self.myQConnection = conn

        # Set the nodeserver status flag to indicate nodeserver is running
        self.setDriver("ST", 1, True, True)

        # Report the logger level to the ISY
        self.setDriver("GV20", LOGGER.level, True, True)
 
        # update the driver values of all nodes (force report)
        self.updateNodeStates(True)

        # startup in active mode polling
        self.setActivePolling()

    # shutdown the nodeserver on stop
    def stop(self):
        if self.myQConnection is not None:
            self.myQConnection.disconnect()

        # Set the nodeserver status flag to indicate nodeserver is not running
        self.setDriver("ST", 0, True, True)
    
    # Set the active polling mode (short polling interval)
    def setActiveMode(self):
        self._activePolling = True
        self._lastActive =  time.time()

    # Run discovery for Sony devices
    def cmd_discover(self, command):

        LOGGER.info("Discover devices in cmd_discover()...")
        
        self.discover()

    # Update the profile on the ISY
    def cmd_updateProfile(self, command):

        LOGGER.info("Install profile in cmd_updateProfile()...")
        
        self.poly.installprofile()
        
    # Update the profile on the ISY
    def cmd_setLogLevel(self, command):

        LOGGER.info("Set logging level in cmd_setLogLevel(): %s", str(command))

        # retrieve the parameter value for the command
        value = int(command.get("value"))
 
        # set the current logging level
        LOGGER.setLevel(value)

        # store the new loger level in custom data
        self.addCustomData("loggerlevel", value)
        self.saveCustomData(self._customData)
        
        # update the state driver to the level set
        self.setDriver("GV20", value)
   
    # Set to active mode and run query
    def cmd_query(self, command):

        LOGGER.info("Query all devices: %s", str(command))

        self.setActivePolling()

        # Update the node states and force report of all driver values
        self.updateNodeStates(True)

    # called every longPoll seconds (default 30)
    def longPoll(self):

        pass

    # called every shortPoll seconds (default 5)
    def shortPoll(self):

        # if node server is not setup yet, return
        if self.myQConnection == None:
            return

        currentTime = time.time()

        # check for elapsed polling interval
        if ((self._activePolling and (currentTime - self._last_poll) >= self._active_poll) or
                (not self._activePolling and (currentTime - self._last_poll) >= self._inactive_poll)):

            # update the node states
            LOGGER.debug("Updating node states in Controller.shortPoll()...")
            self.updateNodeStates()

        # reset active flag if active interval has lapsed
        if self._last_active < (currentTime - ACTIVE_UPDATE_DURATION):
            self._activePolling = False

    # discover MyQ devices in account 
    def discover(self):

        # remove all existing notices for the nodeserver
        self.removeNoticesAll()

        # get device details from myQ service
        devices = self.myQConnection.getDeviceList()

        if devices is None:
            self.addNotice(f"Could not discover devices from MyQ Account. The MyQ service may be offline.")
            LOGGER.warning("getDeviceList() returned no devices.")

        else:

            # iterate devices
            # Note: has to be done in two passes to ensure system (primary/parent) nodes exist
            # before device nodes
            # first pass for gateway nodes
            for device in devices:
    
                if device["type"] == API_DEVICE_TYPE_GATEWAY:
                    
                    devAddr = getValidNodeAddress(device["id"])

                    # If no node already exists for the gateway, then add a node
                    if devAddr not in self.nodes:
                    
                        LOGGER.info("Discovered new device - id: %s, name: %s, type: %s", device["id"], device["description"], device["type"])

                        gwNode = Gateway(
                            self,
                            devAddr,    # set the gateway to be its own primary
                            devAddr,
                            getValidNodeName(device["description"]),
                            device["id"]
                        )
                        self.addNode(gwNode)

                        # update the state value for the gateway node (ST = Online)
                        gwNode.setDriver("ST", int(device["online"]))

            # second pass for device nodes
            for device in devices:
    
                if device["type"] in (API_DEVICE_TYPE_OPENER, API_DEVICE_TYPE_LAMP):

                    devAddr = getValidNodeAddress(device["id"])
                
                    # If no node already exists for the device, then add a node for the device
                    if devAddr not in self.nodes:
                
                        LOGGER.info("Discovered new device - id: %s, name: %s, type: %s", device["id"], device["description"], device["type"])

                        # add opener nodes
                        if device["type"] == API_DEVICE_TYPE_OPENER:
                    
                            devNode = GarageDoorOpener(
                                self,
                                getValidNodeAddress(device["parent_id"]), # set the primary to the gateway address
                                devAddr,
                                getValidNodeName(device["description"]),
                                device["id"]
                            )
                            self.addNode(devNode)

                            # update the state values for the opener node
                            devNode.setDriver("ST", getDoorState(device["state"]))
                            devNode.setDriver("GV0", calcElapsedSecs(device["last_changed"]))
         
                        # add lamp nodes
                        elif device["type"] == API_DEVICE_TYPE_LAMP:
                    
                            devNode = Light(
                                self,
                                getValidNodeAddress(device["parent_id"]), # set the primary to the gateway address
                                devAddr,
                                getValidNodeName(device["description"]),
                                device["id"]
                            )
                            self.addNode(devNode)

                            # update the state values for the light node
                            devNode.setDriver("ST", getLampState(device["state"]))
    
    # update the state of all nodes from the MyQ service
    # Parameters:
    #   forceReport - force reporting of all driver values (for query)
    def updateNodeStates(self, forceReport=False):

        # initially set driver values for controller to false to reflect service connection is gone
        serviceStatus = 0

        # get device details from myQ service
        devices = self.myQConnection.getDeviceList()
        if devices is None:
            LOGGER.warning("getDeviceList() returned no devices.")

        else:

            # If devices were returned, set the service status to True
            serviceStatus = 1

            # iterate the devices
            for device in devices:

                # find the matching node
                devAddr = getValidNodeAddress(device["id"])
                if devAddr in self.nodes:
                    node = self.nodes[devAddr]                
                
                    # set the state values based on the device type
                    if device["type"] == API_DEVICE_TYPE_GATEWAY:
                        
                        # update the state value for the gateway node (ST = Online)
                        node.setDriver("ST", int(device["online"]), True, forceReport)

                    elif device["type"] == API_DEVICE_TYPE_OPENER:

                        # update the state values for the opener node
                        value = getDoorState(device["state"])
                        node.setDriver("ST", value, True, forceReport)
                        node.setDriver("GV0", calcElapsedSecs(device["last_changed"]), True, forceReport)

                        # if a device state has a door in motion, set the active polling mode
                        if value in [IX_GDO_ST_CLOSING, IX_GDO_ST_OPENING, IX_GDO_ST_UNKNOWN]:
                            self.setActivePolling()
        
                    elif device["type"] == API_DEVICE_TYPE_LAMP:
    
                        # update the state values for the light node
                        node.setDriver("ST", getLampState(device["state"]), True, forceReport)

        # Update the controller node state
        self.setDriver("GV0", serviceStatus, True, forceReport)

        # Update the last polling time
        self._last_poll = time.time()

     # helper method for storing custom data
    def addCustomData(self, key, data):

        # add specififed data to custom data for specified key
        self._customData.update({key: data})

    # helper method for retrieve custom data
    def getCustomData(self, key):

        # return data from custom data for key
        return self._customData[key]

    drivers = [
        {"driver": "ST", "value": 0, "uom": ISY_BOOL_UOM},
        {"driver": "GV0", "value": 0, "uom": ISY_BOOL_UOM},
        {"driver": "GV20", "value": 0, "uom": ISY_INDEX_UOM}
    ]
    commands = {
        "QUERY": cmd_query,
        "DISCOVER": cmd_discover,
        "UPDATE_PROFILE" : cmd_updateProfile,
        "SET_LOGLEVEL": cmd_setLogLevel
    }

# Converts state value from MyQ to custom door states setup in editor/NLS in profile:
#   0=Closed, 1=Open, 2=Stopped, 3=Closing, 4=Opening, 9=Unknown
def getDoorState(state):
    if state == API_DEVICE_STATE_OPEN:  
        return IX_GDO_ST_OPEN
    elif state == API_DEVICE_STATE_CLOSED:
        return IX_GDO_ST_CLOSED
    elif state == API_DEVICE_STATE_STOPPED:
        return IX_GDO_ST_STOPPED
    elif state == API_DEVICE_STATE_OPENING:
        return IX_GDO_ST_OPENING
    elif state == API_DEVICE_STATE_CLOSING:
        return IX_GDO_ST_CLOSING
    else:
        return IX_GDO_ST_UNKNOWN

# Converts state value from MyQ to On/Off state for ISY
def getLampState(state):
    if state == API_DEVICE_STATE_ON:    
        return IX_LIGHT_ON
    elif state == API_DEVICE_STATE_OFF:   
        return IX_LIGHT_OFF
    else:
        return IX_LIGHT_UNKNOWN

# Calculate an elapsed time since the provided UTC string
def calcElapsedSecs(utcTimeString):
    return 35 # placeholder

# Removes invalid charaters and lowercase ISY Node address
def getValidNodeAddress(s):

    # remove <>`~!@#$%^&*(){}[]?/\;:"' characters
    addr = re.sub(r"[.<>`~!@#$%^&*(){}[\]?/\\;:\"']+", "", s)

    return addr[:14].lower()

# Removes invalid charaters for ISY Node description
def getValidNodeName(s):

    # remove <>`~!@#$%^&*(){}[]?/\;:"' characters from names
    return re.sub(r"[<>`~!@#$%^&*(){}[\]?/\\;:\"']+", "", s)

# Main function to establish Polyglot connection
if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface()
        polyglot.start()
        control = Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.warning("Received interrupt or exit...")
        polyglot.stop()
    except Exception as err:
        LOGGER.error('Excption: {0}'.format(err), exc_info=True)
        sys.exit(0)