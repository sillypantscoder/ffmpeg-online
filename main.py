from server_lib import SafeDict, read_file, log, HTTPResponse, HTTPServer
import os
import re
import random
import typing
import json

FOLDER_PATH =            r"([a-zA-Z%0-9 _\.\+,!:;\(\)\-]+/)*"
FILE_PATH = FOLDER_PATH + r"[a-zA-Z%0-9 _\.\+,!:;\(\)\-]+\.[a-zA-Z0-9]+"

def validate_filename_strict(name: str):
	n = ""
	for char in name:
		if char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789": n += char.lower()
		elif char == " ": n += "_"
		else: continue
	return n
def validate_filename(name: str):
	n = ""
	for char in name:
		if char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _.+,!:;()-": n += char
		else: continue
	return n

def get_file_size(filename: str) -> int:
	if os.path.isdir(filename):
		return len(filename.split("/")[-1]) + sum([get_file_size(os.path.join(filename, subfile)) for subfile in os.listdir(filename)])
	return len(filename.split("/")[-1]) + os.path.getsize(filename)

def get_mime(extension: str):
	if extension == "pdf": return "application/pdf"
	if extension in ["png", "jpg", "jpeg", "heic", "webp"]: return "image/" + extension
	if extension == "svg": return "image/svg+xml"
	if extension in ["mov", "mp4", "webm"]: return "video/" + extension
	if extension in ["mp3"]: return "audio/" + extension
	return "application/octet-stream"



class File:
	def __init__(self, type: typing.Literal["audio", "video"], extension: str, contents: bytes):
		self.type = type
		self.extension = extension
		self.contents = contents

class Project:
	def __init__(self, id: str):
		self.id = id
		self.files: dict[str, File] = {}

PROJECTS: list[Project] = []

def findProject(id: str) -> Project | None:
	for p in PROJECTS:
		if p.id == id:
			return p
	return None

def matches(s: str, regex: str) -> bool:
	return re.fullmatch(regex, s) != None

class FFMpegServer(HTTPServer):
	def get(self, path: str, query: SafeDict, headers: SafeDict, cookies: SafeDict) -> HTTPResponse:
		if path == "/":
			return {
				"status": 200,
				"headers": {
					"Content-Type": "text/html"
				},
				"content": read_file("client/index.html")
			}
		elif path == "/index.js":
			return {
				"status": 200,
				"headers": {
					"Content-Type": "text/javascript"
				},
				"content": read_file("client/index.js")
			}
		elif path == "/new_project":
			project_id = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
			while len(project_id) < 3 or findProject(project_id) != None:
				project_id += random.choice("0123456789")
			project = Project(project_id)
			PROJECTS.append(project)
			return {
				"status": 200,
				"headers": {},
				"content": project_id.encode("UTF-8")
			}
		elif path.startswith("/project/"):
			project_id = path[9:]
			project = findProject(project_id)
			if project == None:
				return {
					"status": 404,
					"headers": {},
					"content": b"Project Not Found"
				}
			return {
				"status": 200,
				"headers": {
					"Content-Type": "text/html"
				},
				"content": read_file("client/project.html").replace(b"{{PROJECT_DATA}}", json.dumps([
					{ "name": x, "type": project.files[x].type }
					for x in project.files.keys()
				]).encode("UTF-8"))
			}
		elif path == "/project.js":
			return {
				"status": 200,
				"headers": {
					"Content-Type": "text/javascript"
				},
				"content": read_file("client/project.js")
			}
		elif path.startswith("/file/"):
			project_id = path.split("/")[2]
			project = findProject(project_id)
			if project == None:
				return {
					"status": 404,
					"headers": {},
					"content": b"Project Not Found"
				}
			filename = path.split("/")[3]
			if filename not in project.files.keys():
				return {
					"status": 404,
					"headers": {},
					"content": b"File Not Found"
				}
			return {
				"status": 200,
				"headers": {
					"Content-Type": get_mime(filename.split(".")[-1])
				},
				"content": project.files[filename].contents
			}
		else: # 404 page
			log("", "404 GET encountered: " + path)
			return {
				"status": 404,
				"headers": {},
				"content": b"404 Page Not Found"
			}
	def post(self, path: str, query: SafeDict, body: bytes) -> HTTPResponse:
		if path.startswith("/create_file/"):
			project_id = path[13:]
			project = findProject(project_id)
			if project == None:
				return {
					"status": 404,
					"headers": {},
					"content": b"Project Not Found"
				}
			# Find filename
			filename = ".".join(query.get("name").split(".")[:-1]).split("/")[0]
			while filename in project.files.keys():
				filename += "_"
			# File extension and type
			file_extension = query.get("name").split(".")[-1].split("/")[0]
			if file_extension in ["mp3"]:
				file_type = "audio"
			elif file_extension in ["mp4", "mov"]:
				file_type = "video"
			else:
				return {
					"status": 404,
					"headers": {},
					"content": b"Invalid File Type"
				}
			# Save
			project.files[filename + "." + file_extension] = File(file_type, file_extension, body)
			return {
				"status": 200,
				"headers": {},
				"content": b""
			}
		else:
			log("#", "404 POST encountered: " + path)
			return {
				"status": 404,
				"headers": {},
				"content": b"404 POST"
			}

if __name__ == "__main__":
	server = FFMpegServer('0.0.0.0', 10623)
	server.run()
