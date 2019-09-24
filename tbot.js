defineVirtualDevice("tbot", {
	title: "tbot control panel",
	cells:{
		sendData: {
			type: "pushbutton",
			value: "false"
		},
		time: {
			type: "value",
			value: "null"
		},
		time_GetStatus: {
			type: "value",
			value: "null"
		},
		time_SendData: {
			type: "value",
			value: "null"
		},
		ping: {
			type: "value",
			value: "null"
		},
		serverStatus: {
			type: "value",
			value: "Offline"
		}
	}
});