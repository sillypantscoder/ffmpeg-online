/**
 * @param {Element} alignElm
 * @param {{ name: string, icon: string | null, onclick: (() => void) | null }[]} menu_buttons
 */
function createContextMenu(alignElm, menu_buttons) {
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

(() => {
	var fileContainer = document.querySelector("#files")
	if (fileContainer == null) throw new Error("file container must exist")
	/** @type {{ files: { name: string, type: "audio" | "video" }[], conversions: { name: string }[] }} */
	var project_data = JSON.parse(document.querySelector("script[type='text/plain']")?.innerHTML ?? "")
	// Create file elements
	for (var file of project_data.files) {
		let row = fileContainer.appendChild(document.createElement("div"))
		row.classList.add("file-row")
		// Icon
		row.appendChild(document.createElement("div")).innerHTML = `<img src="/icons/${file.type}_file.svg">`
		// Name
		row.appendChild(document.createElement("div")).innerHTML = `<span>${file.name}</span>`
		// Convert Button
		row.appendChild(document.createElement("div")).innerHTML = `<button class="special-btn">Convert...</button>`
		row.children[2].children[0].addEventListener("click", convertFile.bind(null, file.name))
		// Menu Button
		row.appendChild(document.createElement("div")).innerHTML = `<button><img src="/icons/menu.svg"></button>`
		row.children[3].children[0].addEventListener("click", () => createContextMenu(row.children[3].children[0], [
			{ name: "Download", icon: "M 48 64 L 28 44 L 33.6 38.2 L 44 48.6 V 16 H 52 V 48.6 L 62.4 38.2 L 68 44 L 48 64 Z M 24 80 Q 20.7 80 18.35 77.65 T 16 72 V 60 H 24 V 72 H 72 V 60 H 80 V 72 Q 80 75.3 77.65 77.65 T 72 80 H 24 Z",
				onclick: downloadFile.bind(null, file.name) },
			{ name: "Rename", icon: "M 1 7 L 1 9 L 3 9 L 9 3 L 7 1 Z M 2 7 L 7 2 L 8 3 L 3 8 Z", onclick: renameFile.bind(null, file.name) },
			{ name: "Delete", icon: "M 6.5 9 A 1 1 0 0 0 7.5 8 L 7.5 4 A 1 1 0 0 0 6.5 3 L 3.5 3 A 1 1 0 0 0 2.5 4 L 2.5 8 A 1 1 0 0 0 3.5 9 Z M 2.5 1.9 A 0.5 0.5 0 0 0 2.5 2.9 L 7.5 2.9 A 0.5 0.5 0 0 0 7.5 1.9 Z M 4 1.9 A 1 1 0 0 1 6 1.9 L 5.5 1.9 A 0.5 0.5 0 0 0 4.5 1.9 Z M 3.4 4 A 0.3 0.3 0 0 1 4 4 L 4 8 A 0.3 0.3 0 0 1 3.4 8 Z M 4.7 4 A 0.3 0.3 0 0 1 5.3 4 L 5.3 8 A 0.3 0.3 0 0 1 4.7 8 Z M 6 4 A 0.3 0.3 0 0 1 6.6 4 L 6.6 8 A 0.3 0.3 0 0 1 6 8 Z",
				onclick: deleteFile.bind(null, file.name) }
		]))
	}
	// Create conversion elements
	if (project_data.conversions.length > 0) {
		// Create conversion list
		var c_list = document.body.appendChild(document.createElement("ol"))
		// Create heading (inserted before c_list)
		{
			let table2heading = document.createElement("h3")
			table2heading.innerText = "In-progress conversions"
			c_list.insertAdjacentElement("beforebegin", table2heading)
		}
		// Elements
		for (var conversion of project_data.conversions) {
			let row = c_list.appendChild(document.createElement("li"))
			row.innerHTML = `${conversion.name}`
		}
	}
})();

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
