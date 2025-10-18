var file_data = (() => {
	var button_container = document.querySelector("#convert_buttons")
	if (button_container == null) throw new Error("button container must exist")
	/** @type {{ file: { type: "audio" | "video", name: string }, conversions: { name: string }[] }} */
	var conversion_data = JSON.parse(document.querySelector("script[type='text/plain']")?.textContent ?? "")
	// Create convert buttons
	for (var i = 0; i < conversion_data.conversions.length; i++) {
		let conversion = conversion_data.conversions[i]
		// Create button
		let button = button_container.appendChild(document.createElement("button"))
		button.textContent = conversion.name
		button.addEventListener("click", ((/** @type {number} */ i) => {
			applyConversion(i)
		}).bind(null, i))
	}
	return conversion_data.file
})();

/**
 * @param {number} i
 */
async function applyConversion(i) {
	// request conversion
	await new Promise((resolve) => {
		var x = new XMLHttpRequest()
		x.open("POST", "/convert/" + location.pathname.split("/").at(-2) + "/" + file_data.name + "/" + i)
		x.addEventListener("loadend", () => resolve(x.responseText))
		x.send()
	})
	// redirect back to project screen
	location.replace("/project/" + location.pathname.split("/").at(-2))
}

function cancelConversion() {
	// redirect back to project screen
	location.replace("/project/" + location.pathname.split("/").at(-2))
}
