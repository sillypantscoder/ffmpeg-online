var conversion_data = (() => {
	var button_container = document.querySelector("#convert_buttons")
	if (button_container == null) throw new Error("button container must exist")
	/** @type {{ file: { type: "audio" | "video", name: string }, conversions: { name: string, arguments: string[] }[] }} */
	var conversion_data = JSON.parse(document.querySelector("script[type='text/plain']")?.textContent ?? "")
	// File info in header
	document.querySelector("h3 img")?.setAttribute("src", `/icons/${conversion_data.file.type}_file.svg`);
	(document.querySelector("h3 span") ?? document.createElement("span")).textContent = conversion_data.file.name
	// Create convert buttons
	for (var i = 0; i < conversion_data.conversions.length; i++) {
		let conversion = conversion_data.conversions[i]
		// Create button
		let button = button_container.appendChild(document.createElement("button"))
		button.textContent = conversion.name
		button.addEventListener("click", ((/** @type {number} */ i) => {
			viewConversion(i)
		}).bind(null, i))
	}
	return conversion_data
})();

/**
 * @param {string} label
 * @param {Element} container
 */
function create_duration_picker(label, container) {
	var e = container.appendChild(document.createElement("div"))
	e.innerHTML = `${label}: <input type="number" min="0" max="24" value="0">H <input type="number" min="0" max="60" value="0">M <input type="number" min="0" max="60" value="0">S`
	return () => [...e.querySelectorAll("input")].map((v) => v.value).join(":")
}
/**
 * @param {string} label
 * @param {Element} container
 */
function create_checkbox_input(label, container) {
	var e = container.appendChild(document.createElement("div"))
	e.innerHTML = `<input type="checkbox"> ${label}`
	return () => e.querySelector("input")?.checked.toString() ?? "false"
}
/**
 * @param {number} i
 */
function viewConversion(i) {
	var conversion = conversion_data.conversions[i];
	// Button styles
	[...document.querySelectorAll("#convert_buttons .selected")].forEach((v) => v.classList.remove("selected"))
	document.querySelector("#convert_buttons")?.children[i].classList.add("selected")
	// Get info element
	var info_container = document.querySelector("#c_info")
	if (info_container == null) throw new Error("conversion info container must exist")
	// Create info
	info_container.innerHTML = `<h4>${conversion.name}</h4>`
	// Arguments
	/** @type {(() => string)[]} */
	var argument_outputs = []
	for (var a of conversion.arguments) {
		var op = a.split(" ")[0]
		var rest = a.split(" ").slice(1).join(" ")
		if (op == "time") argument_outputs.push(create_duration_picker(rest, info_container))
		if (op == "checkbox") argument_outputs.push(create_checkbox_input(rest, info_container))
	}
	// Submit button
	let button = info_container.appendChild(document.createElement("button"))
	button.innerText = "Convert!"
	button.addEventListener("click", () => {
		var data = argument_outputs.map((v) => v()).join("\n")
		applyConversion(i, data)
	})
}
/**
 * @param {number} i
 * @param {string} extra_data
 */
async function applyConversion(i, extra_data) {
	// request conversion
	await new Promise((resolve) => {
		var x = new XMLHttpRequest()
		x.open("POST", "/convert/" + location.pathname.split("/").at(-2) + "/" + conversion_data.file.name + "/" + i)
		x.addEventListener("loadend", () => resolve(x.responseText))
		x.send(extra_data)
	})
	// redirect back to project screen
	location.replace("/project/" + location.pathname.split("/").at(-2))
}

function cancelConversion() {
	// redirect back to project screen
	location.replace("/project/" + location.pathname.split("/").at(-2))
}
