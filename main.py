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

def removeFE(name: str):
	return ".".join(name.split(".")[:-1])

def get_file_size(filename: str) -> int:
	if os.path.isdir(filename):
		return len(filename.split("/")[-1]) + sum([get_file_size(os.path.join(filename, subfile)) for subfile in os.listdir(filename)])
	return len(filename.split("/")[-1]) + os.path.getsize(filename)

def runFFMpegCommandWithProgress(command: list[str], expected_duration: str | float, progress_callback: typing.Callable[[ float, float ], None]):
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
# TODO: Add this but for whisper. We can split each line on " --> <time>]" and end when the <time> becomes very close to the media duration.



class FileType(typing.TypedDict):
	audio: bool
	video: bool
	subtitles: bool

class File:
	def __init__(self, type: FileType, extension: str, duration: float, contents: bytes):
		self.type: FileType = type
		self.extension = extension
		self.duration = duration
		self.contents = contents
	def get_mime(self):
		type = "video" if self.type["video"] else ("audio" if self.type["audio"] else "application")
		if type == "application": return "application/x-subrip"
		subtype = self.extension
		if self.extension == "mov": subtype = "quicktime"
		return type + "/" + subtype
	@staticmethod
	def guess_type(data: bytes) -> FileType:
		# Use ffprobe
		write_file("checkfile.dat", data)
		raw_info = subprocess.run(["ffprobe", "checkfile.dat"], stderr=subprocess.PIPE).stderr
		# Analyze returned info
		streams_raw = [b": ".join(line.split(b": ")[1:]) for line in raw_info.split(b"\n") if b"Stream" in line]
		has_audio = any([(b"Audio" in line) for line in streams_raw])
		has_video = any([(b"Video" in line and b"kb/s" in line) for line in streams_raw]) # we don't want to accidentally interpret images as video streams
		has_subtitles = any([(b"Subtitle" in line) for line in streams_raw])
		# Check for video
		if not (has_audio or has_video or has_subtitles): raise ValueError("This file is not a video/audio file")
		return { "audio": has_audio, "video": has_video, "subtitles": has_subtitles }
	@staticmethod
	def get_media_duration(data: bytes):
		write_file("checkfile.dat", data)
		return float(subprocess.run([
			"ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", "checkfile.dat"
		], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode("UTF-8").strip())
	@staticmethod
	def get_subtitles_duration(data: bytes):
		lines = data.strip().split(b"\n")
		last_timestamp = lines[-2].split(b" --> ")[-1].decode("UTF-8")
		return \
			(int(last_timestamp.split(":")[0]) * 60 * 60) + \
			(int(last_timestamp.split(":")[1]) * 60) + \
			float(last_timestamp.split(":")[2].replace(",", "."))
	@staticmethod
	def get_duration(data: bytes, file_type: FileType):
		if file_type["audio"] or file_type["video"]: return File.get_media_duration(data)
		else: return File.get_subtitles_duration(data)

NamedFile: typing.TypeAlias = tuple[str, File]
"""Indicates a file with a name. The name should not include a file extension."""

class Conversion:
	def __init__(self, files: list[NamedFile]):
		self.files = files
	def get_name(self) -> str:
		...
	def get_arguments(self) -> list[str]:
		return []
	def get_status(self) -> str:
		...
	async def convert(self, extra_data: str) -> list[NamedFile]:
		...

class ConversionWithOwnFolder(Conversion):
	async def convert(self, extra_data: str) -> list[NamedFile]:
		# Create Folder
		folder = "files_" + str(random.randint(1, 100000000))
		os.makedirs(folder)
		# Write Files
		input_filenames: list[str] = []
		for i in range(len(self.files)):
			filename = folder + "/input_" + str(i) + "." + self.files[i][1].extension
			write_file(filename, self.files[i][1].contents)
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
	async def get_result_files(self, new_files: list[str]) -> list[NamedFile]:
		"""Return a list of files to add to the project. The file extension of each filename will be removed and replaced with the file extension from the associated File object."""
		...

class FileFormatConversion(ConversionWithOwnFolder):
	def __init__(self, file: NamedFile, new_format: str):
		super().__init__([file])
		self.new_format = new_format
		self.progress = "0"
	def get_name(self):
		return "Convert to " + self.new_format.upper()
	def get_status(self):
		return "Converting " + self.files[0][0] + "." + self.files[0][1].extension + " to " + self.new_format.upper() + " (" + self.progress + "% done)"
	async def process_files(self, folder: str, input_filenames: list[str], extra_data: str):
		runFFMpegCommandWithProgress([
			"-i", input_filenames[0], folder + "/output." + self.new_format
		], input_filenames[0], self.setProgress)
	def setProgress(self, done: float, total: float):
		self.progress = str(round(1000 * done / total) / 10)
	async def get_result_files(self, new_files: list[str]) -> list[NamedFile]:
		file_contents = read_file(new_files[0])
		return [
			(self.files[0][0], File(File.guess_type(file_contents), self.new_format, File.get_media_duration(file_contents), file_contents))
		]

class CutConversion(ConversionWithOwnFolder):
	def __init__(self, file: NamedFile):
		super().__init__([file])
		self.progress = "0"
	def get_name(self):
		return "Cut"
	def get_arguments(self) -> list[str]:
		return ["time Start time", "time Duration", "checkbox Absolute end time instead of duration"]
	def get_status(self):
		return "Cutting " + self.files[0][0] + "." + self.files[0][1].extension + " (" + self.progress + "% done)"
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
			"-i", input_filenames[0], "-ss", start_time_str, "-to", end_time_str, folder + "/output." + self.files[0][1].extension
		], duration, self.setProgress)
	def setProgress(self, done: float, total: float):
		self.progress = str(round(1000 * done / total) / 10)
	async def get_result_files(self, new_files: list[str]) -> list[NamedFile]:
		return [
			(self.files[0][0] + "_cut",
				File(self.files[0][1].type, self.files[0][1].extension, File.get_duration(read_file(new_files[0]), self.files[0][1].type), read_file(new_files[0])
		 	))
		]

class AudioTranscriptionConversion(ConversionWithOwnFolder):
	def __init__(self, file: NamedFile):
		super().__init__([file])
	def get_name(self):
		return "Transcribe"
	def get_status(self):
		return "Transcribing " + self.files[0][0] + "." + self.files[0][1].extension
	async def process_files(self, folder: str, input_filenames: list[str], extra_data: str):
		subprocess.run([
			"whisper", "--model", "turbo", "--language", "English", "--threads", "2", "--output_format", "srt", input_filenames[0].split("/")[-1]
		], cwd=folder)
	async def get_result_files(self, new_files: list[str]) -> list[NamedFile]:
		return [
			(self.files[0][0] + "_generated", File(
				{ "audio": False, "video": False, "subtitles": True }, "srt", File.get_subtitles_duration(read_file(new_files[0])), read_file(new_files[0])
			))
		]

def get_available_conversions(files: list[NamedFile]):
	conversions: list[Conversion] = []
	if len(files) == 0: return conversions
	elif len(files) == 1:
		named_file = files[0]
		ftype = named_file[1].type
		ext = named_file[1].extension
		if ftype["video"]:
			# Convert Video Formats
			if ext != "mp4": conversions.append(FileFormatConversion(named_file, "mp4"))
			if ext != "mov": conversions.append(FileFormatConversion(named_file, "mov"))
			if ext != "webm": conversions.append(FileFormatConversion(named_file, "webm"))
			# Extract Audio From Video
			conversions.append(FileFormatConversion(named_file, "mp3"))
		if ftype["audio"]:
			# Convert Audio Formats
			if ext != "mp3": conversions.append(FileFormatConversion(named_file, "mp3"))
			if ext != "wav": conversions.append(FileFormatConversion(named_file, "wav"))
			if ext != "webm": conversions.append(FileFormatConversion(named_file, "webm"))
			if ext != "ogg": conversions.append(FileFormatConversion(named_file, "ogg"))
		if ftype["subtitles"]:
			# Subtitles
			conversions.append(CutConversion(named_file))
		# Cut Media
		if ext == "mp3" or ext == "mp4": conversions.append(CutConversion(named_file))
		# Transcription
		if ftype["audio"] or ftype["video"]: conversions.append(AudioTranscriptionConversion(named_file))
	# Finish
	return conversions

class FileCollection:
	def __init__(self):
		# Files are stored with a file extension here.
		self.files: dict[str, File] = {}
	def add_file(self, filename_without_extension: str, file: File):
		self.files[filename_without_extension + "." + file.extension] = file
	def __getitem__(self, filename: str):
		return self.files[filename]
	def __delitem__(self, filename: str):
		del self.files[filename]
	def __contains__(self, v: str):
		return v in self.files.keys()
	def __iter__(self) -> typing.Iterator[NamedFile]:
		return [
			(removeFE(x), self.files[x])
			for x in self.files.keys()
		].__iter__()

InProgressConversion: typing.TypeAlias = tuple[Conversion, typing.Coroutine[typing.Any, typing.Any, None]]
class Project:
	def __init__(self, id: str):
		self.id = id
		self.files: FileCollection = FileCollection()
		self.processes: list[InProgressConversion] = []
	def apply_conversion(self, conversion: Conversion, extra_data: str):
		"""Apply the conversion, and save the files when it is done."""
		async def run_conversion():
			# Get and save result files
			result_files = await conversion.convert(extra_data)
			for named_file in result_files:
				# Find final filename for this file
				save_filename = named_file[0]
				while save_filename + "." + named_file[1].extension in self.files:
					save_filename += "_"
				# Save this file!
				self.files.add_file(save_filename, named_file[1])
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
						{ "name": file[0] + "." + file[1].extension, "type": file[1].type, "size": len(file[1].contents), "duration": file[1].duration }
						for file in project.files
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
			if filename not in project.files:
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
		elif path.startswith("/conversions/"):
			# Find project
			project_id = unquote(path).split("/")[2]
			project = findProject(project_id)
			if project == None:
				return {
					"status": 404,
					"headers": {},
					"content": b"Project Not Found"
				}
			# Find files
			files: list[NamedFile] = []
			for filename in unquote(path).split("/")[3:]:
				if filename not in project.files:
					return {
						"status": 404,
						"headers": {},
						"content": b"File Not Found: " + filename.encode("UTF-8")
					}
				files.append((removeFE(filename), project.files[filename]))
			# Get conversions
			conversions = get_available_conversions(files)
			return {
				"status": 200,
				"headers": {},
				"content": json.dumps([
					{ "name": conversion.get_name(), "arguments": conversion.get_arguments() }
					for conversion in conversions
				]).encode("UTF-8")
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
			filename = removeFE(query.get("name"))
			filename = filename.replace("<", "").replace(">", "").replace("/", "").replace("&", "")
			file_extension = query.get("name").split(".")[-1]
			file_extension = file_extension.replace("<", "").replace(">", "").replace("/", "").replace("&", "")
			# Ensure file does not already exist
			while filename + "." + file_extension in project.files:
				filename += "_"
			# Guess file type
			try:
				file_type = File.guess_type(body)
			except: return {
				"status": 400,
				"headers": {},
				"content": b"Invalid File Type - " + file_extension.encode("UTF-8")
			}
			# Save
			project.files.add_file(filename, File(file_type, file_extension, File.get_duration(body, file_type), body))
			return {
				"status": 200,
				"headers": {},
				"content": b""
			}
		elif path.startswith("/convert/"):
			# Find project
			project_id = unquote(path).split("/")[2]
			project = findProject(project_id)
			if project == None:
				return {
					"status": 404,
					"headers": {},
					"content": b"Project Not Found"
				}
			# Find files
			files: list[NamedFile] = []
			for filename in unquote(path).split("/")[3:]:
				if filename not in project.files:
					return {
						"status": 404,
						"headers": {},
						"content": b"File Not Found: " + filename.encode("UTF-8")
					}
				files.append((removeFE(filename), project.files[filename]))
			# Get conversion
			conversion_index = int(query.get("c"))
			conversion = get_available_conversions(files)[conversion_index]
			# Apply conversion
			project.apply_conversion(conversion, body.decode("UTF-8"))
			return {
				"status": 200,
				"headers": {},
				"content": b""
			}
		elif path.startswith("/rename_file/"):
			project_id = path[13:]
			project = findProject(project_id)
			if project == None:
				return {
					"status": 404,
					"headers": {},
					"content": b"Project Not Found"
				}
			filename = query.get("name") # Name with extension
			if filename not in project.files:
				return {
					"status": 404,
					"headers": {},
					"content": b"File Not Found"
				}
			newName = query.get("newName") # Name without extension
			if newName + "." + project.files[filename].extension in project.files:
				return {
					"status": 404,
					"headers": {},
					"content": b"File Already Exists"
				}
			# Rename the file
			project.files.add_file(newName, project.files[filename])
			del project.files[filename]
			return {
				"status": 200,
				"headers": {},
				"content": b""
			}
		elif path.startswith("/delete_file/"):
			project_id = path[13:]
			project = findProject(project_id)
			if project == None:
				return {
					"status": 404,
					"headers": {},
					"content": b"Project Not Found"
				}
			filename = query.get("name")
			if filename not in project.files:
				return {
					"status": 404,
					"headers": {},
					"content": b"File Not Found"
				}
			# Rename the file
			del project.files[filename]
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
