#!/usr/bin/env python
"""
Python wrapper class for LiftMaster MyQ API 
by Goose66 (W. Randy King) kingwrandy@gmail.com
Portions Copyright (c) 2017, 2020 arraylabs
"""

import sys
import time
import logging
import requests
from random import choices
import string

# Configure a module level logger for module testing
_LOGGER = logging.getLogger()
if not _LOGGER.hasHandlers():
    logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)

# MyQ REST API v5.1 spec.
_APP_ID = "JVM/G9Nwih5BwKgNCjLxiFUQxQijAebyyg8QUHr7JOrP+tuPb8iHfRHKwTmDzHOu"
_API_HOSTNAME = "api.myqdevice.com"
_API_HTTP_HEADERS = {
    "Content-Type": "application/json",
    "MyQApplicationId": _APP_ID,
    "User-Agent": "".join(choices(string.ascii_letters + string.digits, k=10)),
}
_API_LOGIN = {
    "url": "https://{host_name}/api/v5/Login",
    "method": "POST"
}
_API_GET_ACCOUNT_INFO = {
    "url": "https://{host_name}/api/v5/My",
    "method": "GET"
}
_API_GET_DEVICE_LIST = {
    "url": "https://{host_name}/api/v5.1/Accounts/{account_id}/Devices",
    "method": "GET"
}
_API_GET_DEVICE_PROPERTIES = {
    "url": "https://{host_name}/api/v5.1/Accounts/{account_id}/Devices/{device_id}",
    "method": "GET"
}
_API_DEVICE_ACTION = {
    "url": "https://{host_name}/api/v5.1/Accounts/{account_id}/Devices/{device_id}/actions",
    "method": "PUT"
}
_API_DEVICE_ACTION_OPEN = "open"
_API_DEVICE_ACTION_CLOSE = "close"
_API_DEVICE_ACTION_TURN_ON = "turnon"
_API_DEVICE_ACTION_TURN_OFF = "turnoff"
API_DEVICE_TYPE_GATEWAY = "gateway"
API_DEVICE_TYPE_OPENER = "garagedoor"
API_DEVICE_TYPE_LAMP = "lamp"
API_DEVICE_TYPE_CAMERA = "hawkeyecamera"
API_DEVICE_STATE_OPEN = "open"
API_DEVICE_STATE_CLOSED = "closed"
API_DEVICE_STATE_STOPPED = "stopped"
API_DEVICE_STATE_OPENING = "opening"
API_DEVICE_STATE_CLOSING = "closing"
API_DEVICE_STATE_ON = "on"
API_DEVICE_STATE_OFF = "off"

API_LOGIN_BAD_AUTHENTICATION = 1
API_LOGIN_ERROR = 3
API_LOGIN_SUCCESS = 0

# Timeout durations for HTTP calls - defined here for easy tweaking
_HTTP_GET_TIMEOUT = 12.05
_HTTP_PUT_TIMEOUT = 3.05
_HTTP_POST_TIMEOUT = 6.05

# Module level constants
DEVICE_TYPE_GATEWAY = 1
DEVICE_TYPE_GARAGE_DOOR_OPENER = 2
DEVICE_TYPE_LIGHT = 3

class MyQ(object):

    _userName = ""
    _password = ""
    _tokenTTL = 0
    _accountID = ""
    _lastTokenUpdate = 0
    _session = None
    _logger = None
  
    # Primary constructor method
    def __init__(self, tokenTTL=100, logger=_LOGGER):

        # set instance variables
        self._tokenTTL = tokenTTL
        self._logger = logger

        # create a session object for REST calls
        self._session = requests.Session()
        self._session.headers.update(_API_HTTP_HEADERS)      

    # Call the specified REST API
    def _call_api(self, api, deviceID="", params=None):
      
        method = api["method"]
        url = api["url"].format(host_name = _API_HOSTNAME, account_id = self._accountID, device_id = deviceID)

        # uncomment the next line to dump HTTP request data to log file for debugging
        #self._logger.debug("HTTP %s data: %s", method + " " + url, params)

        try:
            response = self._session.request(
                method,
                url,
                json = params,  
                timeout= _HTTP_POST_TIMEOUT if method in ("POST", "PUT") else _HTTP_GET_TIMEOUT
            )
            
            # raise any codes other than 200, 204, and 401 for error handling 
            if response.status_code not in (200, 204, 401):
                response.raise_for_status()

        # Allow (potentially) temporary network errors to be ignored - log and return None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            self._logger.warning("Network/server error in HTTP %s in _call_api(): %s", method, str(e))
            return None

        # Bail on all other errors
        except:
            self._logger.error("Unexpected error occured: %s", sys.exc_info()[0])
            raise

        # uncomment the next line to dump HTTP response to log file for debugging
        #self._logger.debug("HTTP response code: %d data: %s", response.status_code, response.text)

        return response

    # Use the provided login info to obtain a security token
    def _checkToken(self):
       
        self._logger.debug("In _checkToken()...")

        # check TTL time
        currentTime = time.time()
        if currentTime - self._lastTokenUpdate > self._tokenTTL:

            # format parameters
            params = {
                "Username": self._userName,
                "Password": self._password
            }

            # call the login API
            response = self._call_api(_API_LOGIN, params=params)
        
            if response is not None:
                
                authInfo = response.json()
            
                if response.status_code == 200:

                    token = authInfo["SecurityToken"]
                    self._session.headers.update({"SecurityToken": token})
                    self._lastTokenUpdate = time.time()

                else:
                    
                    # otherwise just log it and try to keep going with current tokens
                    self._logger.error("Error retrieving security token: %d - %s", response.json().get("code"), response.json().get("description"))

            else:
                    # logged in _call_api()
                    pass

    # perform the specified action with the specified device
    def _performAction(self, deviceID, action):

        self._logger.debug("In _performAction()...")

        # update the security token if needed
        # Note: no need to check token here - just send the command promptly
        # self._checkToken() 

        # set the action parameter
        params = {"action_type": action}
        response = self._call_api(_API_DEVICE_ACTION, deviceID, params)

        if response is not None:
            
            if response.status_code == 204:
                return True
            else:
                self._logger.error("Error performing device action for device ID %s: %s", deviceID,  _parseResponseMsg(response))
                return False

        else:
            # Error logged in _call_api function
            return False

    def loginToService(self, userName, password):
        """Logs into the MyQ account and retrieves the account ID and access token.

        Parameters:
        username -- username (email address) for MyQ service (string)
        password -- password for MyQ service (string)

        Returns:
        code indicating login success: API_LOGIN_SUCCESS, API_LOGIN_BAD_AUTHENTICATION, API_LOGIN_ERROR
        """
        self._logger.debug("in API loginToService()...")

        # format parameters
        params = {
            "Username": userName,
            "Password": password
        }

        # call the login API
        response = self._call_api(_API_LOGIN, params=params)
        
        # if data returned, parse the access tokens and store in the instance variables
        if response is not None:
        
            authInfo = response.json()
        
            if response.status_code == 200:

                token = authInfo["SecurityToken"]
                self._session.headers.update({"SecurityToken": token})
                self._lastTokenUpdate = time.time()

                self._userName = userName
                self._password = password

                # Retrieve the account ID for subsequent calls
                response = self._call_api(_API_GET_ACCOUNT_INFO)
                if response and response.status_code == 200:

                    # get the Account ID from the account href parameter - NOT necessarily the same as the UserId
                    accountHref = response.json()["Account"]["href"]
                    accountID = accountHref[accountHref.rfind("/")+1:]
                    self._accountID = accountID

                    return API_LOGIN_SUCCESS
                else:

                    self._logger.error("Error retrieving account ID: %s",  _parseResponseMsg(response))
                    return API_LOGIN_ERROR

            # check for authentication error (most likely bad credentials)
            elif response.status_code == 401:

                self._logger.warning("Authentication error logging into MyQ service: %s",  _parseResponseMsg(response))
                return API_LOGIN_BAD_AUTHENTICATION

            else:
                self._logger.error("Error logging into MyQ service: %s",  _parseResponseMsg(response))
                return API_LOGIN_ERROR

        else:
            # Error logged in _call_api function
            return API_LOGIN_ERROR

    def getDeviceList(self):
        """Returns a list of devices in the account

        Returns:
        list (array) of devices (openers, lights, gateways)
        """
        self._logger.debug("In getDeviceList()...")

        # update the security token if needed    
        self._checkToken()

        response = self._call_api(_API_GET_DEVICE_LIST )

        if response is not None:

            deviceInfo = response.json()
            
            if response.status_code == 200 and "items" in deviceInfo:

                deviceList = []

                for dev in deviceInfo["items"]:
                    
                    # pull out common attributes
                    deviceID = dev["serial_number"]
                    deviceType = dev["device_family"]
                    description = dev.get("name", deviceType + " " + deviceID[-4:])

                    # uncomment the next line to inspect the devices returned from the MyQ service
                    self._logger.debug("Device Found - Device ID: %s, Device Type: %s, Description: %s", deviceID, deviceType, description)

                    # add device to the list with properties based on type
                    if deviceType == API_DEVICE_TYPE_GATEWAY:

                        # get gateway attributes
                        online = dev["state"]["online"]
                        lastUpdated = dev["state"]["last_status"]

                        # add gateway device to list
                        deviceList.append({
                            "type": deviceType,
                            "id": deviceID,
                            "description": description,
                            "online": online,
                            "last_updated": lastUpdated
                        })

                    elif deviceType == API_DEVICE_TYPE_OPENER:
                        
                        # get the door attributes
                        parentID = dev["parent_device_id"]                        
                        state = dev["state"]["door_state"]
                        lastChanged = dev["state"]["last_update"]
                        lastUpdated = dev["state"]["last_status"]

                        # add garage door opener device to list
                        deviceList.append({
                            "type": deviceType,
                            "id": deviceID,
                            "parent_id": parentID,
                            "description": description,
                            "state": state,
                            "last_changed": lastChanged,
                            "last_updated": lastUpdated
                        })
        
                    elif deviceType == API_DEVICE_TYPE_LAMP:

                        # get the lamp attributes
                        parentID = dev["parent_device_id"]                        
                        state = dev["state"]["lamp_state"]              
                        lastChanged = dev["state"]["last_update"]
                        lastUpdated = dev["state"]["last_status"]

                        # add lamp device to list
                        deviceList.append({
                            "type": deviceType,
                            "id": deviceID,
                            "parent_id": parentID,
                            "description": description,
                            "state": state,
                            "last_changed": lastChanged,
                            "last_updated": lastUpdated
                    })
                
                return deviceList
            
            elif response.status_code == 401:
                
                self._logger.error("There was an authentication error with the MyQ account: %s",  _parseResponseMsg(response))
                return None

            else:
                
                self._logger.error("Error retrieving device list: %s",  _parseResponseMsg(response))
                return None

        else:
            # Error logged in _call_api function
            return None


    def open(self, deviceID):
        """Opens the specified device (garage door opener)

        Returns:
        Boolean indicating success of call
        """
        
        return self._performAction(deviceID, _API_DEVICE_ACTION_OPEN)

    def close(self, deviceID):
        """Closes the specified device (garage door opener)

        Returns:
        Boolean indicating success of call
        """
        
        return self._performAction(deviceID, _API_DEVICE_ACTION_CLOSE)

    def turnOn(self, deviceID):
        """Turns on the specified device (light)

        Returns:
        Boolean indicating success of call
        """

        return self._performAction(deviceID, _API_DEVICE_ACTION_TURN_ON)

    def turnOff(self, deviceID):
        """Turns off the specified device (light)

        Returns:
        Boolean indicating success of call
        """
        
        return self._performAction(deviceID, _API_DEVICE_ACTION_TURN_OFF)

    def disconnect(self):
        """Closes the HTTP session to the MyQ service)
        """
        
        self._session.close()

# provide a consistent parsing of HTTP response messages for logging
def _parseResponseMsg(response):

    # should never be None, but just to be safe
    if response is not None:
        r = response.json()
        msg = "{} - {}: {}".format(r.get("code", "N/A"), r.get("message", "N/A"), r.get("description", "No message provided."))
    else:
        msg = "No error message provided."
    
    return msg