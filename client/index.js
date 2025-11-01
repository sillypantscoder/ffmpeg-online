const CHUNK_SIZE = 10000000;
/**
 * @param {string} data
 */
function updateStatus(data) {
	var e = document.querySelector("#status")
	if (e == null) return console.warn("status element missing")
	e.textContent = data + "\n" + e.textContent
}
/**
 * @param {File[]} files
 * @param {string | null} project_id
 */
async function uploadFiles(files, project_id) {
	if (files.length == 0) return;
	if (project_id == null) project_id = await new Promise((resolve) => {
		var x = new XMLHttpRequest()
		x.open("GET", "/new_project")
		x.addEventListener("loadend", () => resolve(x.responseText))
		x.send()
	})
	// upload file
	for (var file of files) {
		updateStatus("Uploading " + file.name)
		await new Promise((resolve) => {
			var x = new XMLHttpRequest()
			x.open("POST", "/start_upload/" + project_id + "?name=" + file.name)
			x.addEventListener("loadend", () => resolve(x.responseText))
			x.send()
		})
		for (var offset = 0; offset < file.size; offset += CHUNK_SIZE) {
			await new Promise((resolve) => {
				var x = new XMLHttpRequest()
				x.open("POST", "/upload/" + project_id + "?name=" + file.name)
				x.addEventListener("loadend", () => resolve(x.responseText))
				x.send(file.slice(offset, offset + CHUNK_SIZE))
			})
			updateStatus(`- ${Math.round(1000 * Math.min(offset + CHUNK_SIZE, file.size) / file.size) / 10}% done`)
		}
		await new Promise((resolve) => {
			var x = new XMLHttpRequest()
			x.open("POST", "/finish_upload/" + project_id + "?name=" + file.name)
			x.addEventListener("loadend", () => resolve(x.responseText))
			x.send()
		})
	}
	// redirect
	location.assign("/project/" + project_id)
}
