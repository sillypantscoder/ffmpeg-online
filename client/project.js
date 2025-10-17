(() => {
	var table = document.querySelector("table")
	if (table == null) throw new Error("table must exist")
	/** @type {{ files: { name: string, type: "audio" | "video" }[], conversions: { name: string }[] }} */
	var project_data = JSON.parse(document.querySelector("script[type='text/plain']")?.textContent ?? "")
	// Create file elements
	for (var file of project_data.files) {
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
	// Create conversion elements
	if (project_data.conversions.length > 0) {
		// Create second table
		var table2 = document.createElement("table")
		table.insertAdjacentElement("afterend", table2)
		// Create heading (inserted before table)
		{
			let table2heading = document.createElement("h3")
			table2heading.innerText = "In-progress conversions"
			table2.insertAdjacentElement("beforebegin", table2heading)
		}
		// Elements
		for (var conversion of project_data.conversions) {
			let row = table2.appendChild(document.createElement("tr"))
			// Name
			row.appendChild(document.createElement("td")).innerHTML = `${conversion.name}`
		}
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
