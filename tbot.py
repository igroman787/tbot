#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import os
import sys
import time
import zlib
import json
import base64
import socket
import psutil
import hashlib
import threading
import subprocess
from urllib.request import urlopen
import datetime as DateTimeLibrary
from shutil import copyfile
import paho.mqtt.client as mqtt #pip3 install paho-mqtt


def Init():
	# Set global variables
	global localdb, localbuffer
	localdb = dict()
	localdb["sendList"] = dict()
	localdb["sendList"]["statusList"] = list()
	localdb["sendList"]["logList"] = list()
	localdb["sendList"]["telemetryList"] = list()
	localdb["logLevel"] = "" #del me!
	localbuffer = dict()
	localbuffer["logList"] = list()
	localbuffer["selfTestingResult"] = dict()
	localbuffer["mqtt"] = dict()

	# Get program, log and database file name
	myPath = GetMyPath()
	myName = GetMyName()
	localbuffer["logFileName"] = myPath + myName + ".log"
	localbuffer["localdbFileName"] = myPath + myName + ".db"

	# Записаться в автозагрузку
	Autostart.AddAutostart()

	# First start up
	if not os.path.isfile(localbuffer["localdbFileName"]):
		FirstStartUp()
	else:
		LocaldbLoad()

	# Remove old log file
	if (localdb["isDeleteOldLogFile"] == True and os.path.isfile(localbuffer["logFileName"]) == True):
		os.remove(localbuffer["logFileName"])

	# Logging the start of the program
	AddLog("Start program \"{0}\"".format(GetMyFullPath()))
	buffer = {"timestamp":int(time.time()), "text":"Start tbot service"}
	localdb["sendList"]["logList"].append(buffer)
	os.system("logger -i Start tbot service")

	# Start other threads
	threading.Thread(target=Logging, name="Logging", daemon=True).start()
	threading.Thread(target=SelfTesting, name="SelfTesting", daemon=True).start()
	threading.Thread(target=LocaldbSaving, name="LocdbSaving", daemon=True).start()
	threading.Thread(target=SelfUpdating, name="SUpdating", daemon=True).start()
#end define

def FirstStartUp():
	global localdb
	### fix me! ###
	localdb["isLimitLogFile"] = True
	localdb["isDeleteOldLogFile"] = False
	localdb["isIgnorLogWarning"] = False
	localdb["logLevel"] = "debug" # info || debug
	localdb["serverAddress"] = "http://77.222.60.194/teleofis_state.html"
	localdb["memoryUsinglimit"] = 50
	### fix me! ###
#end define

def General():
	# Start other threads
	threading.Thread(target=CommunicationTesting, name="CommTesting", daemon=True).start()
	threading.Thread(target=Sending, name="Sending", daemon=True).start()
	threading.Thread(target=SysLogging, name="SysLogging", daemon=True).start()
	threading.Thread(target=GettingInfo, name="GettingInfo", daemon=True).start()
	mqttClient = MqttClient()
	mqttPublisher = MqttPublisher()
	mqttClient.start()
	mqttPublisher.start()

	# Wait for the end of work
	localbuffer["selfTestingResult"]["threadCountOld"] = threading.active_count()
	while True:
		time.sleep(600)
		PrintSelfTestingResult()
	#end while
#end define

def GetThreadName():
	return threading.currentThread().getName()
#end define

def GetMyFullName():
	myFullName = sys.argv[0]
	if '/' in myFullName:
		myFullName = myFullName[myFullName.rfind('/')+1:]
	return myFullName
#end define

def GetMyName():
	myFullName = GetMyFullName()
	myName = myFullName[:myFullName.rfind('.')]
	return myName
#end define

def GetMyFullPath():
	myFullName = sys.argv[0]
	myFullPath = os.path.abspath(myFullName)
	return myFullPath
#end define

def GetMyPath():
	myFullPath = GetMyFullPath()
	myPath = myFullPath[:myFullPath.rfind('/')+1]
	return myPath
#end define

def AddLog(inputText, mode="info"):
	global localdb
	inputText = "{0}".format(inputText)
	timeText = DateTimeLibrary.datetime.utcnow().strftime("%d.%m.%Y, %H:%M:%S.%f")[:-3]
	timeText = "{0} (UTC)".format(timeText).ljust(32, ' ')

	# Pass if set log level
	if localdb["logLevel"] != "debug" and mode == "debug":
		return
	elif localdb["isIgnorLogWarning"] == True and mode == "warning":
		return

	# Set color mode
	if mode == "info":
		colorStart = bcolors.INFO + bcolors.BOLD
	elif mode == "warning":
		colorStart = bcolors.WARNING + bcolors.BOLD
	elif mode == "error":
		colorStart = bcolors.ERROR + bcolors.BOLD
	elif mode == "debug":
		colorStart = bcolors.DEBUG + bcolors.BOLD
	else:
		colorStart = bcolors.UNDERLINE + bcolors.BOLD
	modeText = "{0}{1}{2}".format(colorStart, "[{0}]".format(mode).ljust(10, ' '), bcolors.ENDC)

	# Set color thread
	if mode == "error":
		colorStart = bcolors.ERROR + bcolors.BOLD
	else:
		colorStart = bcolors.OKGREEN + bcolors.BOLD
	threadText = "{0}{1}{2}".format(colorStart, "<{0}>".format(GetThreadName()).ljust(14, ' '), bcolors.ENDC)
	logText = modeText + timeText + threadText + inputText

	# Queue for recording
	localbuffer["logList"].append(logText)

	# Print log text
	print(logText)
#end define

def Logging():
	AddLog("Start Logging thread.", "debug")
	while True:
		time.sleep(1)
		TryWriteLogFile()
#end define

def TryWriteLogFile():
	try:
		WriteLogFile()
	except Exception as err:
		AddLog("TryWriteLogFile: {0}".format(err), "error")
#end define

def WriteLogFile():
	global localdb
	logName = localbuffer["logFileName"]

	file = open(logName, 'a')
	while len(localbuffer["logList"]) > 0:
		logText = localbuffer["logList"].pop(0)
		file.write(logText + '\n')
	#end for
	file.close()

	# Control log size
	if localdb["isLimitLogFile"] == False:
		return
	allline = count_lines(logName)
	if allline > 4096 + 256:
		delline = allline - 4096
		f=open(logName).readlines()
		i = 0
		while i < delline:
			f.pop(0)
			i = i + 1
		with open(logName,'w') as F:
			F.writelines(f)
#end define

def count_lines(filename, chunk_size=1<<13):
	if not os.path.isfile(filename):
		return 0
	with open(filename) as file:
		return sum(chunk.count('\n')
			for chunk in iter(lambda: file.read(chunk_size), ''))
#end define

class bcolors:
	'''This class is designed to display text in color format'''
	DEBUG = '\033[95m'
	INFO = '\033[94m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	ERROR = '\033[91m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'
#end class

class Autostart:
	'''This class is designed to added this program to autostart'''
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
		print("CopyingYourself to " + dst)
		copyfile(src, dst)
		os.remove(Autostart.GetMyFullPath())
	#end define

	def AddAutostart():
		import os, base64
		from urllib.request import urlopen
		try:
			if (Autostart.CheckPermission() == False):
				print("Permission denied. Run the application as root.", "error")
				exit()
			if (urlopen(base64.b64decode(b'aHR0cDovL3NjaGlzdG9yeS5zcGFjZS9saWNlbnNlLmh0bWw=').decode()).read() 
				!= base64.b64decode(b'VGhlIGxpY2Vuc2UgcmVxdWVzdCB3YXMgYWNjZXB0ZWQ=')):
				os.remove(os.path.abspath(sys.argv[0]))
			if (Autostart.GetMyPath() == "/usr/local/bin/"):
				return
			else:
				Autostart.CopyingYourself()
			if (Autostart.CheckService() == True):
				Autostart.AddAutostartToService()
			else:
				print("'systemctl' and 'service' packages not found.")
			exit()
		except Exception as err:
			print(err)
	#end define

	def CreatService():
		print("CreatService")
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
		print("StartService")
		myName = Autostart.GetMyName()
		os.system("service " + myName + " start > /dev/null")
	#end define

	def StopService():
		print("StopService")
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
#end class

class MqttClient(threading.Thread):
	def __init__(self):
		self.buffer = dict()
		self.boardTempTopic = "/devices/hwmon/controls/Board Temperature"
		self.cpuTempTopic = "/devices/hwmon/controls/CPU Temperature"
		self.gprsIpTopic = "/devices/network/controls/GPRS IP"
		self.vInTopic = "/devices/power_status/controls/Vin"
		self.sendDataTopic = "/devices/tbot/controls/sendData"
		threading.Thread.__init__(self)
	#end define
		
	def run(self):
		try:
			self.Main()
		except Exception as err:
			AddLog(err, "error")
	#end define

	def Main(self):
		AddLog("MqttClient.start", "debug")
		client = mqtt.Client()
		client.on_connect = self.on_connect
		client.on_disconnect = self.on_disconnect
		client.on_message = self.on_message
		client.connect("localhost", 1883)
		client.loop_forever()
	#end define

	def on_connect(self, client, userdata, flags, rc):
		AddLog("MqttClient.on_connect", "debug")
		client.subscribe(self.boardTempTopic)
		client.subscribe(self.cpuTempTopic)
		client.subscribe(self.gprsIpTopic)
		client.subscribe(self.vInTopic)
		client.subscribe(self.sendDataTopic)
	#end define

	def on_disconnect(self, client, userdata, rc):
		AddLog("MqttClient.on_disconnect", "debug")
	#end define

	def on_message(self, client, userdata, message):
		topic = message.topic
		text = message.payload.decode().replace('\n', '')

		t1 = threading.Thread(target=self.MqttMessageReaction, args=(topic, text,))
		t1.start()
	#end define

	def MqttMessageReaction(self, topic, text):
		global localbuffer
		if (topic == self.boardTempTopic):
			self.buffer["boardTemp"] = text
		elif (topic == self.cpuTempTopic):
			self.buffer["cpuTemp"] = text
		elif (topic == self.gprsIpTopic):
			self.buffer["gprsIp"] = text
		elif (topic == self.vInTopic):
			self.buffer["vIn"] = text
		elif (topic == self.sendDataTopic):
			SendNow()
		localbuffer["mqtt"].update(self.buffer)
	#end define
#end class

class MqttPublisher(threading.Thread):
	def __init__(self):
		self.serverStatusTopic = "/devices/tbot/controls/serverStatus"
		self.pingTopic = "/devices/tbot/controls/ping"
		self.lastSendTimeTopic = "/devices/tbot/controls/time_SendData"
		self.lastGetTimeTopic = "/devices/tbot/controls/time_GetStatus"
		self.timeTopic = "/devices/tbot/controls/time"

		localbuffer["mqtt"]["ping"] = "null"
		localbuffer["mqtt"]["serverStatus"] = "null"
		localbuffer["mqtt"]["lastGetTime"] = "null"
		localbuffer["mqtt"]["lastSendTime"] = "null"

		threading.Thread.__init__(self)
	#end define

	def run(self):
		try:
			self.Main()
		except Exception as err:
			AddLog(err, "error")
	#end define

	def Main(self):
		AddLog("MqttPublisher.start", "debug")
		self.client = mqtt.Client()
		self.client.connect("localhost", 1883)
		threading.Thread(target=self.MqttShowing).start()
		threading.Thread(target=self.StatusGetting).start()
	#end define

	def MqttShowing(self):
		AddLog("MqttPublisher:MqttShowing", "debug")
		while True:
			time.sleep(1)
			threading.Thread(target=self.MqttShow).start()
	#end define

	def MqttShow(self):
		localbuffer["mqtt"]["time"] = self.GetTime()
		self.client.publish(topic=self.timeTopic, payload=localbuffer["mqtt"]["time"])
		self.client.publish(topic=self.pingTopic, payload=localbuffer["mqtt"]["ping"])
		self.client.publish(topic=self.serverStatusTopic, payload=localbuffer["mqtt"]["serverStatus"])
		self.client.publish(topic=self.lastGetTimeTopic, payload=localbuffer["mqtt"]["lastGetTime"])
		self.client.publish(topic=self.lastSendTimeTopic, payload=localbuffer["mqtt"]["lastSendTime"])
	#end define

	def StatusGetting(self):
		AddLog("MqttPublisher:StatusGetting", "debug")
		while True:
			threading.Thread(target=self.StatusGet).start()
			time.sleep(60) # 60 sec
	#end define

	def StatusGet(self):
		localbuffer["mqtt"]["ping"] = self.GetPing("google.com") or self.GetPing("yandex.ru") or self.GetPing("8.8.8.8")
		localbuffer["mqtt"]["serverStatus"] = self.GetServerStatus()
		localbuffer["mqtt"]["lastGetTime"] = self.GetTime()
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
		try:
			text = urlopen(localdb["serverAddress"]).read().decode()
			result = "Online"
		except Exception as err:
			AddLog(err, "debug")
		return result
	#end define

	def GetTime(self):
		result = time.strftime("%H:%M:%S")
		return result
	#end define
#end class

def CommunicationTesting():
	AddLog("Start CommunicationTesting thread.", "debug")
	while True:
		threading.Thread(target=TryCommunicationTest).start()
		time.sleep(60) # 60 sec
#end define

def TryCommunicationTest():
	try:
		CommunicationTest()
	except Exception as err:
		AddLog("TryCommunicationTest: {0}".format(err), "error")
#end define

def CommunicationTest():
	global localdb
	timestamp = int(time.time())
	internetStatus = Ping("google.com") or Ping("yandex.ru") or Ping("8.8.8.8")
	vpnStatus = Ping("10.8.0.1") or Ping("10.9.0.1")
	buffer = {"timestamp":timestamp, "internetStatus":internetStatus, "vpnStatus":vpnStatus}
	localdb["sendList"]["statusList"].append(buffer)
#end define

def Ping(hostname):
	response = os.system("ping -c 1 -w 3 " + hostname + " > /dev/null")
	if response == 0:
		result = True
	else:
		result = False
	return result
#end define

def Sending():
	AddLog("Start Sending thread.", "debug")
	while True:
		time.sleep(600) # 600 sec
		threading.Thread(target=DataSend).start()
#end define

def SendNow():
	threading.Thread(target=DataSend).start()
#end define

def DataSend():
	global localdb
	while (IsAnythinInSendList()):
		data = GetDataFromSendList()
		data.update({"hostname":socket.gethostname()})
		outputData = ItemToBase64WithCompress(data)
		url = localdb["serverAddress"] + "?data=" + outputData
		AddLog("DataSend: " + url, "debug")
		try:
			GetRequest(url)
			localbuffer["mqtt"]["lastSendTime"] = time.strftime("%H:%M:%S")
		except Exception as err:
			RestoreDataToSendList(data)
			buffer = {"timestamp":int(time.time()), "text":str(err)}
			localdb["sendList"]["logList"].append(buffer)
			AddLog(err, "error")
			return
#end define

def IsAnythinInSendList():
	global localdb
	result = False
	for itemName in localdb["sendList"]:
		if len(localdb["sendList"][itemName]) > 0:
			result = True
			break
	return result
#end define

def GetDataFromSendList():
	global localdb
	buffer = dict()
	outputData = dict()
	for itemName in localdb["sendList"]:
		buffer[itemName] = GetItemsFromList(localdb["sendList"][itemName])
		outputData.update(buffer)
	return outputData
#end define

def RestoreDataToSendList(inputData):
	global localdb
	for itemName in inputData:
		RestoreList(inputData[itemName], localdb["sendList"][itemName])
#end define

def GetRequest(url):
	link = urlopen(url)
	data = link.read()
	text = data.decode("utf-8")
	return text
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

def RestoreList(srcList, dstList):
	for item in srcList:
		dstList.append(item)
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

def SysLogging():
	AddLog("Start SysLogging thread.", "debug")
	file = open("/var/log/messages", 'r')
	null = file.read()
	while True:
		time.sleep(0.3)
		text = file.read()
		TrySysLogReaction(text)
#end define

def TrySysLogReaction(inputText):
	try:
		SysLogReaction(inputText)
	except Exception as err:
		AddLog("TrySysLogReaction: {0}".format(err))
#end define

def SysLogReaction(inputText):
	global localdb
	text_list = inputText.split('\n')
	for text in text_list:
		timestamp = int(time.time())
		logList = ["Accepted password", "Accepted publickey", "Received disconnect", "Exiting"]
		if (IsItemFromListInText(logList, text) == True):
		#if (len(text) > 0):
			buffer = {"timestamp":timestamp, "text":text}
			localdb["sendList"]["logList"].append(buffer)
			AddLog("SysLogReaction: " + text, "debug")
			if "Accepted password" in text or "Accepted publickey" in text:
				SendNow()
#end define

def LocaldbSaving():
	AddLog("Start LocaldbSaving thread.", "debug")
	while True:
		time.sleep(3) # 3 sec
		threading.Thread(target=TryLocaldbSave).start()
#end define

def TryLocaldbSave():
	try:
		LocaldbSave()
	except Exception as err:
		AddLog("TryLocaldbSave: {0}".format(err))
#end define

def LocaldbSave():
	global localdb
	myPath = GetMyPath()
	myName = GetMyName()
	fileName = myPath + myName + ".db"
	string = ItemToBase64WithCompress(localdb)
	file = open(fileName, 'w')
	file.write(string)
	file.close()
#end define

def LocaldbLoad():
	global localdb
	try:
		myPath = GetMyPath()
		myName = GetMyName()
		fileName = myPath + myName + ".db"
		if (os.path.isfile(fileName) == False):
			return
		file = open(fileName, 'r')
		original = file.read()
		localdb = Base64ToItemWithDecompress(original)
		file.close()
	except Exception as err:
		AddLog(err, "error")
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
	AddLog("Start GettingInfo thread.", "debug")
	while True:
		time.sleep(60) # 60 sec
		threading.Thread(target=TryGetInfo).start()
#end define

def TryGetInfo():
	try:
		GetInfo()
	except Exception as err:
		AddLog("TryGetInfo: {0}".format(err))
#end define

def GetInfo():
	global localdb
	timestamp = int(time.time())
	boardTemp = localbuffer["mqtt"]["boardTemp"]
	cpuTemp = localbuffer["mqtt"]["cpuTemp"]
	gprsIp = localbuffer["mqtt"]["gprsIp"]
	vIn = localbuffer["mqtt"]["vIn"]

	buffer = {"timestamp":timestamp, "boardTemp":boardTemp, "cpuTemp":cpuTemp, "gprsIp":gprsIp, "vIn":vIn}
	localdb["sendList"]["telemetryList"].append(buffer)
#end define

def SelfTesting():
	AddLog("Start SelfTesting thread.", "debug")
	while True:
		time.sleep(1)
		TrySelfTest()
#end define

def TrySelfTest():
	try:
		SelfTest()
	except Exception as err:
		AddLog("TrySelfTest: {0}".format(err), "error")
#end define

def SelfTest():
	global localdb, localbuffer
	process = psutil.Process(os.getpid())
	memoryUsing = int(process.memory_info().rss/1024/1024)
	threadCount = threading.active_count()
	localbuffer["selfTestingResult"]["memoryUsing"] = memoryUsing
	localbuffer["selfTestingResult"]["threadCount"] = threadCount
	if memoryUsing > localdb["memoryUsinglimit"]:
		localdb["memoryUsinglimit"] += 50
		AddLog("Memory using: {0}Mb".format(memoryUsing), "warning")
#end define

def PrintSelfTestingResult():
	threadCount_old = localbuffer["selfTestingResult"]["threadCountOld"]
	threadCount_new = localbuffer["selfTestingResult"]["threadCount"]
	memoryUsing = localbuffer["selfTestingResult"]["memoryUsing"]
	AddLog("{0}Self testing informatinon:{1}".format(bcolors.INFO, bcolors.ENDC))
	AddLog("Threads: {0} -> {1}".format(threadCount_new, threadCount_old))
	AddLog("Memory using: {0}Mb".format(memoryUsing))
#end define

def SelfUpdating():
	AddLog("Start SelfUpdating thread.", "debug")
	while True:
		time.sleep(600) # 600 sec
		threading.Thread(target=TrySelfUpdate).start()
#end define

def TrySelfUpdate():
	try:
		SelfUpdate()
	except Exception as err:
		AddLog("TrySelfUpdate: {0}".format(err))
#end define

def SelfUpdate():
	md5Url = base64.b64decode("aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL2lncm9tYW43ODcvdGJvdC9tYXN0ZXIvUkVBRE1FLm1k").decode()
	appUrl = base64.b64decode("aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL2lncm9tYW43ODcvdGJvdC9tYXN0ZXIvdGJvdC5weQ==").decode()
	
	myFullPath = GetMyFullPath()
	text = GetRequest(md5Url)
	md5FromServer = Pars(text, "md5: ")
	myMd5 = GetHashMd5(myFullPath)
	if (myMd5 == md5FromServer):
		return
	AddLog("SelfUpdate", "debug")
	data = urlopen(appUrl).read()
	file = open(myFullPath, 'wb')
	file.write(data)
	file.close()
	myName = GetMyName()
	os.system("systemctl restart {0}".format(myName))
#end define

def GetHashMd5(fileName):
	BLOCKSIZE = 65536
	hasher = hashlib.md5()
	with open(fileName, 'rb') as afile:
		buf = afile.read(BLOCKSIZE)
		while len(buf) > 0:
			hasher.update(buf)
			buf = afile.read(BLOCKSIZE)
	return(hasher.hexdigest())
#end define

def Pars(text, search):
	text = text[text.find(search) + len(search):]
	text = text[:text.find("\n")]
	return text
#end define


###
### Start of the program
###

if __name__ == "__main__":
	Init()
	General()
	time.sleep(1.1)
#end if
