class Utils {
	/**
	 * @param {Element} alignElm
	 * @param {{ name: string, icon: string | null, onclick: (() => void) | null }[]} menu_buttons
	 */
	static createContextMenu(alignElm, menu_buttons) {
		var button_box = alignElm.getBoundingClientRect()
		// create menu element
		var menu = document.body.appendChild(document.createElement("aside"))
		menu.setAttribute("style", `box-shadow: -0.1em 0.1em 1em 0em black; background: white; display: inline-block; position: absolute; right: ${window.innerWidth - button_box.right}px; top: ${button_box.bottom}px;`)
		// buttons
		for (var btn of menu_buttons) {
			var e = menu.appendChild(document.createElement("button"))
			e.classList.add("not-btn")
			e.setAttribute("style", "padding: 0.5em; display: block; width: 100%; text-align: left;")
			e.innerHTML = (btn.icon == null ? "" : `<svg style="height: 1.5em; vertical-align: middle; margin-right: 0.5em;" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="${btn.icon}"></path></svg>`) +
				`<span style="vertical-align: middle;">${btn.name}</span>`
			if (btn.onclick != null) {
				var click = btn.onclick
				e.addEventListener("mousedown", click)
			} else {
				e.setAttribute("style", "padding: 0.714285em; font-size: 0.7em; color: gray;")
			}
		}
		// click elsewhere
		window.addEventListener("mousedown", (e) => {
			menu.remove()
			// @ts-ignore
			if (! menu.contains(e.target)) e.stopPropagation()
		}, { capture: true, once: true })
	}
	/** @param {number} bytes */
	static formatFileSize(bytes) {
		              if (bytes < 1024) return (bytes)                       .toFixed(0) +  " B";
		       if (bytes < 1024 * 1024) return (bytes / 1024)                .toFixed(0) + " KB";
		if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024))       .toFixed(1) + " MB";
		                           else return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
	}
	/**
	 * @param {number} seconds
	 */
	static formatFileDuration(seconds) {
		var minutes = Math.floor(seconds / 60); seconds -= minutes * 60;
		var hours = Math.floor(minutes / 60); minutes -= hours * 60;
		seconds = Math.round(seconds * 100) / 100
		if (hours > 0) return `${hours} hours ${minutes} minutes ${seconds} seconds`
		else return `${minutes} minutes ${seconds} seconds`
	}
}

/** @type {string[]} */
var selectedFiles = []

function updateProjectInfo() {
	// Erase previous data
	var fileContainer = document.querySelector("#files")
	if (fileContainer == null) throw new Error("file container must exist");
	[...fileContainer.children].forEach((v) => v.remove());
	[...document.querySelectorAll("body :not(body > h3:first-child, #files, script)")].forEach((v) => v.remove());
	// Get project data
	/** @type {{ files: { name: string, type: { audio: boolean, video: boolean, subtitles: boolean }, size: number, duration: number }[], conversions: { name: string }[] }} */
	var project_data = JSON.parse(document.querySelector("script[type='text/plain']")?.innerHTML ?? "")
	// Create file elements
	for (let file of project_data.files) {
		let row = fileContainer.appendChild(document.createElement("div"))
		row.classList.add("file-row")
		// Icon
		row.appendChild(document.createElement("div")).innerHTML = `<img src="/icons/${file.type.audio ? 'audio_file' : 'file_blank'}.svg"><img src="/icons/${file.type.video ? 'video_file' : 'file_blank'}.svg"><img src="/icons/${file.type.subtitles ? 'subtitles_file' : 'file_blank'}.svg">`
		// Name
		row.appendChild(document.createElement("div")).innerHTML = `<span>${file.name}<div style="font-size: 0.75em; opacity: 0.75;">${Utils.formatFileSize(file.size)} - ${Utils.formatFileDuration(file.duration)}</div></span>`
		// Convert Button
		if (selectedFiles.includes(file.name)) {
			row.appendChild(document.createElement("div")).innerHTML = `<button class="special-btn btn-cancel">Cancel</button>`
			row.children[2].children[0].addEventListener("click", () => {
				selectedFiles.splice(selectedFiles.indexOf(file.name), 1)
				updateProjectInfo()
			})
		} else {
			row.appendChild(document.createElement("div")).innerHTML = `<button class="special-btn">Convert...</button>`
			row.children[2].children[0].addEventListener("click", () => {
				selectedFiles.push(file.name)
				updateProjectInfo()
			})
		}
		// Menu Button
		row.appendChild(document.createElement("div")).innerHTML = `<button><img src="/icons/menu.svg"></button>`
		row.children[3].children[0].addEventListener("click", () => Utils.createContextMenu(row.children[3].children[0], [
			{ name: "Download", icon: "M 5 6.67 L 2.92 4.58 L 3.5 3.98 L 4.58 5.06 V 1.67 H 5.42 V 5.06 L 6.5 3.98 L 7.08 4.58 L 5 6.67 Z M 2.5 8.33 Q 2.16 8.33 1.91 8.09 T 1.67 7.5 V 6.25 H 2.5 V 7.5 H 7.5 V 6.25 H 8.33 V 7.5 Q 8.33 7.84 8.09 8.09 T 7.5 8.33 H 2.5 Z",
				onclick: downloadFile.bind(null, file.name) },
			{ name: "Rename", icon: "M 1 7 L 1 9 L 3 9 L 9 3 L 7 1 Z M 2 7 L 7 2 L 8 3 L 3 8 Z", onclick: renameFile.bind(null, file.name) },
			{ name: "Delete", icon: "M 6.5 9 A 1 1 0 0 0 7.5 8 L 7.5 4 A 1 1 0 0 0 6.5 3 L 3.5 3 A 1 1 0 0 0 2.5 4 L 2.5 8 A 1 1 0 0 0 3.5 9 Z M 2.5 1.9 A 0.5 0.5 0 0 0 2.5 2.9 L 7.5 2.9 A 0.5 0.5 0 0 0 7.5 1.9 Z M 4 1.9 A 1 1 0 0 1 6 1.9 L 5.5 1.9 A 0.5 0.5 0 0 0 4.5 1.9 Z M 3.4 4 A 0.3 0.3 0 0 1 4 4 L 4 8 A 0.3 0.3 0 0 1 3.4 8 Z M 4.7 4 A 0.3 0.3 0 0 1 5.3 4 L 5.3 8 A 0.3 0.3 0 0 1 4.7 8 Z M 6 4 A 0.3 0.3 0 0 1 6.6 4 L 6.6 8 A 0.3 0.3 0 0 1 6 8 Z",
				onclick: deleteFile.bind(null, file.name) }
		]))
	}
	// Create conversion elements
	if (project_data.conversions.length > 0) {
		// Create conversion list
		let c_list = document.body.appendChild(document.createElement("ul"))
		// Create heading (inserted before c_list)
		{
			let table2heading = document.createElement("h3")
			table2heading.innerText = "In-progress conversions"
			c_list.insertAdjacentElement("beforebegin", table2heading)
		}
		// Elements
		for (let conversion of project_data.conversions) {
			let row = c_list.appendChild(document.createElement("li"))
			row.innerHTML = `${conversion.name}`
		}
	}
	// Create refresh button
	{
		let refreshbtn = document.body.appendChild(document.createElement("button"))
		refreshbtn.innerText = "Refresh"
		refreshbtn.addEventListener("click", () => {
			refreshbtn.disabled = true
			/** @type {Promise<string>} */
			var promise = new Promise((resolve) => {
				var x = new XMLHttpRequest()
				x.open("GET", "/project/" + location.pathname.split("/").at(-1))
				x.addEventListener("loadend", () => resolve(x.responseText))
				x.send()
			})
			promise.then((html) => {
				var project_data = html.substring(html.indexOf("/plain\">") + 8, html.indexOf("</script>"))
				// Update element with new project data
				var dataContainer = document.querySelector("script[type='text/plain']")
				if (dataContainer == null) throw new Error("project data container must exist")
				dataContainer.textContent = project_data
				// Refresh display
				selectedFiles = []
				updateProjectInfo()
			})
		})
	}
	// Selected files
	if (selectedFiles.length > 0) {
		let s_list = document.body.appendChild(document.createElement("ol"))
		// Create heading (inserted before s_list)
		{
			let table3heading = document.createElement("h3")
			table3heading.innerText = "Selected files"
			s_list.insertAdjacentElement("beforebegin", table3heading)
		}
		// Elements
		for (var filename of selectedFiles) {
			let row = s_list.appendChild(document.createElement("li"))
			row.innerHTML = `${filename}`
		}
		// Conversions
		var conversion_list = document.body.appendChild(document.createElement("div"))
		var conversion_info = document.body.appendChild(document.createElement("div"))
		new Promise((resolve) => {
			var x = new XMLHttpRequest()
			x.open("GET", "/conversions/" + location.pathname.split("/").at(-1) + "/" + selectedFiles.join("/"))
			x.addEventListener("loadend", () => resolve(x.responseText))
			x.send()
		}).then((_data) => {
			/** @type {{ name: string, arguments: string[] }[]} */
			var conversions = JSON.parse(_data)
			for (var i = 0; i < conversions.length; i++) {
				// Create button
				let button = conversion_list.appendChild(document.createElement("button"))
				button.textContent = conversions[i].name
				button.dataset.cvname = conversions[i].name
				button.classList.add("convert-button")
				button.addEventListener("click", ConversionSelection.viewConversion.bind(null, i, conversions[i], conversion_info))
			}
		})
	}
}
updateProjectInfo()

/**
 * @param {File[]} files
 */
async function uploadFiles(files) {
	if (files.length == 0) return;
	// upload file
	for (var file of files) {
		await new Promise((resolve) => {
			var x = new XMLHttpRequest()
			x.open("POST", "/create_file/" + location.pathname.split("/").at(-1) + "?name=" + file.name)
			x.addEventListener("loadend", () => resolve(x.responseText))
			x.send(file)
		})
	}
	// refresh
	location.reload()
}
/**
 * @param {string} filename
 */
function convertFile(filename) {
	location.replace("/convert/" + location.pathname.split("/").at(-1) + "/" + filename)
}

/**
 * @param {string} filename
 */
function downloadFile(filename) {
	var a = document.createElement("a")
	a.href = "/file/" + location.pathname.split("/").at(-1) + "/" + filename
	a.download = filename
	a.click()
}
/**
 * @param {string} filename
 */
async function renameFile(filename) {
	var newName = prompt("Enter the new filename:", filename.split(".").slice(0, -1).join("."))
	if (newName == null) return;
	// send rename
	await new Promise((resolve) => {
		var x = new XMLHttpRequest()
		x.open("POST", "/rename_file/" + location.pathname.split("/").at(-1) + "?name=" + filename + "&newName=" + newName)
		x.addEventListener("loadend", () => resolve(x.responseText))
		x.send()
	})
	// refresh
	location.reload()
}
/**
 * @param {string} filename
 */
async function deleteFile(filename) {
	var confirmation = confirm("Are you SURE you want to delete this file?\n" + filename)
	if (confirmation == false || confirmation == undefined) return;
	// send rename
	await new Promise((resolve) => {
		var x = new XMLHttpRequest()
		x.open("POST", "/delete_file/" + location.pathname.split("/").at(-1) + "?name=" + filename)
		x.addEventListener("loadend", () => resolve(x.responseText))
		x.send()
	})
	// refresh
	location.reload()
}

class ConversionSelection {
	/**
	 * @param {string} label
	 * @param {Element} container
	 */
	static create_duration_picker(label, container) {
		var e = container.appendChild(document.createElement("div"))
		e.innerHTML = `${label}: <input type="number" min="0" max="24" value="0">H <input type="number" min="0" max="60" value="0">M <input type="number" min="0" max="60" value="0">S`
		return () => [...e.querySelectorAll("input")].map((v) => v.value).join(":")
	}
	/**
	 * @param {string} label
	 * @param {Element} container
	 */
	static create_checkbox_input(label, container) {
		var e = container.appendChild(document.createElement("div"))
		e.innerHTML = `<input type="checkbox"> ${label}`
		return () => e.querySelector("input")?.checked.toString() ?? "false"
	}
	/**
	 * @param {number} i
	 * @param {{ name: string, arguments: string[] }} conversion
	 * @param {Element} info_container
	 */
	static viewConversion(i, conversion, info_container) {
		// Button styles
		[...(info_container.previousElementSibling?.querySelectorAll(".selected") ?? [])].forEach((v) => v.classList.remove("selected"))
		info_container.previousElementSibling?.querySelector(`button[data-cvname="${conversion.name}"]`)?.classList.add("selected")
		// Create info
		info_container.innerHTML = `<h4>${conversion.name}</h4>`
		// Arguments
		/** @type {(() => string)[]} */
		var argument_outputs = []
		for (var a of conversion.arguments) {
			var op = a.split(" ")[0]
			var rest = a.split(" ").slice(1).join(" ")
			if (op == "time") argument_outputs.push(ConversionSelection.create_duration_picker(rest, info_container))
			if (op == "checkbox") argument_outputs.push(ConversionSelection.create_checkbox_input(rest, info_container))
		}
		// Submit button
		let button = info_container.appendChild(document.createElement("button"))
		button.innerText = "Convert!"
		button.addEventListener("click", () => {
			var data = argument_outputs.map((v) => v()).join("\n")
			ConversionSelection.applyConversion(i, data)
		})
	}
	/**
	 * @param {number} i
	 * @param {string} extra_data
	 */
	static async applyConversion(i, extra_data) {
		// request conversion
		await new Promise((resolve) => {
			var x = new XMLHttpRequest()
			x.open("POST", `/convert/${location.pathname.split("/").at(-1)}/${selectedFiles.join("/")}?c=${i}`)
			x.addEventListener("loadend", () => resolve(x.responseText))
			x.send(extra_data)
		})
		// redirect back to project screen
		location.reload()
	}
}
