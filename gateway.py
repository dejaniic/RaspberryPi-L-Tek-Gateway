import pygatt.backends
import paho.mqtt.client as mqtt
import time
import timeit
import threading
import sys

global devices
global continuousRead
global client
continuousRead = []
# Klemen Skoda, FireFly, EDITED by Luka P.
# Configuration values needed to connect to IBM IoT Cloud
orgID = "ac6zwh" 		#For registered connection, replace with your organisation ID.
deviceType = "Rpi"  #For registered connection, replace with your Device Type.
deviceID = "FF-Rpi-GW" 				#For registered connection, replace with your Device ID.
auth_token = "dejan123" 			#For registered connection, replace with your Device authentication token.

class BLEdevice:

    deviceCount = 0
    busy = False
    
    def __init__(self, name, mac, interval, command):
        self.name = name
        self.mac = mac
        self.interval = interval
        self.command = command
        self.newCommand = ""
        self.commandToSend = False
        self.end = False
        BLEdevice.deviceCount += 1

    def lowerCount(self):
        BLEdevice.deviceCount -= 1

    def makeBusy(self):
        BLEdevice.busy = True

    def free(self):
        BLEdevice.busy = False

    def endThread(self):
        self.end = True

    def changeCommand(self, newCommand, newInterval):
        self.command = newCommand
        self.interval = newInterval

class myThread(threading.Thread):

    def __init__(self, threadID, device):
        print("Thread initialized!")
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.device = device

    def run(self):
        print("Thread started!")
        loopRead(self.threadID, self.device)
        print("Thread ended!")


#Callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))

    if(orgID != 'quickstart'):
        #Subscribing in on_connect() means tha if we lose the connection and reconnect the subscription will be renewed.
        client.subscribe("iot-2/cmd/+/fmt/json", 0)
        print("subscribed to iot-2/cmd/+/fmt/json")

#The callback for then a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print("\n----------------------------------------------")
    print("MSG received on TOPIC: " + msg.topic + "\npayload: " +str(msg.payload) + "\n")

    if(len(msg.payload)>13):
        nodeID = msg.payload[8:11]
        command = msg.payload[11:12]

        mac = findAddress(nodeID, adapter)
        #print(mac)
        if(mac == 'null'):
            while True:
                if(BLEdevice.busy == False):
                    BLEdevice.busy = True
                    adapter.start()
                    global devices
                    #print(devices)
                    devices = scanForDevices()
                    mac = findAddress(nodeID, adapter)
                    BLEdevice.busy = False
                    break

        if(mac != 'null'):
            if  (command == '0'):
                found = False
                
                for item in continuousRead:
                    if(item.device.name == nodeID):
                        found = True

                if(found == False):
                    connection = tryConnect(adapter, mac)
                    writeCommand(connection, nodeID, msg.payload[8:len(msg.payload)-2])
                    time.sleep(0.1)
                    readChar(connection, mac)

            elif(command == '1'):
                units = msg.payload[12:13]
                interval = int(msg.payload[13:15])
                print(units)
                print(interval)
                if  (units == '1'):
                    interval = interval * 3600
                elif(units == '2'):
                    interval = interval * 60
                elif(units == '3'):
                    interval = interval
                elif(units == '4'):
                    interval = interval / 10

                print(interval)
                found = False
                
                global continuousRead

                for item in continuousRead:
                    if(item.device.name == nodeID):
                        print("Changing command!")
                        found = True
                        item.device.changeCommand(msg.payload[8:len(msg.payload)-2], interval)
                        item.device.newCommand = msg.payload[8:len(msg.payload)-2]
                        item.device.commandToSend = True

                if(found == False):
                    device = BLEdevice(nodeID, mac, interval, msg.payload[8:len(msg.payload)-2])
                    t = myThread(device.deviceCount, device)
                    t.start()
                    continuousRead.append(t)
                    print(continuousRead)
                    print("Added new device, number of connected devices: " + t.device.deviceCount)
                
                
            elif(command == '2'):
                global continuousRead
                print(continuousRead)
                for item in continuousRead:
                    if(item.device.name == nodeID):
                        item.device.lowerCount()
                        item.device.changeCommand(command, 10)
                        item.device.endThread()
                        continuousRead.remove(item)
                        print(continuousRead)
                        break

            elif(command == '3' or command == '4'):
                found = False
                
                for item in continuousRead:
                    if(item.device.name == nodeID):
                        print("Sending command!")
                        found = True
                        item.device.newCommand = msg.payload[8:len(msg.payload)-2]
                        item.device.commandToSend = True

                if(found == False):
                    connection = tryConnect(adapter, mac)
                    writeCommand(connection, nodeID, msg.payload[8:len(msg.payload)-2])

                
            #adapter.reset()
            #adapter.start()

def writeCommand(firefly, endNode, cmd):
    cmd = endNode + cmd
    print("Writing command " + cmd + "to sensor with ID: " + endNode)
    firefly.char_write_handle(24, map(ord, cmd))

def readChar(firefly,mac):
    try:
        received = firefly.char_read_hnd(24)
        print(received)
        if(len(received) > 30):
            publishMQTT(received, client)
    except pygatt.exceptions.NotificationTimeout:
        print("passed")

def loopRead(thread, device):
    print("normal")
    error = 0
    connection = None
    adapterTmp = pygatt.backends.GATTToolBackend()
    #adapterTmp.reset()
    adapterTmp.start()
    passed = False
    
    while True:
        if(passed == False):
            time1 = time.clock()

        #   ending thread if we got "kill continuous response" command
        if(device.end == True):
            device.makeBusy()
            try:
                writeCommand(connection, device.name, device.command)
            except:
                connection = tryConnect(adapterTmp, device.mac)
                try:
                    writeCommand(connection, device.name, device.command)
                except:
                    pass
            device.free()
            if(connection != None):
                connection.disconnect()
            break
        
        try:
            if(error > 2):
                error = 0
                connection = None

            if(connection is None and device.busy == False):
                device.makeBusy()
                connection = tryConnect(adapterTmp, device.mac)
                try:
                    writeCommand(connection, device.name, device.command)
                except:
                    pass
                device.free()
                time.sleep(0.1)
            if(connection != None):
                passed = False
                received = connection.char_read_hnd(24)
                print(received)
                if(len(received) > 30):
                    publishMQTT(received, client)
                error = 0
                if(device.commandToSend == True):
                    try:
                        writeCommand(connection, device.name, device.newCommand)
                    except:
                        pass
                    device.commandToSend = False
        except pygatt.exceptions.NotificationTimeout:
            error += 1
            passed = True
            print("passed ")
            print(thread)
        
        if(passed == False):
            time2 = time.clock()
            delay1 = device.interval - (time2 - time1)

            print(delay1)
            if(delay1 < 0):
                delay1 = 0

            #   this part of the code disconnects from FlyTag module so it's visible by other devices,
            #   in this case if interval is longer than 10seconds
            if(device.interval >= 10 and connection != None):
                connection.disconnect()
                connection = None
            time.sleep(delay1)
            
def tryConnect(adapter2, mac):

    error = 0
    
    while True:
        try:
            print("Trying to connect...")
            if(error > 3):
                print("Could not reconnect.")
                return 'null'
            else:
                return(adapter2.connect(mac, 5, 'random'))
            break
        except pygatt.exceptions.NotConnectedError:
            error += 1
            print("Had an Error...")
            time.sleep(2)
            pass

def scanForDevices():
    tmp = adapter.scan(3,True)
    print("Filter devices to use only firefly devices")
    return([device for device in tmp if str(device["name"]).startswith("FF-")])
    
def findAddress(endNode, adapter1):
    print("Finding address for endNode: " + endNode)
    endNode = "FF-" + endNode
    print("endNode ID: " + endNode)
    print("List of all connected devices:")
    print(devices)
    print("\n")
    for i in range(len(devices)):
        if(devices[i]['name'] == endNode):
            print("Found device: " + devices[i]['address'])
            return(devices[i]['address'])
    print("Device not present")
    return("null")

def publishMQTT(data, clientMQTT):
    g2x = (data[4] << 8) | (data[5])
    g2y = (data[6] << 8) | (data[7])
    g2z = (data[8] << 8) | (data[9])

    gx = g2x * 0.003125
    gy = g2y * 0.003125
    gz = g2z * 0.003125

    ax = (data[10] << 8) | data[11]
    ay = (data[12] << 8) | data[13] 
    az = (data[14] << 8) | data[15] 

    a1x = ax / 16384.0
    a1y = ay / 16384.0
    a1z = az / 16384.0

    if (data[10] > 127):
        a1x = a1x - 4.0
    if (data[12]> 127):
        a1y = a1y - 4.0
    if (data[14]> 127):
        a1z = a1z - 4.0

    mx = (data[16] << 8) | data[17]
    my = (data[18] << 8) | data[19] 
    mz = (data[20] << 8) | data[21]

    if (data[16] > 127):
        mx = mx - 65536
    if (data[18]> 127):
        my = my - 65536
    if (data[20]> 127):
        mz = mz - 65536

    lux = (data[26] << 8) | data[27]

    t = (data[22] << 8) | data[23]
    temp = ((175.72 * t) / 65536) - 46.85
    
    rh = (data[24] << 8) | data[25]
    humid = ((125.0 * rh) / 65536) - 6

    analog = data[30]

    print("Publishing MQTT msg")
    sendData = ("{\"d\": {\"ID\":\"FF-%c%c%c\",\"gX\":%.2f,\"gY\":%.2f,\"gZ\":%.2f,\"aX\":%.2f,\"aY\":%.2f,\"aZ\":%.2f,\"mX\":%d,\"mY\":%d,\"mZ\":%d,\"Lux\": %d, \"Temp\": %.1f,\"RelHum\" :%.1f, \"Analog\":%d}}" % (data[0],data[1], data[2], gx, gy, gz, a1x, a1y, a1z, mx, my, mz, lux, temp, humid, analog))
    clientMQTT.publish("iot-2/evt/testing/fmt/json", sendData)

try:

    if(orgID == 'quickstart'):
        mac = open('/sys/class/net/eth0/address').read()
        mac = mac.replace(":","")
        mac = mac[0:12]
        print(mac)
        client = mqtt.Client("d:quickstart:"+deviceType+":"+mac)
        print("d:quickstart:"+ deviceType +":" + mac)

        client.on_connect = on_connect
        client.on_message = on_message
        
        client.connect("quickstart.messaging.internetofthings.ibmcloud.com", 1883, 60)
    else:
        client = mqtt.Client("d:"+orgID+ ":" +deviceType+":" + deviceID)

        client.on_connect = on_connect
        client.on_message = on_message
        
        client.connect(orgID+".messaging.internetofthings.ibmcloud.com", 1883, 15)
        client.username_pw_set("use-token-auth", auth_token)
    
    
    print("Get adapter obj")
    adapter = pygatt.backends.GATTToolBackend()
    adapter.reset()
    adapter.start()
    print("Scanning for devices...")
    devices = scanForDevices()
    print("List of connected devices: ")
    print(devices)
    print("\n")

    if(orgID == 'quickstart'):
        connect = 0;
        for i in range(len(devices)):
            if(connect<3):
                try:
                    if(devices[i]['name'].startswith('FF-')):
                        print(devices[i]['address'])
                        print(devices[i]['name'][3:6])
                        device = BLEdevice(devices[i]['name'][3:6], devices[i]['address'], 5, '0001305')
                        t = myThread(device.deviceCount, device)
                        t.start()
                        continuousRead.append(t)
                        print(continuousRead)
                        print(t.device.deviceCount)
                        connect+=1
                except Exception as e:
                    #print e
                    pass

    while(True):
        print("main")
        client.loop_forever()

except KeyboardInterrupt:
    print("Exiting program!")
    for item in continuousRead:
        item.device.lowerCount()
        item.device.changeCommand("0002", 10)
        item.device.endThread()
        continuousRead.remove(item)
        print(continuousRead)
        
    sys.exit(1)

