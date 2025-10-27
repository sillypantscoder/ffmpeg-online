from server_lib import SafeDict, read_file, write_file, log, HTTPResponse, HTTPServer
import os
import re
import random
import typing
import json
import subprocess
import threading
from urllib.parse import unquote
from subtitles import SubtitleFile

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
def runWhisperTranscriptionWithProgress(filename: str, cwd: str, progress_callback: typing.Callable[[ float, float ], None]):
	import time as T
	# First find the file size
	duration_seconds = float(subprocess.run([
		"ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", cwd + "/" + filename
	], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode("UTF-8").strip())
	# Set environment variables
	env = os.environ.copy()
	env["PYTHONUNBUFFERED"] = "1"
	# Start the command
	proc = subprocess.Popen(["whisper", "--model", "turbo", "--language", "English", "--threads", "3", "--output_format", "srt", filename], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
	if proc.stdout == None: raise TypeError
	# Thread for pipe flushing
	running = True
	def flush_thread():
		while running:
			if proc.stdout == None: raise TypeError
			proc.stdout.flush()
			T.sleep(1)
	threading.Thread(target=flush_thread, args=()).start()
	# Loop over output
	while running:
		T.sleep(0.125)
		line = proc.stdout.readline()
		if line.startswith(b"["):
			time = line[1:].split(b"]")[0].split(b" --> ")[1]
			# Calculate given time
			try:
				timeH = float(time.split(b":")[-3].decode("UTF-8"))
			except: timeH = 0
			timeM = float(time.split(b":")[-2].decode("UTF-8"))
			timeS = float(time.split(b":")[-1].decode("UTF-8"))
			timeTotal = (60 * ((60 * timeH) + timeM)) + timeS
			if timeTotal > duration_seconds: timeTotal = duration_seconds
			progress_callback(timeTotal, duration_seconds)
		# Finish
		if len(line) == 0: running = False # Done!



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
	@staticmethod
	def from_filename(filename: str):
		data = read_file(filename)
		file_extension = filename.split(".")[-1]
		type = File.guess_type(data)
		return File(type, file_extension, File.get_duration(data, type), data)

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
		new_files.sort(key=lambda x: os.path.getmtime(x))
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
		return [
			(self.files[0][0], File.from_filename(new_files[0]))
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
		# TODO: Cut subtitles separately
		# Run command
		runFFMpegCommandWithProgress([
			"-i", input_filenames[0], "-ss", start_time_str, "-to", end_time_str, folder + "/output." + self.files[0][1].extension
		], duration, self.setProgress)
	def setProgress(self, done: float, total: float):
		self.progress = str(round(1000 * done / total) / 10)
	async def get_result_files(self, new_files: list[str]) -> list[NamedFile]:
		return [
			(self.files[0][0] + "_cut", File.from_filename(new_files[0]))
		]

class CombiningConversion(ConversionWithOwnFolder):
	def __init__(self, files: list[NamedFile]):
		super().__init__(files)
		self.fileType: FileType = { "audio": False, "video": False, "subtitles": False }
		for f in files:
			if f[1].type["audio"]:
				if self.fileType["audio"]: raise TypeError
				else: self.fileType["audio"] = True
			if f[1].type["video"]:
				if self.fileType["video"]: raise TypeError
				else: self.fileType["video"] = True
			if f[1].type["subtitles"]:
				if self.fileType["subtitles"]: raise TypeError
				else: self.fileType["subtitles"] = True
		self.output_file_extension = "mp4" if self.fileType["video"] else ("mp3" if self.fileType["audio"] else ("srt" if self.fileType["subtitles"] else ""))
		self.progress = "0"
	def get_name(self):
		return "Combine Files"
	def get_status(self):
		return "Combining " + " and ".join([n[0] + "." + n[1].extension for n in self.files]) + " (" + self.progress + "% done)"
	async def process_files(self, folder: str, input_filenames: list[str], extra_data: str):
		duration = min([File.get_duration(x[1].contents, x[1].type) for x in self.files])
		# Register input files
		arguments: list[str] = []
		for filename in input_filenames:
			arguments.append("-i")
			arguments.append(filename)
			# Crop SRT files so all files are the same length
			if File.guess_type(read_file(filename))["subtitles"]:
				subtitles = SubtitleFile.parse(read_file(filename))
				subtitles.cropEnd(duration)
				write_file(filename, subtitles.save())
		# Streams
		if self.fileType["video"]: arguments.extend(["-c:v", "copy"])
		if self.fileType["audio"]: arguments.extend(["-c:a", "copy"])
		if self.fileType["subtitles"]: arguments.extend(["-c:s", "mov_text", "-metadata:s:s:0", "language=eng"])
		# Run command!
		runFFMpegCommandWithProgress([
			*arguments, "-t", str(duration - 1), folder + "/output." + self.output_file_extension
		], duration, self.setProgress)
	def setProgress(self, done: float, total: float):
		self.progress = str(round(1000 * done / total) / 10)
	async def get_result_files(self, new_files: list[str]) -> list[NamedFile]:
		return [
			("_".join([x[0] for x in self.files]), File.from_filename(new_files[-1]))
		]

class JoinConversion(ConversionWithOwnFolder):
	def __init__(self, files: list[NamedFile]):
		super().__init__(files)
		self.fileType = files[0][1].type
		for f in files:
			if f[1].type != self.fileType:
				raise TypeError
		self.progress = "0"
	def get_name(self):
		return "Join Files"
	def get_status(self):
		return "Joining " + " and ".join([n[0] + "." + n[1].extension for n in self.files]) + " (" + self.progress + "% done)" # TODO: ETA
	async def process_files(self, folder: str, input_filenames: list[str], extra_data: str):
		# Join media (because the "concat" complex filter doesn't support subtitles)
		if self.fileType["audio"] or self.fileType["video"]:
			await self.join_media(folder, input_filenames)
		# Join subtitles
		if self.fileType["subtitles"]:
			# Note that input_filenames is guaranteed to be in the same order as self.files
			# First convert input files to subtitle files
			for i in range(len(input_filenames)):
				subprocess.run(["ffmpeg", "-i", input_filenames[i], f"{folder}/subtitles_{i}.srt"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			# Read files
			subtitles_data = [read_file(f"{folder}/subtitles_{i}.srt") for i in range(len(input_filenames))]
			subtitle_files = [
				(self.files[i][1].duration, subtitles_data[i])
				for i in range(len(input_filenames))
			]
			# Combine files
			await self.join_subtitles(folder, subtitle_files)
		# Combine media and subtitles
		if (self.fileType["audio"] or self.fileType["video"]) and self.fileType["subtitles"]:
			subprocess.run([
				"ffmpeg", "-i", folder + "/output_media." + self.files[0][1].extension,
				"-i", folder + "/output_subtitles.srt", "-c", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng",
				f"{folder}/output_combined.{self.files[0][1].extension}"
			], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	async def join_media(self, folder: str, input_filenames: list[str]):
		# Register input files
		arguments: list[str | typing.Callable[[ ], str]] = []
		for filename in input_filenames:
			arguments.append("-i")
			arguments.append(filename)
		# Complex filter inputs
		complex_filter = ""
		for i in range(len(input_filenames)):
			if self.fileType["video"]: complex_filter += f"[{i}:v:0]"
			if self.fileType["audio"]: complex_filter += f"[{i}:a:0]"
		# Complex filter operation
		complex_filter += f"concat=n={len(input_filenames)}:v={1 if self.fileType['video'] else 0}:a={1 if self.fileType['audio'] else 0}"
		# Add complex filter to arguments
		arguments.append("-filter_complex")
		arguments.append(lambda : complex_filter)
		# Add complex filter outputs and output mappings
		if self.fileType["video"]: complex_filter += "[outv]"; arguments.extend(["-map", "[outv]"])
		if self.fileType["audio"]: complex_filter += "[outa]"; arguments.extend(["-map", "[outa]"])
		# Run command!
		duration = sum([File.get_duration(x[1].contents, x[1].type) for x in self.files])
		runFFMpegCommandWithProgress([
			*[(x if isinstance(x, str) else x()) for x in arguments], folder + "/output_media." + self.files[0][1].extension
		], duration, self.setProgress)
	async def join_subtitles(self, folder: str, subtitle_files: list[tuple[float, bytes]]):
		files: list[SubtitleFile] = [SubtitleFile.parse(data[1]) for data in subtitle_files]
		# Set file offsets
		offset = 0
		for f in range(len(files)):
			files[f].shift(offset)
			offset += subtitle_files[f][0]
		# Combine files
		combined = SubtitleFile([])
		for f in files:
			combined.subtitles.extend(f.subtitles)
		# Save string to file
		write_file(folder + "/output_subtitles.srt", combined.save())
	def setProgress(self, done: float, total: float):
		self.progress = str(round(1000 * done / total) / 10)
	async def get_result_files(self, new_files: list[str]) -> list[NamedFile]:
		return [
			("_".join([x[0] for x in self.files]), File.from_filename(new_files[-1]))
		]

class AudioTranscriptionConversion(ConversionWithOwnFolder):
	def __init__(self, file: NamedFile):
		super().__init__([file])
		self.progress = "Initializing..."
	def get_name(self):
		return "Transcribe"
	def get_status(self):
		return "Transcribing " + self.files[0][0] + "." + self.files[0][1].extension + " (" + self.progress + ")"
	async def process_files(self, folder: str, input_filenames: list[str], extra_data: str):
		runWhisperTranscriptionWithProgress(input_filenames[0].split("/")[-1], folder, self.setProgress)
	def setProgress(self, done: float, total: float):
		self.progress = str(round(1000 * done / total) / 10) + "% done"
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
			if ext != "webm" and not ftype["video"]: conversions.append(FileFormatConversion(named_file, "webm"))
			if ext != "ogg": conversions.append(FileFormatConversion(named_file, "ogg"))
			# Transcription
			conversions.append(AudioTranscriptionConversion(named_file))
		if ftype["subtitles"]:
			# Extract Subtitles
			if ext != "srt": conversions.append(FileFormatConversion(named_file, "srt"))
		# Cut Media
		conversions.append(CutConversion(named_file))
	elif len(files) >= 2:
		# Combining
		try: conversions.append(CombiningConversion(files))
		except TypeError: pass
		# Joining
		try: conversions.append(JoinConversion(files))
		except TypeError: pass
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
