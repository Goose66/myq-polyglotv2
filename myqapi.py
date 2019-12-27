# LiftMaster MyQ API wrapper class
# Portions Copyright (c) 2017 arraylabs

import sys
import time
import logging
import requests
from calendar import timegm

_APP_ID = "JVM/G9Nwih5BwKgNCjLxiFUQxQijAebyyg8QUHr7JOrP+tuPb8iHfRHKwTmDzHOu"
_HOST_URI = "api.myqdevice.com"
_LOGIN_ENDPOINT = "api/v5/Login"
_ACCOUNT_INFO_ENDPOINT = "api/v5/My"
_DEVICE_BASE = "api/v5.1/Accounts"
_DESIRED_DOOR_STATE_OPEN = "open"
_DESIRED_DOOR_STATE_CLOSED = "close"
_DESIRED_LIGHT_STATE_ON = "turnon"
_DESIRED_LIGHT_STATE_OFF = "turnoff"
_GATEWAY_DEVICE_TYPE = "ethernetgateway"
_OPENER_DEVICE_TYPE = "garagedooropener"
_LIGHT_DEVICE_TYPE = "lamp"

# Timeout durations for HTTP calls - defined here for easy tweaking
_HTTP_GET_TIMEOUT = 12.05
_HTTP_PUT_TIMEOUT = 3.05
_HTTP_POST_TIMEOUT = 6.05

# Module level constants
DEVICE_TYPE_GATEWAY = 1
DEVICE_TYPE_GARAGE_DOOR_OPENER = 2
DEVICE_TYPE_LIGHT_SWITCH = 3

class MyQ(object):

    # Primary constructor method
    def __init__(self, userName, password, tokenTTL=100, logger=None):

        # declare instance variables
        self._userName = userName
        self._password = password
        self._tokenTTL = tokenTTL
        self._securityToken = ""
        self._accountId = ""
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
            "Username": self._userName,
            "Password": self._password
        }
        try:
            response = self._myQSession.post(
                "https://{host_uri}/{login_endpoint}".format(
                    host_uri=_HOST_URI,
                    login_endpoint=_LOGIN_ENDPOINT
                ),
                json=params,
                timeout=_HTTP_POST_TIMEOUT
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
            self.refresh_account_info()
            return True
        else:
            self._logger.error("Security token not retrieved: %s", authContent["ErrorMessage"])

    def refresh_account_info(self):
        params = { "expand": "account" }
        try:
            response = self._myQSession.get(
                "https://{host_uri}/{info_endpoint}".format(
                    host_uri=_HOST_URI,
                    info_endpoint=_ACCOUNT_INFO_ENDPOINT
                ),
                params=params,
                timeout=_HTTP_POST_TIMEOUT
            )
            response.raise_for_status()    # Raise HTTP errors to be handled in exception handling
        # Allow timeout and connection errors to be ignored - log and return false
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            self._logger.warning("HTTP GET in refresh_account_info() failed: %s", str(e))
            return False
        except:
            self._logger.error("Unexpected error occured: %s", sys.exc_info()[0])
            raise
        accountInfo = response.json()
        if "Account" in accountInfo:
            self._accountId = accountInfo["Account"]["Id"]
            self._logger.info("Account ID updated")
            return True
        else:
            self._logger.error("Account ID not retrieved: %s", authContent["ErrorMessage"])
        

    def set_device_state(self, deviceID, new_state):
        self._logger.debug("in set_device_state()...")

        # update token if TTL has expired
        if time.time() > self._lastTokenUpdate + self._tokenTTL:
            if not self.update_security_token():
                return False

        payload = { "action_type": new_state }

        try:
            response = self._myQSession.put(
                "https://{host_uri}/{device_base}/{account_id}/Devices/{device_id}/Actions".format(
                    host_uri=_HOST_URI,
                    device_base=_DEVICE_BASE,
                    account_id=self._accountId,
                    device_id=deviceID.upper()
                ),
                json=payload,
                timeout=_HTTP_PUT_TIMEOUT
            )
            response.raise_for_status()    # Raise HTTP errors to be handled in exception handling

        # Allow timeout and connection errors to be ignored - log and return false
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            self._logger.warning("HTTP PUT in set_device_state() failed: %s", str(e))
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
                "https://{host_uri}/{device_base}/{account_id}/Devices".format(
                    host_uri=_HOST_URI,
                    device_base=_DEVICE_BASE,
                    account_id=self._accountId
                ),
                timeout=_HTTP_GET_TIMEOUT
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
        if not "items" in response.json():
            return deviceList

        for dev in response.json()["items"]:
            deviceID = dev["serial_number"].lower() # Oh boy, ISY doesn't support uppercases in IDs... need to convert
            deviceType = dev["device_type"]
            description = dev["name"]
            online = dev["state"]["online"]

            # uncomment the next line to inspect the devices returned from the MyQ service
            #self._logger.debug("Device Found - DeviceId: %s, DeviceTypeId: %s, Description: %s", deviceID, deviceType, description)

            if deviceType == _GATEWAY_DEVICE_TYPE:
                deviceList.append({
                    "type": DEVICE_TYPE_GATEWAY,
                    "id": deviceID,
                    "description": description,
                    "online": online
                })
            elif deviceType == _OPENER_DEVICE_TYPE and len(description) > 0:
                # devices without a description may not be initialized/setup in the MyQ Service
                # so ignore them
                allow_open = dev["state"]["is_unattended_open_allowed"]
                allow_close = dev["state"]["is_unattended_close_allowed"]
                state = dev["state"]["door_state"]
                last_update = self.convert_time(dev["state"]["last_update"])
                deviceList.append({
                    "type": DEVICE_TYPE_GARAGE_DOOR_OPENER,
                    "id": deviceID,
                    "description": description,
                    "state": state,
                    "last_updated": last_update,
                    "allow_open": allow_open,
                    "allow_close": allow_close
                })
            elif deviceType == _LIGHT_DEVICE_TYPE and len(description) > 0:
                state = dev["state"]["lamp_state"]
                last_update = self.convert_time(dev["state"]["last_update"])
                deviceList.append({
                    "type": DEVICE_TYPE_LIGHT_SWITCH,
                    "id": deviceID,
                    "description": description,
                    "state": state,
                    "last_updated": last_update
                })
        return deviceList

    def open(self, deviceID):
        return self.set_device_state(deviceID, _DESIRED_DOOR_STATE_OPEN)

    def close(self, deviceID):
        return self.set_device_state(deviceID, _DESIRED_DOOR_STATE_CLOSED)

    def turn_on(self, deviceID):
        return self.set_device_state(deviceID, _DESIRED_LIGHT_STATE_ON)

    def turn_off(self, deviceID):
        return self.set_device_state(deviceID, _DESIRED_LIGHT_STATE_OFF)

    def convert_time(self, timestamp):
        #  Input format: 2019-11-06T02:28:28.3802657Z
        utc_time = time.strptime(timestamp[0:22] + "Z", "%Y-%m-%dT%H:%M:%S.%fZ")
        return timegm(utc_time)
