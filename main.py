from server_lib import SafeDict, read_file, write_file, log, HTTPResponse, HTTPServer
import os
import re
import random
import typing
import json
import subprocess
import threading
from urllib.parse import unquote

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

def runFFMpegCommandWithProgress(command: list[str], expected_duration: str | int, progress_callback: typing.Callable[[ float, float ], None]):
	# First find the file size
	if isinstance(expected_duration, str):
		duration_seconds = float(subprocess.run([
			"ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", expected_duration
		], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode("UTF-8").strip())
	else:
		duration_seconds = expected_duration
	# Start the command
	proc = subprocess.Popen(["ffmpeg", "-progress", "-", "-nostats", *command], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
	if proc.stdout == None: raise TypeError
	while True:
		line = proc.stdout.readline()
		if line.startswith(b"out_time="):
			# Calculate given time
			timeH = float(line.split(b"=")[1].split(b":")[0].decode("UTF-8"))
			timeM = float(line.split(b"=")[1].split(b":")[1].decode("UTF-8"))
			timeS = float(line.split(b"=")[1].split(b":")[2].decode("UTF-8"))
			timeTotal = (60 * ((60 * timeH) + timeM)) + timeS
			progress_callback(timeTotal, duration_seconds)
		if line == b"progress=end\n": break # Done!



class File:
	def __init__(self, type: typing.Literal["audio", "video"], extension: str, contents: bytes):
		self.type: typing.Literal["audio", "video"] = type
		self.extension = extension
		self.contents = contents
	def get_mime(self):
		subtype = self.extension
		if self.extension == "mov": subtype = "quicktime"
		return self.type + "/" + subtype
	@staticmethod
	def guess_type(data: bytes) -> typing.Literal["audio", "video"]:
		# Use ffprobe
		write_file("checkfile.dat", data)
		raw_info = subprocess.run(["ffprobe", "checkfile.dat"], stderr=subprocess.PIPE).stderr
		# Analyze returned info
		streams_raw = [b": ".join(line.split(b": ")[1:]) for line in raw_info.split(b"\n") if b"Stream" in line]
		has_audio = any([(b"Audio" in line) for line in streams_raw])
		has_video = any([(b"Video" in line and b"kb/s" in line) for line in streams_raw]) # we don't want to accidentally interpret images as video streams
		# Check for video
		if not (has_audio or has_video): raise ValueError("This file is not a video/audio file")
		if has_video: return "video"
		else: return "audio"

class Conversion:
	def get_name(self) -> str:
		...
	def get_arguments(self) -> list[str]:
		return []
	def get_status(self) -> str:
		...
	async def convert(self, files: list[File], extra_data: str) -> dict[str, File]:
		...

class ConversionWithOwnFolder(Conversion):
	async def convert(self, files: list[File], extra_data: str) -> dict[str, File]:
		# Create Folder
		folder = "files_" + str(random.randint(1, 100000000))
		os.makedirs(folder)
		# Write Files
		input_filenames: list[str] = []
		for i in range(len(files)):
			filename = folder + "/input_" + str(i) + "." + files[i].extension
			write_file(filename, files[i].contents)
			input_filenames.append(filename)
		# Process Files
		await self.process_files(folder, input_filenames, extra_data)
		# Get Result Files
		new_files = [f"{folder}/{n}" for n in os.listdir(folder) if f"{folder}/{n}" not in input_filenames]
		result_files = await self.get_result_files(new_files)
		# Delete Folder
		for n in os.listdir(folder): os.remove(f"{folder}/{n}")
		os.removedirs(folder)
		# Finish
		return result_files
	async def process_files(self, folder: str, input_filenames: list[str], extra_data: str):
		...
	async def get_result_files(self, new_files: list[str]) -> dict[str, File]:
		"""Return a list of files to add to the project. The file extension of each filename will be removed and replaced with the file extension from the associated File object."""
		...

class FileFormatConversion(ConversionWithOwnFolder):
	def __init__(self, type: typing.Literal["audio", "video"], previous_filename: str, new_format: str):
		self.type: typing.Literal["audio", "video"] = type
		self.new_format = new_format
		self.filename = previous_filename
		self.progress = "0"
	def get_name(self):
		return "Convert to " + self.new_format.upper()
	def get_status(self):
		return "Converting " + self.filename + " to " + self.new_format.upper() + " (" + self.progress + "% done)"
	async def process_files(self, folder: str, input_filenames: list[str], extra_data: str):
		runFFMpegCommandWithProgress([
			"-i", input_filenames[0], folder + "/output." + self.new_format
		], input_filenames[0], self.setProgress)
	def setProgress(self, done: float, total: float):
		self.progress = str(round(1000 * done / total) / 10)
	async def get_result_files(self, new_files: list[str]) -> dict[str, File]:
		return {
			self.filename: File(self.type, self.new_format, read_file(new_files[0]))
		}

class CutConversion(ConversionWithOwnFolder):
	def __init__(self, type: typing.Literal["audio", "video"], filename: str):
		self.type: typing.Literal["audio", "video"] = type
		self.file_name = ".".join(filename.split(".")[:-1])
		self.file_extension = filename.split(".")[-1]
		self.progress = "0"
	def get_name(self):
		return "Cut"
	def get_arguments(self) -> list[str]:
		return ["time Start time", "time Duration", "checkbox Absolute end time instead of duration"]
	def get_status(self):
		return "Cutting " + self.file_name + "." + self.file_extension + " (" + self.progress + "% done)"
	async def processStartTimeEndTimeDuration(self, extra_data: str):
		# Process start time
		start_time_raw = extra_data.split("\n")[0]
		start_time_int = [int(start_time_raw.split(":")[0]), int(start_time_raw.split(":")[1]), int(start_time_raw.split(":")[2])]
		start_time_str = f"{str(start_time_int[0]).rjust(2, '0')}:{str(start_time_int[1]).rjust(2, '0')}:{str(start_time_int[2]).rjust(2, '0')}"
		# Process end time
		end_time_raw = extra_data.split("\n")[1]
		end_time_int = [int(end_time_raw.split(":")[0]), int(end_time_raw.split(":")[1]), int(end_time_raw.split(":")[2])]
		is_duration = extra_data.split("\n")[2] == "false"
		if is_duration:
			# Update seconds
			end_time_int[2] += start_time_int[2]
			while end_time_int[2] >= 60: end_time_int[2] -= 60; end_time_int[1] += 1
			# Update minutes
			end_time_int[1] += start_time_int[1]
			while end_time_int[1] >= 60: end_time_int[1] -= 60; end_time_int[0] += 1
			# Update hours
			end_time_int[0] += start_time_int[0]
		end_time_str = f"{str(end_time_int[0]).rjust(2, '0')}:{str(end_time_int[1]).rjust(2, '0')}:{str(end_time_int[2]).rjust(2, '0')}"
		# Find duration (for progress indicator)
		start_time_sec = (60 * 60 * start_time_int[0]) + (60 * start_time_int[1]) + start_time_int[2]
		end_time_sec = (60 * 60 * end_time_int[0]) + (60 * end_time_int[1]) + end_time_int[2]
		duration = end_time_sec - start_time_sec
		# Return info
		return (start_time_str, end_time_str, duration)
	async def process_files(self, folder: str, input_filenames: list[str], extra_data: str):
		start_time_str, end_time_str, duration = await self.processStartTimeEndTimeDuration(extra_data)
		# Run command
		runFFMpegCommandWithProgress([
			"-i", input_filenames[0], "-ss", start_time_str, "-to", end_time_str, folder + "/output." + self.file_extension
		], duration, self.setProgress)
	def setProgress(self, done: float, total: float):
		self.progress = str(round(1000 * done / total) / 10)
	async def get_result_files(self, new_files: list[str]) -> dict[str, File]:
		return {
			self.file_name + "_cut." + self.file_extension: File(self.type, self.file_extension, read_file(new_files[0]))
		}

def get_available_conversions(f: File, filename: str):
	"""ADD NEW FILE TYPES HERE"""
	conversions: list[Conversion] = []
	# Convert Audio Formats
	if f.type == "audio":
		if f.extension != "mp3": conversions.append(FileFormatConversion("audio", filename, "mp3"))
		if f.extension != "wav": conversions.append(FileFormatConversion("audio", filename, "wav"))
		if f.extension != "webm": conversions.append(FileFormatConversion("audio", filename, "webm"))
		if f.extension != "ogg": conversions.append(FileFormatConversion("audio", filename, "ogg"))
	# Convert Video Formats
	if f.type == "video":
		if f.extension != "mp4": conversions.append(FileFormatConversion("video", filename, "mp4"))
		if f.extension != "mov": conversions.append(FileFormatConversion("video", filename, "mov"))
		if f.extension != "webm": conversions.append(FileFormatConversion("video", filename, "webm"))
	# Cut Media
	if f.extension == "mp3" or f.extension == "mp4": conversions.append(CutConversion(f.type, filename))
	# Finish
	return conversions

InProgressConversion: typing.TypeAlias = tuple[Conversion, typing.Coroutine[typing.Any, typing.Any, None]]
class Project:
	def __init__(self, id: str):
		self.id = id
		self.files: dict[str, File] = {}
		self.processes: list[InProgressConversion] = []
	def apply_conversion(self, f: File, conversion: Conversion, extra_data: str):
		"""Apply the conversion, and save the files when it is done."""
		async def run_conversion():
			# Get and save result files
			result_files = await conversion.convert([f], extra_data)
			for filename in result_files:
				# Find final filename for this file
				save_filename = ".".join(filename.split(".")[:-1])
				while save_filename + "." + result_files[filename].extension in self.files.keys():
					save_filename += "_"
				# Save this file!
				self.files[save_filename + "." + result_files[filename].extension] = result_files[filename]
			# Remove this conversion from process list
			for proc in self.processes:
				if proc[0] == conversion:
					self.processes.remove(proc)
					break
		def run_conversion_sync():
			coroutine = run_conversion()
			self.processes.append((conversion, coroutine))
			# Start the conversion!
			try:
				coroutine.send(None)
			except StopIteration:
				pass
		threading.Thread(target=run_conversion_sync, name=None, args=()).start()

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
				"content": read_file("client/project.html").replace(b"{{PROJECT_DATA}}", json.dumps({
					"files": [
						{ "name": x, "type": project.files[x].type }
						for x in project.files.keys()
					],
					"conversions": [
						{ "name": x[0].get_status() }
						for x in project.processes
					]
				}).encode("UTF-8"))
			}
		elif path == "/project.js":
			return {
				"status": 200,
				"headers": {
					"Content-Type": "text/javascript"
				},
				"content": read_file("client/project.js")
			}
		elif matches(path, r"/icons/[a-zA-Z_]+\.svg"):
			return {
				"status": 200,
				"headers": {
					"Content-Type": "image/svg+xml"
				},
				"content": read_file("client" + path)
			}
		elif path.startswith("/file/"):
			project_id = unquote(path).split("/")[2]
			project = findProject(project_id)
			if project == None:
				return {
					"status": 404,
					"headers": {},
					"content": b"Project Not Found"
				}
			filename = unquote(path).split("/")[3]
			if filename not in project.files.keys():
				return {
					"status": 404,
					"headers": {},
					"content": b"File Not Found"
				}
			return {
				"status": 200,
				"headers": {
					"Content-Type": project.files[filename].get_mime()
				},
				"content": project.files[filename].contents
			}
		elif path.startswith("/convert/"):
			# Find file in project
			project_id = unquote(path).split("/")[2]
			project = findProject(project_id)
			if project == None:
				return {
					"status": 404,
					"headers": {},
					"content": b"Project Not Found"
				}
			filename = unquote(path).split("/")[3]
			if filename not in project.files.keys():
				return {
					"status": 404,
					"headers": {},
					"content": b"File Not Found"
				}
			# Get conversions
			conversions = get_available_conversions(project.files[filename], filename)
			return {
				"status": 200,
				"headers": {
					"Content-Type": "text/html"
				},
				"content": read_file("client/convert.html").replace(b"{{CONVERSION_DATA}}", json.dumps({
					"file": {
						"type": project.files[filename].type,
						"name": filename
					},
					"conversions": [
						{ "name": x.get_name(), "arguments": x.get_arguments() }
						for x in conversions
					]
				}).encode("UTF-8"))
			}
		elif path == "/convert.js":
			return {
				"status": 200,
				"headers": {
					"Content-Type": "text/javascript"
				},
				"content": read_file("client/convert.js")
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
			filename = filename.replace("<", "").replace(">", "").replace("/", "").replace("&", "")
			while filename in project.files.keys():
				filename += "_"
			# File extension and type
			file_extension = query.get("name").split(".")[-1].split("/")[0]
			try:
				file_type = File.guess_type(body)
			except: return {
				"status": 400,
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
		elif path.startswith("/convert/"):
			# Find file in project
			project_id = unquote(path).split("/")[2]
			project = findProject(project_id)
			if project == None:
				return {
					"status": 404,
					"headers": {},
					"content": b"Project Not Found"
				}
			filename = unquote(path).split("/")[3]
			if filename not in project.files.keys():
				return {
					"status": 404,
					"headers": {},
					"content": b"File Not Found"
				}
			# Get conversion
			conversion_index = int(path.split("/")[4])
			conversion = get_available_conversions(project.files[filename], filename)[conversion_index]
			# Apply conversion
			project.apply_conversion(project.files[filename], conversion, body.decode("UTF-8"))
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
