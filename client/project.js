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
		row.appendChild(document.createElement("div")).innerHTML = `<button>Convert...</button>`
		row.children[2].children[0].addEventListener("click", convertFile.bind(null, file.name))
		// Download Button
		row.appendChild(document.createElement("div")).innerHTML = `<button>Download</button>`
		row.children[3].children[0].addEventListener("click", downloadFile.bind(null, file.name))
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
