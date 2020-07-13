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

# Configure a module level logger for module testing
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

# MyQ REST API v5.1 spec.
_APP_ID = "JVM/G9Nwih5BwKgNCjLxiFUQxQijAebyyg8QUHr7JOrP+tuPb8iHfRHKwTmDzHOu"
_API_HOSTNAME = "api.myqdevice.com"
_API_HTTP_HEADERS = {
    "Content-Type": "application/json",
    "MyQApplicationId": _APP_ID,
    "User-Agent": "okhttp/3.10.0",
    "ApiVersion": "5.1",
    "BrandId": "2",
    "Culture": "en"
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
    "url": "https://{host_name}/api/v5.1/Accounts/{account_id}/Devices/{device_id}/Actions",
    "method": "PUT"
}
_API_DEVICE_ACTION_OPEN = "open"
_API_DEVICE_ACTION_CLOSE = "close"
_API_DEVICE_ACTION_TURN_ON = "turnon"
_API_DEVICE_ACTION_TURN_OFF = "turnoff"
API_DEVICE_TYPE_GATEWAY = "ethernetgateway"
API_DEVICE_TYPE_OPENER = "garagedooropener"
API_DEVICE_TYPE_LAMP = "lamp"
API_DEVICE_STATE_OPEN = "open"
API_DEVICE_STATE_CLOSED = "closed"
API_DEVICE_STATE_STOPPED = "stopped"
API_DEVICE_STATE_OPENING = "opening"
API_DEVICE_STATE_CLOSING = "closing"
API_DEVICE_STATE_ON = "on"
API_DEVICE_STATE_OFF = "off"

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
    def __init__(self, userName, password, tokenTTL=100, logger=_LOGGER):

        # declare instance variables
        self._userName = userName
        self._password = password
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

        # Allow timeout and connection errors to be ignored - log and return false
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            self._logger.warning("HTTP %s in _call_api() failed: %s", method, str(e))
            return False
        except:
            self._logger.error("Unexpected error occured: %s", sys.exc_info()[0])
            raise

        # uncomment the next line to dump HTTP response to log file for debugging
        #self._logger.debug("HTTP response code: %d data: %s", response.status_code, response.text)

        return response

    # Use the provided login info to obtain a security token
    def _update_security_token(self):
        self._logger.debug("In _update_security_token()...")
        params = {
            "Username": self._userName,
            "Password": self._password
        }
        response = self._call_api(_API_LOGIN, params=params)

        # if data returned, update authentication and account info
        if response:

            authInfo = response.json()

            #   , update security token and account info
            if response.status_code == 200:

                token = authInfo["SecurityToken"]
                self._session.headers.update({"SecurityToken": token})
                self._lastTokenUpdate = time.time()
                self._logger.info("MyQ security token updated")

                # The account ID doesn't appear to change, so only update it if needed
                if self._accountID == "":
                    response = self._call_api(_API_GET_ACCOUNT_INFO, params)
                    if response and response.status_code == 200:
                        accountID = response.json().get("UserId", "")
                        self._accountID = accountID
                        return True

                    else:
                        self._logger.error("Error retrieving account ID: %s", response.json().get("ErrorMessage", "No error message provided."))
                        return False
                else:
                    return True
    
            else:
                self._logger.error("Security token not retrieved: %s", authInfo.get("ErrorMessage", "No error message provided."))
                return False

        else:
            # Error logged in _call_api function
            return False

    # perform the specified action with the specified device
    def _perform_action(self, deviceID, action):

        self._logger.debug("In _perform_action()...")

        # update token if TTL has expired
        if time.time() > self._lastTokenUpdate + self._tokenTTL:
            if not self._update_security_token():
                return False

        # set the action parameter
        params = {"action_type": action}
        response = self._call_api(_API_DEVICE_ACTION, deviceID, params)

        if response:
            
            if response.status_code == 204:
                return True
            else:
                self._logger.error("Error performing device action for device ID %s: %s", deviceID, response.json().get("ErrorMessage", "No error message provided."))
                return False

        else:
            # Error logged in _call_api function
            return False

    def get_device_list(self):
        """Returns a list of devices in the account

        Returns:
        dictionary of devices (openers, lights, gateways)
        """
        self._logger.debug("In get_device_list()...")

        # update token if TTL has expired
        if time.time() > self._lastTokenUpdate + self._tokenTTL:
            if not self._update_security_token():
                return None

        response = self._call_api(_API_GET_DEVICE_LIST )

        if response:

            deviceInfo = response.json()
            
            if response.status_code == 200 and "items" in deviceInfo:

                deviceList = []

                for dev in deviceInfo["items"]:
                    
                    # temporarily convert device ID to lowercase to preserve compatibility with old API module
                    deviceID = dev["serial_number"].lower()
                    deviceType = dev["device_type"]
                    description = dev["name"]
                    online = dev["state"]["online"]
                    last_updated = dev["state"]["last_status"]

                    # uncomment the next line to inspect the devices returned from the MyQ service
                    #self._logger.debug("Device Found - DeviceId: %s, DeviceTypeId: %s, Description: %s", deviceID, deviceType, description)

                    # add gateway type devices to the list
                    if deviceType == API_DEVICE_TYPE_GATEWAY:
                        deviceList.append({
                            "type": deviceType,
                            "id": deviceID,
                            "description": description,
                            "online": online,
                            "last_updated": last_updated
                        })

                    elif deviceType == API_DEVICE_TYPE_OPENER:
    
                        # get the door state
                        state = dev["state"]["door_state"]
                        deviceList.append({
                            "type": deviceType,
                            "id": deviceID,
                            "description": description,
                            "state": state,
                            "last_updated": last_updated
                        })
    
                    elif deviceType == API_DEVICE_TYPE_LAMP:

                        # get the lamp state
                        state = dev["state"]["lamp_state"]
                        deviceList.append({
                            "type": deviceType,
                            "id": deviceID,
                            "description": description,
                            "state": state,
                            "last_updated": last_updated
                    })
                
                return deviceList
            
            else:
                
                self._logger.error("Error retrieving device list: %s", deviceInfo.get("ErrorMessage", "No error message provided."))
                return None

        else:
            # Error logged in _call_api function
            return False


    def open(self, deviceID):
        """Opens the specified device (garage door opener)

        Returns:
        Boolean indicating success of call
        """
        
        # temporarily convert device ID back to uppercase to account for compatibility with old API module
        return self._perform_action(deviceID.upper(), _API_DEVICE_ACTION_OPEN)

    def close(self, deviceID):
        """Closes the specified device (garage door opener)

        Returns:
        Boolean indicating success of call
        """
        
        # temporarily convert device ID back to uppercase to account for compatibility with old API module
        return self._perform_action(deviceID.upper(), _API_DEVICE_ACTION_CLOSE)

    def turn_on(self, deviceID):
        """Turns on the specified device (light)

        Returns:
        Boolean indicating success of call
        """
        
        # temporarily convert device ID back to uppercase to account for compatibility with old API module
        return self._perform_action(deviceID.upper(), _API_DEVICE_ACTION_TURN_ON)

    def turn_off(self, deviceID):
        """Turns off the specified device (light)

        Returns:
        Boolean indicating success of call
        """
        
        # temporarily convert device ID back to uppercase to account for compatibility with old API module
        return self._perform_action(deviceID.upper(), _API_DEVICE_ACTION_TURN_ON)

    def disconnect(self):
        """Closes the HTTP session to the MyQ service)
        """
        
        self._session.close()