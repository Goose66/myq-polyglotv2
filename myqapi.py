# LiftMaster MyQ API wrapper class
# Portions Copyright (c) 2017 arraylabs

import sys
import time
import logging
import requests

_APP_ID = "Vj8pQggXLhLy0WHahglCD4N1nAkkXQtGYpq2HrHD7H1nvmbT55KqtN6RSF4ILB/i"
_HOST_URI = "myqexternal.myqdevice.com"
_LOGIN_ENDPOINT = "api/v4/User/Validate"
_DEVICE_LIST_ENDPOINT = "api/v4/UserDeviceDetails/Get"
_DEVICE_SET_ATTR_ENDPOINT = "api/v4/DeviceAttribute/PutDeviceAttribute"
_DEVICE_GET_ATTR_ENDPOINT = "api/v4/DeviceAttribute/GetDeviceAttribute" # Never tested
_DOOR_STATE_SET_ATTR_NAME = "desireddoorstate"
_DESIRED_DOOR_STATE_OPEN = 1
_DESIRED_DOOR_STATE_CLOSED = 0
_GATEWAY_DEVICE_TYPES = {1}
_OPENER_DEVICE_TYPES = {2, 5, 7, 9, 17}
_LIGHT_DEVICE_TYPES = {3, 15, 16}


# Module level constants
DEVICE_TYPE_GATEWAY = 1
DEVICE_TYPE_GARAGE_DOOR_OPENER = 2

class MyQ(object):

    # Primary constructor method
    def __init__(self, userName, password, tokenTTL=600, logger=None):

        # declare instance variables
        self._userName = userName
        self._password = password
        self._tokenTTL = tokenTTL
        self._securityToken = ""
        self._lastTokenUpdate = 0
        self._myQSession = requests.Session()
        self._myQSession.headers.update({"MyQApplicationId": _APP_ID})
        
        if logger is None:
            # setup basic console logger for debugging
            logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
            self._logger = logging.getLogger() # Root logger
        else:
            self._logger = logger

    # Use the provided login info to obtain a security token
    def update_security_token(self):

        self._logger.debug("In update_security_token()...")

        params = {
            "username": self._userName,
            "password": self._password
        }

        try:
            response = self._myQSession.post(
                "https://{host_uri}/{login_endpoint}".format(
                    host_uri=_HOST_URI,
                    login_endpoint=_LOGIN_ENDPOINT
                ),
                json=params,
                timeout=6.05
            )
            response.raise_for_status()    # Raise HTTP errors to be handled in exception handling

        # Allow timeout and connection errors to be ignored - log and return false
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            self._logger.warning("HTTP POST in update_security_token() failed: %s", str(e))
            return False
        except:
            self._logger.error("Unexpected error occured: %s", sys.exc_info()[0])
            raise

        authContent = response.json()
        if "SecurityToken" in authContent:
            self._securityToken = authContent["SecurityToken"]
            self._myQSession.headers.update({"SecurityToken": self._securityToken})
            self._lastTokenUpdate = time.time()
            self._logger.info("MyQ security token updated")
            return True
        else:
            self._logger.error("Security token not retrieved: %s", authContent["ErrorMessage"])

    # Set the named attribute for the specified device to the specified value
    def set_device_attribute(self, deviceID, attrName, attrValue):

        self._logger.debug("in set_device_attribute()...")

        # update token if TTL has expired
        if time.time() > self._lastTokenUpdate + self._tokenTTL:
            if not self.update_security_token():
                return False

        payload = {
            "attributeName": attrName,
            "myQDeviceId": deviceID,
            "AttributeValue": attrValue
        }

        try:
            response = self._myQSession.put(
                "https://{host_uri}/{device_set_endpoint}".format(
                    host_uri=_HOST_URI,
                    device_set_endpoint=_DEVICE_SET_ATTR_ENDPOINT
                ),
                data=payload,
                timeout=3.05
            )
            response.raise_for_status()    # Raise HTTP errors to be handled in exception handling

        # Allow timeout and connection errors to be ignored - log and return false
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            self._logger.warning("HTTP PUT in set_device_attribute() failed: %s", str(e))
            return False
        except:
            self._logger.error("Unexpected error occured: %s", sys.exc_info()[0])
            raise
        else:
            return True

    def get_device_list(self):
    # Get a list of the devices (garage door openers and gateways) in the account

        self._logger.debug("In get_device_list()...")

        # update token if TTL has expired
        if time.time() > self._lastTokenUpdate + self._tokenTTL:
            if not self.update_security_token():
                return None

        try:
            response = self._myQSession.get(
                "https://{host_uri}/{device_list_endpoint}".format(
                    host_uri=_HOST_URI,
                    device_list_endpoint=_DEVICE_LIST_ENDPOINT
                ),
                timeout=6.05
            )
            response.raise_for_status()    # Raise HTTP errors to be handled in exception handling

        # Allow timeout and connection errors to be ignored - log and return no data
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            self._logger.warning("HTTP GET in get_device_list() failed: %s", str(e))
            return None
        except:
            self._logger.error("Unexpected error occured: %s", sys.exc_info()[0])
            raise

        deviceList = []
        for dev in response.json()["Devices"]:

            deviceID = str(dev["MyQDeviceId"])
            deviceType = dev["MyQDeviceTypeId"]

            # scan through device attributes and save the important ones
            for attribute in dev["Attributes"]:
                if attribute["AttributeDisplayName"] == "desc":
                    description = attribute["Value"]
                elif attribute["AttributeDisplayName"] == "online":
                    online = attribute["Value"] == "True"
                elif attribute["AttributeDisplayName"] == "numdevices":
                    numdevices = attribute["Value"]
                elif attribute["AttributeDisplayName"] == "isunattendedopenallowed":
                    allow_open = attribute["Value"] == "1"
                elif attribute["AttributeDisplayName"] == "isunattendedcloseallowed":
                    allow_close = attribute["Value"] == "1"
                elif attribute["AttributeDisplayName"] == "doorstate":
                    state = attribute["Value"]
                    last_updated = attribute["UpdatedDate"]

            if deviceType in _GATEWAY_DEVICE_TYPES: # Gateway

                deviceList.append({
                    "type": DEVICE_TYPE_GATEWAY,
                    "id": deviceID,
                    "description": description,
                    "online": online,
                    "numdevices": numdevices
                })

            elif deviceType in _OPENER_DEVICE_TYPES: # GarageDoorOpener

                deviceList.append({
                    "type": DEVICE_TYPE_GARAGE_DOOR_OPENER,
                    "id": deviceID,
                    "description": description,
                    "state": state,
                    "last_updated": last_updated,
                    "allow_open": allow_open,
                    "allow_close": allow_close
                })

        return deviceList

    def open(self, deviceID):
        return self.set_device_attribute(deviceID, _DOOR_STATE_SET_ATTR_NAME, _DESIRED_DOOR_STATE_OPEN)

    def close(self, deviceID):
        return self.set_device_attribute(deviceID, _DOOR_STATE_SET_ATTR_NAME, _DESIRED_DOOR_STATE_CLOSED)
