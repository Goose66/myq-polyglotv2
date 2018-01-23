# myq-polyglotv2
A NodeServer for the Polyglot v2 that interfaces with LiftMaster's MyQ Web Service to allow the ISY 994i to control LiftMaster MyQ compatible garage door openers. See https://www.liftmaster.com/myqcompatibility for compatible garage door openers.

Instructions for Local (Co-resident with Polyglot) installation:

1. Install the MyQ nodeserver from the Polyglot Nodeserver Store, or do a Git from the repository to the folder ~/.polyglot/nodeservers/MyQ in your Polyglot v2 installation.
2. Log into the Polyglot Version 2 Dashboard (https://(Polyglot IP address):3000)
3. Add the MyQ nodeserver as a Local nodeserver type.
4. Add the following required Custom Configuration Parameters under Configuration:
```
    "username" = login name for LiftMaster MyQ account
    "password" = password for LiftMaster MyQ account
```
5. Add the following optional Custom Configuration Parameters:
```
    "tokenttl" = timeout for security token (secs) - defaults to 1200
    "activeupdateinterval" = polling interval when active (secs) - defaults to 20
    "inactiveupdateinterval" = polling interval when inactive (secs) - defaults to 60
```
