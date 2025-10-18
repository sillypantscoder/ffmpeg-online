/**
 * @param {File[]} files
 */
async function uploadFiles(files) {
	if (files.length == 0) return;
	var project_id = await new Promise((resolve) => {
		var x = new XMLHttpRequest()
		x.open("GET", "/new_project")
		x.addEventListener("loadend", () => resolve(x.responseText))
		x.send()
	})
	// upload file
	for (var file of files) {
		await new Promise((resolve) => {
			var x = new XMLHttpRequest()
			x.open("POST", "/create_file/" + project_id + "?name=" + file.name)
			x.addEventListener("loadend", () => resolve(x.responseText))
			x.send(file)
		})
	}
	// redirect
	location.assign("/project/" + project_id)
}
