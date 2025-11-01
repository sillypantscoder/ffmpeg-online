import math

class SubtitleFile:
	def __init__(self, subtitles: list[tuple[float, float, bytes]]):
		self.subtitles = subtitles
	def shift(self, offset_seconds: float):
		# Shift file
		i = 0
		while i < len(self.subtitles):
			self.subtitles[i] = (
				max(self.subtitles[i][0] + offset_seconds, 0),
				self.subtitles[i][1] + offset_seconds,
				self.subtitles[i][2]
			)
			if self.subtitles[i][1] < 0:
				self.subtitles.pop(i)
			else:
				i += 1
	def cropEnd(self, max_duration: float):
		i = 0
		while i < len(self.subtitles):
			self.subtitles[i] = (
				self.subtitles[i][0],
				min(self.subtitles[i][0], max_duration),
				self.subtitles[i][2]
			)
			if self.subtitles[i][0] >= max_duration:
				self.subtitles.pop(i)
			else:
				i += 1
	def save(self):
		# Ensure subtitles are sorted
		self.subtitles.sort(key=lambda x: x[0])
		# Save subtitles to string
		output = b""
		for i in range(len(self.subtitles)):
			s = self.subtitles[i]
			# Stringify start time
			start_time_s = s[0]
			start_time_m = math.floor(start_time_s / 60); start_time_s -= start_time_m * 60
			start_time_h = math.floor(start_time_m / 60); start_time_m -= start_time_h * 60
			start_time = str(start_time_h).rjust(2, "0") + ":" + str(start_time_m).rjust(2, "0") + ":" + str(math.floor(start_time_s)).rjust(2, "0") + "," + str(start_time_s - math.floor(start_time_s)).split(".")[1].ljust(3, "0")[:3]
			# Stringify end time
			end_time_s = s[1]
			end_time_m = math.floor(end_time_s / 60); end_time_s -= end_time_m * 60
			end_time_h = math.floor(end_time_m / 60); end_time_m -= end_time_h * 60
			end_time = str(end_time_h).rjust(2, "0") + ":" + str(end_time_m).rjust(2, "0") + ":" + str(math.floor(end_time_s)).rjust(2, "0") + "," + str(end_time_s - math.floor(end_time_s)).split(".")[1].ljust(3, "0")[:3]
			# Save subtitle entry
			line = str(i + 1).encode("UTF-8") + b"\n" + start_time.encode("UTF-8") + b" --> " + end_time.encode("UTF-8") + b"\n" + s[2] + b"\n\n"
			output += line
		return output
	@staticmethod
	def parse(file: bytes):
		subtitles: list[tuple[float, float, bytes]] = []
		# Parse the file
		items = [section.split(b"\n") for section in file.split(b"\n\n")][:-1]
		for item in items:
			# Parse item time
			timing = item[1].split(b" --> ")
			start_time_h = int(timing[0].split(b":")[0].decode("UTF-8"))
			start_time_m = int(timing[0].split(b":")[1].decode("UTF-8"))
			start_time_s = float(timing[0].split(b":")[2].decode("UTF-8").replace(",", "."))
			start_time = (60 * 60 * start_time_h) + (60 * start_time_m) + start_time_s
			end_time_h = int(timing[1].split(b":")[0].decode("UTF-8"))
			end_time_m = int(timing[1].split(b":")[1].decode("UTF-8"))
			end_time_s = float(timing[1].split(b":")[2].decode("UTF-8").replace(",", "."))
			end_time = (60 * 60 * end_time_h) + (60 * end_time_m) + end_time_s
			contents = item[2]
			subtitles.append((start_time, end_time, contents))
		return SubtitleFile(subtitles)
