#!/usr/bin/env python
"""
Python wrapper class for LiftMaster MyQ API 
by Goose66 (W. Randy King) kingwrandy@gmail.com
"""

# Standard Python Library
import sys
import time
import logging
import string
from urllib.parse import parse_qs, urlsplit

# 3rd Party Libraries
import requests
import pkce
from pyquery import PyQuery

# Configure a module level logger for module testing
_LOGGER = logging.getLogger()
if not _LOGGER.hasHandlers():
    logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)

# MyQ REST API v6 spec.

_API_SESSION_HEADERS = {
    "User-Agent": "null"
}
_API_GET_ACCOUNT_INFO = {
    "url": "https://accounts.myq-cloud.com/api/v6.0/accounts",
    "method": "GET"
}
_API_GET_DEVICE_LIST = {
    "url": "https://devices.myq-cloud.com/api/v5.2/Accounts/{account_id}/Devices",
    "method": "GET"
}
_API_GET_DEVICE_PROPERTIES = {
    "url": "https://devices.myq-cloud.com/api/v5.2/Accounts/{account_id}/Devices/{device_id}",
    "method": "GET"
}
_API_GDO_DEVICE_ACTION = {
    "url": "https://account-devices-gdo.myq-cloud.com/api/v5.2/Accounts/{account_id}/door_openers/{device_id}/{command}",
    "method": "PUT"
}
_API_LAMP_DEVICE_ACTION = {
    "url": "https://account-devices-lamp.myq-cloud.com/api/v5.2/Accounts/{account_id}/lamps/{device_id}/{command}",
    "method": "PUT"
}

_OAUTH_BASE_URL = "https://partner-identity.myq-cloud.com"
_OAUTH_AUTHORIZATION_URL = f"{_OAUTH_BASE_URL}/connect/authorize"
_OAUTH_TOKEN_URL = f"{_OAUTH_BASE_URL}/connect/token"
_OAUTH_SESSION_HEADERS = {
    "User-Agent": "null"
}
_OAUTH_CLIENT_ID = "IOS_CGI_MYQ"
_OAUTH_CLIENT_SECRET = "VUQ0RFhuS3lQV3EyNUJTdw=="
_OAUTH_REDIRECT_URI = "com.myqops://ios"
_OAUTH_MYQ_SCOPE = "MyQ_Residential offline_access"
_OAUTH_TOKEN_TTL = 3600 # 60 minutes

_API_DEVICE_ACTION_OPEN = "open"
_API_DEVICE_ACTION_CLOSE = "close"
_API_DEVICE_ACTION_TURN_ON = "on"
_API_DEVICE_ACTION_TURN_OFF = "off"

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

LOGIN_BAD_AUTHENTICATION = 1
LOGIN_ERROR = 3
LOGIN_BAD_HOME_NAME = 4
LOGIN_SUCCESS = 0

# Timeout durations for HTTP calls - defined here for easy tweaking
_HTTP_OAUTH_TIMEOUT = 12.05
_HTTP_GET_TIMEOUT = 12.05
_HTTP_PUT_TIMEOUT = 3.05
_HTTP_POST_TIMEOUT = 6.05

class MyQ(object):

    _accessToken = ""
    _refreshToken = ""
    _tokenType = ""
    _tokenTTL = 0
    _lastTokenUpdate = 0

    _userName = ""
    _password = ""

    _accountID = ""
    _apiSession = None
    _oAuthSession = None
    _logger = None
  
    # Primary constructor method
    def __init__(self, logger=_LOGGER):

        # set instance variables
        self._logger = logger   

    def loginToService(self, userName, password, homeName=None):
        """Logs into the MyQ account and retrieves the acess token via oAuth session

        Parameters:
        username -- username (email address) for MyQ service (string)
        password -- password for MyQ service (string)
        homeName -- specifies a "Home Name" for indicating which account to use if multiple accounts are present

        Returns:
        code indicating login success: LOGIN_SUCCESS, LOGIN_BAD_AUTHENTICATION, LOGIN_ERROR
        """
        self._logger.debug("in API loginToService()...")

        rc = self._oAuthRetrieveToken(userName, password)

        if rc == LOGIN_SUCCESS:
        
            # in case the token expires before being refreshed and we have to retrieve
            # a new access token
            self._userName = userName
            self._password = password

            # get the account ID and store it for subsequent calls
            rc = self._getAccountID(homeName)
        
        return rc

    def getDeviceList(self):
        """Returns a list of devices in the account

        Returns:
        list (array) of devices (openers, lights, gateways)
        """

        self._logger.debug("In getDeviceList()...")

        # update the security token if needed    
        if self._checkToken():

            response = self._callAPI(_API_GET_DEVICE_LIST, useSession=True)

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
                # Error logged in _callAPI function
                return None

        else:
            # Check token failed - wait and see if next call successful
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
        """Closes the HTTP sessions to the MyQ services
        """
        self._apiSession.close()
        self._oAuthSession.close()
    
        # Check the access token and refresh if expired
    def _checkToken(self):
       
        currentTime = time.time()

        # If the access token has expired, then we have to retrieve a new one
        # using the stored user credentials
        if currentTime - self._lastTokenUpdate > self._tokenTTL:
            rc = self._oAuthRetrieveToken(self._userName, self._password)
            return (rc == LOGIN_SUCCESS)

        # If the access token is within 10 minutes of expiring, then refresh
        # the access token using the oAuth refresh token
        elif currentTime - self._lastTokenUpdate > self._tokenTTL - 600:
            return self._oAuthRefreshToken()

        # Otherwise token has not expired so all good
        return True

    # perform the specified action with the specified device
    def _performAction(self, deviceID, action):

        self._logger.debug("In _performAction()...")

        # Note: no need to check token here - just send the command promptly
        # self._checkToken() 

        # set the device URL based on the commands - different for lamps and GDOs
        if action in (_API_DEVICE_ACTION_TURN_ON, _API_DEVICE_ACTION_TURN_OFF):
            api = _API_LAMP_DEVICE_ACTION
        else:
            api = _API_GDO_DEVICE_ACTION

        # call the MyQ API to perform the action 
        response = self._callAPI(api, deviceID=deviceID, command=action)

        if response is not None:
            
            if response.status_code == 202:
                return True
            else:
                self._logger.error("Error performing device action for device ID %s: %s", deviceID,  _parseResponseMsg(response))
                return False

        else:
            # Error logged in _callAPI function
            return False

    # retrieve the account ID for subsequent calls
    def _getAccountID(self, homeName):
        
        self._logger.debug("In _getAccountID()...")

        # retrieve the accounts list from the MyQ service
        resp = self._callAPI(_API_GET_ACCOUNT_INFO)
        if resp and resp.status_code == 200:

            accounts = resp.json()["accounts"]

            # if a home name was specified, search the accounts for the home name 
            if homeName is not None:
                for a in accounts:
                    if _strip(a.get("name")) == _strip(homeName):
                        self._accountID = a["id"]
                        return LOGIN_SUCCESS
                
                # if the homename was not found, return bad home name error
                return LOGIN_BAD_HOME_NAME
            
            # otherwise just get the Account ID for the first listed account
            else:
                self._accountID = accounts[0]["id"]
                return LOGIN_SUCCESS
   
        else:

            self._logger.error("Error retrieving account ID: %s",  _parseResponseMsg(resp))
            return LOGIN_ERROR        

    # Call the specified REST API
    def _callAPI(self, api, deviceID="", command="", useSession=False):
      
        # if a session is to be used, e.g. device list API calls, then create one if it doesn't already exist
        if useSession and self._apiSession is None:
            self._apiSession = requests.Session()
            self._apiSession.headers.update(_API_SESSION_HEADERS)

        method = api["method"]
        url = api["url"].format(account_id = self._accountID, device_id = deviceID, command=command)

        # make sure the header has the latest access token
        headers = {"Authorization": self._tokenType + " " + self._accessToken}


        # uncomment the next line to dump HTTP request data to log file for debugging
        # WARNING: this may expose credentials
        #self._logger.debug("HTTP %s to %s", method, url)

        try:
            if useSession:
                response = self._apiSession.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=_HTTP_POST_TIMEOUT if method in ("POST", "PUT") else _HTTP_GET_TIMEOUT
                )
            else:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=_HTTP_POST_TIMEOUT if method in ("POST", "PUT") else _HTTP_GET_TIMEOUT
                )

            # raise any codes other than 200, 202, and 204 for error handling 
            if response.status_code not in (200, 202, 204):
                response.raise_for_status()

        # Allow (potentially) temporary network errors to be ignored - log and return None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            self._logger.warning("Network/server error in HTTP %s in _callAPI(): %s", method, str(e))
            return None

        # Bail on all other errors
        except:
            self._logger.error("Unexpected error occured: %s", sys.exc_info()[0])
            raise

        # uncomment the next line to dump HTTP response to log file for debugging
        #self._logger.debug("HTTP response code: %d data: %s", response.status_code, response.text)

        return response

    def _oAuthRetrieveToken(self, userName, password):        

        self._logger.info("Logging in and retrieving access token via oAuth...")

        # oAuth 2.0 Authorization Code Flow:
        # Step 1: Transmit the PKCE challenge and retrieve the MyQ login page

        # get the PKCE code challenge 
        code_verifier, code_challenge = pkce.generate_pkce_pair(code_verifier_length = 43)

        # format the parameters for the GET
        params={
            "client_id": _OAUTH_CLIENT_ID,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "redirect_uri": _OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": _OAUTH_MYQ_SCOPE,
        }
        headers={
            "redirect": "follow"
        }

        # call the authorization URL retrieve the MyQ login page
        respAuth = self._oAuthRequest(
            url=_OAUTH_AUTHORIZATION_URL,
            headers=headers,
            params=params,  
            allow_redirects=True, # redirects through several pages to get the login page
        )
            
        # if an HTTP or network error occured, return login error code
        if respAuth is None:
            self._logger.debug("Error in Step 1 of oAuth flow.")
            return LOGIN_ERROR

        # Step 2: Post back to the MyQ login page with the provided credentials and values parsed from the login page

        # get the set cookie from the response headers
        setCookie = respAuth.headers["Set-Cookie"]

        # get the verification token input field value from the login form HTML
        docAuth = PyQuery(respAuth.text)
        requestVerificationToken = docAuth("input[name='__RequestVerificationToken']").attr("value")

        # verify verification token was retrieved
        if not requestVerificationToken:
            self._logger.warning("Unable to complete OAuth login. The verification token could not be retrieved")
            return LOGIN_ERROR

        # format the data for the POST 
        data={
            "Email": userName,
            "Password": password,
            "__RequestVerificationToken": requestVerificationToken,
        }
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Set-Cookie": setCookie,
        }

        # call the authorization URL retrieve the MyQ login page
        respLogin = self._oAuthRequest(
            url=respAuth.url,
            method="POST",
            data=data,
            headers=headers,
            allow_redirects=False,
        )

        # if an HTTP or network error occured, return login error code
        if respLogin is None:
            self._logger.debug("Error in Step 2 of oAuth flow.")
            return LOGIN_ERROR

        # if we didn't get back at least 2 cookies, then likely authentication failed
        if len(respLogin.cookies) < 2:
            self._logger.warning("Error logging into MyQ service - invalid MyQ credentials provided.")
            return LOGIN_BAD_AUTHENTICATION

        # Step 3: Intercept the redirect back to the MyQ iOS app

        # get the set cookie from the response headers
        setCookie = respLogin.headers["Set-Cookie"]
        redirectURL = respLogin.headers["location"]

        # format the parameters for the POST 
        headers={
            "Set-Cookie": setCookie,
        }

        # call the authorization URL retrieve the MyQ login page
        respRedirect = self._oAuthRequest(
            url=_OAUTH_BASE_URL+redirectURL,
            method="GET",
            headers=headers,
            allow_redirects=False,
        )

        # if an HTTP or network error occured, return login error code
        if respRedirect is None:
            self._logger.debug("Error in Step 3 of oAuth flow.")
            return LOGIN_ERROR

        # Step 4: Retrieve the access tokens     
                         
        redirectURL = respRedirect.headers["Location"]
        challengeCode = parse_qs(urlsplit(redirectURL).query).get("code", "")
        scope = parse_qs(urlsplit(redirectURL).query).get("scope", "MyQ_Residential offline_access")

        # format the parameters for the POST 
        params={
            "client_id": _OAUTH_CLIENT_ID,
            "client_secret": _OAUTH_CLIENT_SECRET,
            "code": challengeCode,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "redirect_uri": _OAUTH_REDIRECT_URI,
            "scope": scope
        }
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # post final challenge and retrieve the tokens
        respToken = self._oAuthRequest(
            url=_OAUTH_TOKEN_URL,
            method="POST",
            data=params,
            headers=headers,
        )

        # if an HTTP or network error occured, return login error code
        if respToken is None:
            self._logger.debug("Error in Step 4 of oAuth flow.")
            return LOGIN_ERROR
                      
        # Get the token from the response and add it to the session headers
        tokenInfo = respToken.json()
        self._accessToken = tokenInfo["access_token"]
        self._tokenType = tokenInfo["token_type"]
        self._refreshToken = tokenInfo["refresh_token"]
        self._tokenTTL = tokenInfo.get("expires_in", _OAUTH_TOKEN_TTL)
        self._lastTokenUpdate = time.time()

        return LOGIN_SUCCESS   

    def _oAuthRefreshToken(self):

        self._logger.info("Refreshing oAuth access token...")

        # call the oAuth service with the refresh token to retrieve a new access token
        params={
            "client_id": _OAUTH_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self._refreshToken,
        }
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # post final challenge and retrieve the tokens
        respToken = self._oAuthRequest(
            url=_OAUTH_TOKEN_URL,
            method="POST",
            data=params,
            headers=headers,
        )

        # if an HTTP or network error occured, return login error code
        if respToken is None:
            self._logger.error("Error refreshing access token with MyQ oAuth service.")
            return False

        if respToken.status_code == 200:

            # Get the token from the response and add it to the session headers
            tokenInfo = respToken.json()
            self._accessToken = tokenInfo["access_token"]
            self._tokenType = tokenInfo["token_type"]
            self._refreshToken = tokenInfo["refresh_token"]
            self._tokenTTL = tokenInfo.get("expires_in", _OAUTH_TOKEN_TTL)
            self._lastTokenUpdate = time.time()
            return True

        else:

            # log error data from response
            self._logger.error("Error refresing access token: %d - %s", respToken.json().get("code"), respToken.json().get("description"))

            # let the routine proceed with the current access token
            return True

    def _oAuthRequest(self, url, method="GET", params=None, data=None, headers=None, allow_redirects=False):
    
        # create HTTP session for oAuth calls
        if self._oAuthSession is None:
            self._oAuthSession = requests.Session()
            self._oAuthSession.headers.update(_OAUTH_SESSION_HEADERS)

        # call the specified URL with the specified method and parameters
        try:
            response = self._oAuthSession.request(
                url=url,
                method=method,
                params=params,
                data = data,  
                headers=headers,
                allow_redirects=allow_redirects,
                timeout= _HTTP_OAUTH_TIMEOUT,
            )
            
            # raise any codes other than 200 and 302 for error handling
            if response.status_code not in (200, 302):
                response.raise_for_status()

        # Log any temprary network errors - login will be retried
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            self._logger.warning("Network/server error logging into MyQ service: %s", str(e))
            return None

        # Bail on all other errors
        except:
            self._logger.error("Unexpected error occured: %s", sys.exc_info()[0])
            raise

        return response

# provide a consistent parsing of HTTP response messages for logging
def _parseResponseMsg(response):

    # should never be None, but just to be safe
    if response is not None:
        r = response.json()
        msg = "{} - {}: {}".format(r.get("code", "N/A"), r.get("message", "N/A"), r.get("description", "No message provided."))
    else:
        msg = "No error message provided."
    
    return msg

# return a string stripped of case, puncutation, and spaces
def _strip(string):
    return ''.join([letter.lower() for letter in ''.join(string) if letter.isalnum()])