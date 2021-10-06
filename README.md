# myq-polyglotv2
A NodeServer for the Polyglot v2 that interfaces with LiftMaster/Chamberlain MyQ Web Service to allow the ISY 994i to control LiftMaster/Chamberlain MyQ compatible garage door openers and light modules. See https://www.liftmaster.com/myqcompatibility for compatible garage door openers, gateways, and modules.

### Instructions for local Polyglot-V2 installation:

From the Polyglot Dashboard:
1. Install the MyQ nodeserver from the Polyglot Nodeserver Store.
2. Add the MyQ nodeserver as a Local (Co-Resident with Polyglot) nodeserver type.
3. Add/modify the following Configuration Parameters under Configuration (note that the keys are added on first run with default values):

    #### Advanced Configuration:
    - key: shortPoll, value: polling interval for MyQ cloud service in "active" polling mode (defaults to 10 seconds - minimum polling interval).
    - key: longPoll, value: polling interval for MyQ cloud service when not in "active" polling mode (defaults to 60 seconds).

    #### Custom Configuration Parameters:
    - key: username, value: username (email address) for MyQ online account (required)
    - key: password, value: password for MyQ online account (required)
    - key: homename, value: home name from which to load devices (if your account has access to multiple homes) (optional)

4. Start (Restart) the MyQ nodeserver from the Polyglot Dashboard
5. Once the MyQ Service node appears in ISY994i Adminstative Console and the MyQ Service shows connected, click "Discover Devices" to load nodes for the gateways, garage door openers, and light modules configured in your account. The MyQ Service connection status may take a minute or two to show connected, so please be patient. Also, please check the Polyglot Dashboard for messages regarding connection and Discover Devices failure conditions.

Notes for this version (v2.3.17):

1. This version works with Polyglot Cloud (PGC) through the ISY Portal. Note that you may want to increase the shortPoll configuration value to 20 seconds from the default of 10 seconds to save ISY resources. Also note that due to PGC peculiarities, the initial states of nodes don't show until they are changed through the nodeserver (doors opened or closed) and there is increase latency between sending a command and receiving the changed state.
2. The nodeserver does not attempt to connect and login to the MyQ service until the first longpoll - approximately 60 seconds after the nodeserver starts. This is done to allow network components to reestablish connections when recovering from a power failure. The nodeserver will continue to attempt to connect and login every longpoll (e.g., every 60 seconds) until a connection is established, so watch your Polyglot Dashboard messages for connection errors or bad credentials when starting/restarting to avoid locking out your account.
3. If you have multiple accounts (referred to in the MyQ app as "Homes") authorized to your MyQ account, the nodeserver loads the first one in the list by default. To change this, add the "homename" configuration parameter to the Custom Configuration Parameters with the name of the "home" you want to use. You can find the "Home Name" at the top of the device list in the MyQ mobile app.
4. Upon selecting "Discover Devices," garage door opener and light module nodes are grouped under the gateway through which they are accessed. The node for the MyQ Nodeserver is separate. This is due to the single level nesting restriction in the ISY Administration Console. You can "Ungroup" the device nodes from under the gateway nodes through the Admin console user interface.
5. When you close a garage door using a remote command (e.g., through the MyQ service), there is a ~10 second alarming period. During this period, the status may change from "Closing" to "Open" before finally changing to "Closed," depending on the timing of the status polling.
6. To delete a garage door opener node, you must use the Polyglot Version 2 Dashboard. If you delete the node from the ISY Administrative Console, it will reappear the next that Polyglot and/or the MyQ nodeserver are restarted.
7. The code will filter any invalid characters from the garage door opener description (like [ ] ( ) < > \ / * ! & ? ; " ') before adding the Node to the ISY. You can rename the nodes in the ISY as you like.

For more information regarding this Polyglot Nodeserver, see https://forum.universal-devices.com/topic/22479-polyglot-myq-nodeserver/.