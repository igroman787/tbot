import base64
import json
import zlib

def Base64ToItemWithDecompress(item):
	data = item.encode("utf-8")
	b64 = base64.b64decode(data)
	decompress = zlib.decompress(b64)
	original = decompress.decode("utf-8")
	data = json.loads(original)
	return data
#end define

while True:
	inputText = input("enter base64: ")
	data = Base64ToItemWithDecompress(inputText)
	myJson = json.dumps(data, sort_keys=True, indent=4)
	print(myJson)
#end while