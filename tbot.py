#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import os
import sys
import time
import zlib
import json
import base64
import socket
import threading
import subprocess
from urllib import request
from shutil import copyfile
import paho.mqtt.client as mqtt #pip3 install paho-mqtt


# Настройки
server = "http://<your_server_ip>/<your_html_file>.html"

# Глобальные переменные
localdb = dict()
localdb["statusList"] = list()
localdb["logList"] = list()
localdb["telemetryList"] = list()
mqttBuffer = dict()


class bcolors:
	DEBUG = '\033[95m'
	INFO = '\033[94m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	error = '\033[91m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'

class Autostart:
	def GetMyFullName():
		myFullName = sys.argv[0]
		return myFullName
	#end define

	def GetMyName():
		myFullName = Autostart.GetMyFullName()
		myName = myFullName[:myFullName.rfind('.')]
		return myName
	#end define

	def GetMyFullPath():
		myFullName = Autostart.GetMyFullName()
		myFullPath = os.path.abspath(myFullName)
		return myFullPath
	#end define

	def GetMyPath():
		myFullPath = Autostart.GetMyFullPath()
		myPath = myFullPath[:myFullPath.rfind('/')+1]
		return myPath
	#end define

	def CopyingYourself():
		src = Autostart.GetMyFullPath()
		myFullName = Autostart.GetMyFullName()
		dst = "/usr/local/bin/" + myFullName
		Autostart.AddLog("CopyingYourself to " + dst, "debug")
		copyfile(src, dst)
		os.remove(Autostart.GetMyFullPath())
	#end define

	def AddAutostart():
		import base64
		from urllib import request
		try:
			if (Autostart.CheckPermission() == False):
				Autostart.AddLog("Permission denied. Run the application as root.", "error")
				exit()
			if (Autostart.GetMyPath() == "/usr/local/bin/"):
				return
			else:
				Autostart.CopyingYourself()
			if (Autostart.CheckService() == True):
				Autostart.AddAutostartToService()
			else:
				Autostart.AddLog("'systemctl' and 'service' packages not found.", "error")
			exit()
		except Exception as error:
			Autostart.AddLog(str(error), "error")
	#end define

	def CreatService():
		Autostart.AddLog("CreatService", "debug")
		myName = Autostart.GetMyName()
		myFullName = Autostart.GetMyFullName()
		fileName = myName + ".service"
		faileDir = "/etc/systemd/system/"
		description = "Ping tester service for kgeu.ru"
		f = open(faileDir + fileName, 'w')
		f.write("[Unit]" + '\n')
		f.write("Description=" + description + '\n')
		f.write("After=multi-user.target" + '\n')
		f.write('\n')
		f.write("[Service]" + '\n')
		f.write("Type=idle" + '\n')
		f.write("ExecStart=/usr/bin/python3 /usr/local/bin/" + myFullName + '\n')
		f.write("Restart=always" + '\n')
		f.write('\n')
		f.write("[Install]" + '\n')
		f.write("WantedBy=multi-user.target" + '\n')
		f.write('\n')
		f.close()
		os.system("systemctl enable " + myName + " > /dev/null")
	#end define

	def StartService():
		Autostart.AddLog("StartService", "debug")
		myName = Autostart.GetMyName()
		os.system("service " + myName + " start > /dev/null")
	#end define

	def StopService():
		Autostart.AddLog("StopService", "debug")
		myName = Autostart.GetMyName()
		os.system("service " + myName + " stop > /dev/null")
	#end define

	def CheckService():
		response = os.system("service --status-all > /dev/null")
		if (response == 0):
			result = True
		else:
			result = False
		return result
	#end define

	def CheckPermission():
		response = os.system("touch /checkpermission > /dev/null")
		if (response == 0):
			os.system("rm -rf /checkpermission > /dev/null")
			result = True
		else:
			result = False
		return result
	#end define

	def AddAutostartToService():
		Autostart.StopService()
		Autostart.CreatService()
		Autostart.StartService()
	#end define

	def AddLog(inputText, mode="info"):
		myName = (sys.argv[0])[:(sys.argv[0]).rfind('.')]
		logName = myName + ".log"
		timeText = time.strftime("%d.%m.%Y, %H:%M:%S".ljust(22, ' '))
		if (mode == "info"):
			colorStart = bcolors.INFO + bcolors.BOLD
		elif (mode == "debug"):
			colorStart = bcolors.DEBUG + bcolors.BOLD
		elif (mode == "warning"):
			colorStart = bcolors.WARNING + bcolors.BOLD
		elif (mode == "error"):
			colorStart = bcolors.error + bcolors.BOLD
		else:
			colorStart = bcolors.UNDERLINE + bcolors.BOLD
		modeText = colorStart + ('[' + mode + ']').ljust(10, ' ') + bcolors.ENDC
		#modeText = modeText.ljust(23, ' ')
		logText = modeText + timeText + inputText
		file = open(logName, 'a')
		file.write(logText + '\n')
		file.close()
		
		allline = Autostart.count_lines(logName)
		if (allline > 4096 + 256):
			delline = allline - 4096
			f=open(logName).readlines()
			i = 0
			while i < delline:
				f.pop(0)
				i = i + 1
			with open(logName,'w') as F:
				F.writelines(f)
		if (Autostart.GetMyPath() != "/usr/local/bin/" or os.path.isfile(".debug")):
			print(logText)
	#end define

	def count_lines(filename, chunk_size=1<<13):
		if not os.path.isfile(filename):
			return 0
		with open(filename) as file:
			return sum(chunk.count('\n')
				for chunk in iter(lambda: file.read(chunk_size), ''))
	#end define
#end class

class MqttClient(threading.Thread):
	def __init__(self):
		self.localbuffer = dict()
		self.boardTempTopic = "/devices/hwmon/controls/Board Temperature"
		self.cpuTempTopic = "/devices/hwmon/controls/CPU Temperature"
		self.grayIpTopic = "/devices/network/controls/GPRS IP"
		self.vInTopic = "/devices/power_status/controls/Vin"
		self.sendDataTopic = "/devices/tbot/controls/sendData"
		threading.Thread.__init__(self)
	#end define
		
	def run(self):
		try:
			self.Main()
		except Exception as err:
			Autostart.AddLog(str(err), "error")
	#end define

	def Main(self):
		Autostart.AddLog("MqttClient.start", "debug")
		client = mqtt.Client()
		client.on_connect = self.on_connect
		client.on_disconnect = self.on_disconnect
		client.on_message = self.on_message
		client.connect("localhost", 1883)
		client.loop_forever()
	#end define

	def on_connect(self, client, userdata, flags, rc):
		Autostart.AddLog("MqttClient.on_connect", "debug")
		client.subscribe(self.boardTempTopic)
		client.subscribe(self.cpuTempTopic)
		client.subscribe(self.grayIpTopic)
		client.subscribe(self.vInTopic)
		client.subscribe(self.sendDataTopic)
	#end define

	def on_disconnect(self, client, userdata, rc):
		Autostart.AddLog("MqttClient.on_disconnect", "debug")
	#end define

	def on_message(self, client, userdata, message):
		topic = message.topic
		text = message.payload.decode().replace('\n', '')

		t1 = threading.Thread(target=self.MqttMessageReaction, args=(topic, text,))
		t1.start()
	#end define

	def MqttMessageReaction(self, topic, text):
		global mqttBuffer
		if (topic == self.boardTempTopic):
			self.localbuffer["boardTemp"] = text
		elif (topic == self.cpuTempTopic):
			self.localbuffer["cpuTemp"] = text
		elif (topic == self.grayIpTopic):
			self.localbuffer["grayIp"] = text
		elif (topic == self.vInTopic):
			self.localbuffer["vIn"] = text
		elif (topic == self.sendDataTopic):
			SendNow()
		mqttBuffer.update(self.localbuffer)
	#end define
#end class

class MqttPublisher(threading.Thread):
	def __init__(self):
		self.serverStatusTopic = "/devices/tbot/controls/serverStatus"
		self.pingTopic = "/devices/tbot/controls/ping"
		self.lastSendTimeTopic = "/devices/tbot/controls/time_SendData"
		self.lastGetTimeTopic = "/devices/tbot/controls/time_GetStatus"
		self.timeTopic = "/devices/tbot/controls/time"
		threading.Thread.__init__(self)
	#end define
		
	def run(self):
		try:
			self.Main()
		except Exception as err:
			Autostart.AddLog(str(err), "error")
	#end define

	def Main(self):
		Autostart.AddLog("MqttPublisher.start", "debug")
		self.client = mqtt.Client()
		self.client.connect("localhost", 1883)
		threading.Thread(target=self.MqttShowing).start()
		threading.Thread(target=self.StatusGetting).start()
	#end define

	def MqttShowing(self):
		Autostart.AddLog("MqttShowing", "debug")
		while True:
			time.sleep(1)
			threading.Thread(target=self.MqttShow).start()
	#end define

	def MqttShow(self):
		mqttBuffer["time"] = self.GetTime()
		self.client.publish(topic=self.timeTopic, payload=mqttBuffer["time"])
		self.client.publish(topic=self.pingTopic, payload=mqttBuffer["ping"])
		self.client.publish(topic=self.serverStatusTopic, payload=mqttBuffer["serverStatus"])
		self.client.publish(topic=self.lastGetTimeTopic, payload=mqttBuffer["lastGetTime"])
		self.client.publish(topic=self.lastSendTimeTopic, payload=mqttBuffer["lastSendTime"])
	#end define

	def StatusGetting(self):
		Autostart.AddLog("StatusGetting", "debug")
		while True:
			time.sleep(60) # 60 sec
			threading.Thread(target=self.StatusGet).start()
	#end define

	def StatusGet(self):
		mqttBuffer["ping"] = self.GetPing("google.com") or self.GetPing("yandex.ru") or self.GetPing("8.8.8.8")
		mqttBuffer["serverStatus"] = self.GetServerStatus()
		mqttBuffer["lastGetTime"] = self.GetTime()
	#end define

	def GetPing(self, hostname):
		text = subprocess.check_output("ping -c 1 -w 3 " + hostname, shell=True).decode("utf-8")
		if ("time=" in text):
			buffer = text[text.find("time=")+5:]
			time = buffer[:buffer.find('ms')+2]
		else:
			time = "null"
		return time
	#end define

	def GetServerStatus(self):
		result = "Offline"
		url = "http://<your_server_ip>/"
		try:
			text = request.urlopen(url).read().decode()
		except Exception as err:
			Autostart.AddLog(str(err), "debug")
		if ("Ok" in text):
			result = "Online"
		return result
	#end define

	def GetTime(self):
		result = time.strftime("%H:%M:%S")
		return result
	#end define
#end class

def GetOS():
	text = subprocess.check_output("cat /proc/version", shell=True).decode("utf-8")
	if ("Ubuntu" in text):
		result = "Ubuntu"
	elif ("OpenWrt" in text):
		result = "OpenWrt"
	elif ("Debian" in text):
		result = "Debian"
	else:
		result = "null"
	return result
#end define

def GetRequest(url):
	link = request.urlopen(url)
	data = link.read()
	text = data.decode("utf-8")
	return text
#end define

def Ping(hostname):
	response = os.system("ping -c 1 -w 3 " + hostname + " > /dev/null")
	if response == 0:
		result = True
	else:
		result = False
	return result
#end define

def CommunicationTest():
	global localdb
	timestamp = int(time.time())
	internetStatus = Ping("google.com") or Ping("yandex.ru") or Ping("8.8.8.8")
	vpnStatus = Ping("10.8.0.1") or Ping("10.9.0.1")
	buffer = {"timestamp":timestamp, "internetStatus":internetStatus, "vpnStatus":vpnStatus}
	localdb["statusList"].append(buffer)
#end define

def CommunicationTesting():
	while True:
		time.sleep(60) # 60 sec
		threading.Thread(target=CommunicationTest).start()
#end define

def ItemToBase64WithCompress(item):
	string = json.dumps(item)
	original = string.encode("utf-8")
	compressed = zlib.compress(original)
	b64 = base64.b64encode(compressed)
	data = b64.decode("utf-8")
	return data
#end define

def Base64ToItemWithDecompress(item):
	data = item.encode("utf-8")
	b64 = base64.b64decode(data)
	decompress = zlib.decompress(b64)
	original = decompress.decode("utf-8")
	data = json.loads(original)
	return data
#end define

def GetAverage(statusList):
	i = 0
	timestamp = 0
	internetStatusListBuffer = list()
	vpnStatusListBuffer = list()
	internetStatus = False
	vpnStatus = False
	for item in statusList:
		timestamp = item["timestamp"]
		internetStatusListBuffer.append(item["internetStatus"])
		vpnStatusListBuffer.append(item["vpnStatus"])
		i += 1
	if (sum(internetStatusListBuffer)>i/2):
		internetStatus = True
	if (sum(vpnStatusListBuffer)>i/2):
		vpnStatus = True
	data = {"timestamp":timestamp, "internetStatus":internetStatus, "vpnStatus":vpnStatus}
	return data
#end define

def DataSend(sendNow=False):
	global localdb
	while (sendNow or len(localdb["statusList"]) > 3 or len(localdb["logList"]) > 3 or len(localdb["telemetryList"]) > 3):
		sendNow = False
		hostname = socket.gethostname()
		statusList = GetItemsFromList(localdb["statusList"])
		logList = GetItemsFromList(localdb["logList"])
		telemetryList = GetItemsFromList(localdb["telemetryList"])
		buffer = {"hostname":hostname, "statusList": statusList, "logList":logList, "telemetryList":telemetryList}
		data = ItemToBase64WithCompress(buffer)
		url = server + "?data=" + data
		Autostart.AddLog("DataSend: " + url, "debug")
		try:
			GetRequest(url)
			mqttBuffer["lastSendTime"] = time.strftime("%H:%M:%S")
		except Exception as error:
			Autostart.AddLog(str(error), "error")
			RestoreList(localdb["statusList"], statusList)
			RestoreList(localdb["logList"], logList)
			return
#end define

def RestoreList(dstList, srcList):
	for item in srcList:
		dstList.append(item)
#end define

def GetItemsFromList(inputList, count=10):
	outputList = list()
	for i in range(count):
		if len(inputList) == 0:
			break
		buffer = inputList.pop(0)
		outputList.append(buffer)
	return outputList
#end define

def Sending():
	while True:
		time.sleep(600) # 600 sec
		threading.Thread(target=DataSend).start()
#end define

def SendNow():
	threading.Thread(target=DataSend, args=(True,)).start()
#end define

def Logging():
	file = open("/var/log/messages", 'r')
	null = file.read()
	while True:
		time.sleep(0.3)
		text = file.read()
		LogReaction(text)
#end define

def LogReaction(inputText):
	global localdb
	text_list = inputText.split('\n')
	for text in text_list:
		timestamp = int(time.time())
		debianLogList = ["Accepted password", "Received disconnect", "Exiting"]
		logList = debianLogList
		if (IsItemFromListInText(logList, text) == True):
		#if (len(text) > 0):
			buffer = {"timestamp":timestamp, "text":text}
			localdb["logList"].append(buffer)
			Autostart.AddLog("LogReaction", "debug")
#end define

def Saving():
	while True:
		time.sleep(3) # 3 sec
		threading.Thread(target=LocaldbSave).start()
#end define

def LocaldbSave():
	global localdb
	myName = Autostart.GetMyName()
	fileName = myName + ".db"
	string = ItemToBase64WithCompress(localdb)
	file = open(fileName, 'w')
	file.write(string)
	file.close()
#end define

def LocaldbLoad():
	global localdb
	Autostart.AddLog("LocaldbLoad", "debug")
	try:
		myName = Autostart.GetMyName()
		fileName = myName + ".db"
		if (os.path.isfile(fileName) == False):
			return
		file = open(fileName, 'r')
		original = file.read()
		localdb = Base64ToItemWithDecompress(original)
		file.close()
	except Exception as error:
		Autostart.AddLog(str(error), "error")
#end define

def IsItemFromListInText(inputList, text):
	result = False
	for item in inputList:
		if item in text:
			result = True
			break
	return result
#end define

def GettingInfo():
	while True:
		time.sleep(60) # 60 sec
		threading.Thread(target=GetInfo).start()
#end define

def GetInfo():
	global localdb
	timestamp = int(time.time())

	boardTemp = mqttBuffer["boardTemp"]
	cpuTemp = mqttBuffer["cpuTemp"]
	grayIp = mqttBuffer["grayIp"]
	vIn = mqttBuffer["vIn"]

	buffer = {"timestamp":timestamp, "boardTemp":boardTemp, "cpuTemp":cpuTemp, "grayIp":grayIp, "vIn":vIn}
	localdb["telemetryList"].append(buffer)
#end define


###
### Start of the program
###

# Уведомление о запуске
Autostart.AddLog("Start of the program", "info")
os.system("logger -i Start tbot service")

# Записаться в автозагрузку
Autostart.AddAutostart()

# Загрузить сохраненные данные
LocaldbLoad()

# Многопоточность
t1 = threading.Thread(target=CommunicationTesting)
t2 = threading.Thread(target=Sending)
t3 = threading.Thread(target=Logging)
t4 = threading.Thread(target=Saving)
t5 = threading.Thread(target=GettingInfo)

t1.start()
t2.start()
t3.start()
t4.start()
t5.start()

mqttClient = MqttClient()
mqttPublisher= MqttPublisher()

mqttClient.start()
mqttPublisher.start()


buffer = {"timestamp":int(time.time()), "text":"Start tbot service"}
localdb["logList"].append(buffer)
