# myq-polyglotv2
A NodeServer for the Polyglot v2 that interfaces with LiftMaster/Chamberlain MyQ Web Service to allow the ISY 994i to control LiftMaster/Chamberlain MyQ compatible garage door openers and light modules. See https://www.liftmaster.com/myqcompatibility for compatible garage door openers, gateways, and modules.

### Instructions for local Polyglot-V2 installation:

1. Install the MyQ nodeserver from the Polyglot Nodeserver Store.
2. Log into the Polyglot Dashboard (https://<Polyglot Server address>:3000)
3. Add the MyQ nodeserver as a Local (Co-Resident with Polyglot) nodeserver type.
4. Add the following required Custom Configuration Parameters under Configuration:
```
    "username" = login name for MyQ account
    "password" = password for MyQ account
```
5. Add the following optional Custom Configuration Parameters:
```
    "tokenttl" = timeout for security token (secs) - defaults to 1200
    "activeupdateinterval" = polling interval when active (secs) - defaults to 10
    "inactiveupdateinterval" = polling interval when inactive (secs) - defaults to 60
```
6. Once the MyQ Service node appears in ISY994i Adminstative Console, click "Discover Devices" to load nodes for the gateways, garage door openers, and light modules configured in your account.

Here are the currently known anomalies:

1. Upon selecting "Discover Devices," garage door opener and light module nodes are grouped under the gateway through which they are accessed. The node for the MyQ Nodeserver is separate. This is due to the single level nesting restriction in the ISY Administration Console. You can "Ungroup" the device nodes from under the gateway nodes through the Admin console user interface.
2. The code will filter any invalid characters from the garage door opener description (like [ ] ( ) < > \ / * ! & ? ; " ') before adding the Node to the ISY. You can rename the nodes in the ISY as you like.
3. When you close a garage door using a remote command (e.g., through the MyQ service), there is a ~10 second alarming period. During this period, the status may change from "Closing" to "Open" before finally changing to "Closed," depending on the timing of the status polling.
4. To delete a garage door opener node, you must use the Polyglot Version 2 Dashboard. If you delete the node from the ISY Administrative Console, it will reappear the next that Polyglot and/or the MyQ nodeserver are restarted.
5. The Nodeserver checks for bad credentials and authentication errors when starting and provides associated messages in the Polyglot Dashboard, and then stops the nodeserver. However, once it begins polling, any authentication problems (password changed, account lockout, etc.) will be logged, but the nodeserver continues to operate and poll without any messages in the Dashboard. The "MyQ Service Connected" state in the MyQ Service node should indicate False, but the logs will have to be checked to determine the source of the problem.

For more information regarding this Polyglot Nodeserver, see https://forum.universal-devices.com/topic/22479-polyglot-myq-nodeserver/.