(() => {
	var table = document.querySelector("table")
	if (table == null) throw new Error("table must exist")
	/** @type {{ name: string, type: "audio" | "video" }[]} */
	var project_data = JSON.parse(document.querySelector("script[type='text/plain']")?.textContent ?? "")
	for (var file of project_data) {
		let row = table.appendChild(document.createElement("tr"))
		// Icon
		row.appendChild(document.createElement("td")).innerHTML = `[${file.type} icon]`
		// Name
		row.appendChild(document.createElement("td")).innerHTML = `${file.name}`
		// Convert Button
		row.appendChild(document.createElement("td")).innerHTML = `<button onclick='convertFile(${JSON.stringify(file.name)})'>Convert...</button>`
		// Download Button
		row.appendChild(document.createElement("td")).innerHTML = `<button onclick='downloadFile(${JSON.stringify(file.name)})'>Download</button>`
	}
})();

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
function convertFile(filename) {
	location.replace("/convert/" + location.pathname.split("/").at(-1) + "/" + filename)
}
