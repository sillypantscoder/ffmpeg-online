import socket
import http.server
import os
import datetime
#from urllib.parse import unquote
import typing
import sys
from types import TracebackType



def read_file(filename: str) -> bytes:
	f = open(filename, "rb")
	t = f.read()
	f.close()
	return t

def write_file(filename: str, content: bytes):
	f = open(filename, "wb")
	f.write(content)
	f.close()

def log(importance: str, msg: str):
	f = open("log.txt", "a")
	f.write(datetime.datetime.now().isoformat())
	f.write(" - ")
	f.write(importance.center(5))
	f.write(" - ")
	f.write(msg.replace("\n\t", "\n\t\t\t\t\t\t\t\t\t\t"))
	f.write("\n")
	f.close()

def log_existence_check():
	if os.path.isfile("log.txt"):
		if b"-" not in read_file("log.txt"):
			os.remove("log.txt")

class SafeDict:
	def __init__(self, fields: dict[str, str]):
		self.fields: dict[str, str] = fields
	def get(self, key: str, default: str = ''):
		if key.lower() in self.fields:
			return self.fields[key.lower()]
		else:
			return default
	@staticmethod
	def from_list(fields: list[tuple[str, str]]):
		f: dict[str, str] = {}
		for i in fields:
			f[i[0].lower()] = i[1]
		return SafeDict(f)
	@staticmethod
	def from_query(query: str):
		fields: dict[str, str] = {}
		for f in query.split("&"):
			s = f.split("=")
			if len(s) >= 2:
				fields[s[0].lower()] = s[1]
		return SafeDict(fields)
	@staticmethod
	def from_cookies(cookies: str):
		f: dict[str, str] = {}
		if len(cookies.strip()) != 0:
			for cookie in cookies.split(";"):
				key, value = cookie.split("=", 1)
				key, value = key.strip(), value.strip()
				f[key.lower()] = value
		return SafeDict(f)

class HTTPResponse(typing.TypedDict):
	status: int
	headers: dict[str, str]
	content: bytes

class HTTPServer:
	def __init__(self, hostName: str, serverPort: int):
		self.address: tuple[str, int] = (hostName, serverPort)
		self.webServer = http.server.HTTPServer((hostName, serverPort), lambda request, client_address, server: ProxyRequestHandler(request, client_address, server, self))
		self.webServer.timeout = 1
	def run(self):
		running = True
		print(f"Server started http://{self.address[0]}:{self.address[1]}/")
		while running:
			try:
				self.webServer.handle_request()
			except KeyboardInterrupt:
				running = False
		self.webServer.server_close()
		print("Server stopped")
	def get(self, path: str, query: SafeDict, headers: SafeDict, cookies: SafeDict) -> HTTPResponse:
		if os.path.isfile("public_files" + path):
			returnheaders = {
				"Content-Type": {
					"html": "text/html",
					"json": "application/json",
					"css": "text/css",
					"ico": "image/x-icon",
					"jpeg": "image/jpeg",
					"png": "image/png",
					"js": "application/javascript",
					"txt": "text/plain",
					"xml": "image/svg+xml"
				}[path.split(".")[-1]]
			}
			return {
				"status": 200,
				"headers": returnheaders,
				"content": read_file("public_files" + path)
			}
		elif path == "/":
			return {
				"status": 200,
				"headers": {
					"Content-Type": "text/html"
				},
				"content": read_file("index.html")
			}
		else: # 404 page
			log("", "404 encountered: " + path + "\n\t(Referrer: " + headers.get("Referer") + ")")
			return {
				"status": 404,
				"headers": {
					"Content-Type": "text/html"
				},
				"content": b"404 Page Not Found"
			}
	def post(self, path: str, query: SafeDict, body: bytes) -> HTTPResponse:
		log("#", "404 POST encountered: " + path)
		return {
			"status": 404,
			"headers": {
				"Content-Type": "text/html"
			},
			"content": b"404 POST"
		}

class ProxyRequestHandler(http.server.BaseHTTPRequestHandler):
	def __init__(self, request: socket.socket, client_address: tuple[str, int], server: http.server.HTTPServer, interface: HTTPServer):
		self.interface: HTTPServer = interface
		super().__init__(request, client_address, server)
	def do_GET(self):
		log_existence_check()
		# Attempt to get response
		try:
			splitpath = self.path.split("?")
			res = self.interface.get(splitpath[0], SafeDict.from_query(''.join(splitpath[1:])), SafeDict.from_list(self.headers.items()), SafeDict.from_cookies(self.headers["Cookie"] if self.headers["Cookie"] != None else ''))
		except Exception as e:
			# Get exception info
			tb = sys.exc_info()[2]
			self.handle_server_error(e, tb)
			res: HTTPResponse = {
				"status": 500,
				"headers": {},
				"content": b""
			}
		# Send response
		self.send_response(res["status"])
		for h in res["headers"]:
			self.send_header(h, res["headers"][h])
		self.end_headers()
		c = res["content"]
		self.wfile.write(c)
	def do_POST(self):
		# Get response
		splitpath = self.path.split("?")
		try:
			res = self.interface.post(splitpath[0], SafeDict.from_query(''.join(splitpath[1:])), self.rfile.read(int(self.headers["Content-Length"])))
		except Exception as e:
			# Get exception info
			tb = sys.exc_info()[2]
			self.handle_server_error(e, tb)
			res: HTTPResponse = {
				"status": 500,
				"headers": {},
				"content": b""
			}
		# Send response
		self.send_response(res["status"])
		for h in res["headers"]:
			self.send_header(h, res["headers"][h])
		self.end_headers()
		self.wfile.write(res["content"])
	def log_message(self, format: str, *args: typing.Any) -> None:
		return
	def handle_server_error(self, exception: BaseException, tb: TracebackType | None):
		if tb != None: tb = tb.tb_next
		frames: list[str] = []
		while tb != None:
			frames.append(str(tb.tb_frame))
			tb = tb.tb_next
		frames = [x[26:-1] for x in frames]
		frames.reverse()
		all_error_info = f"[WARNING!] Server encountered error during handing of request:\n\tRequest path: {self.path}\n\tError details: {exception.__class__.__name__}: {str(exception)}" + \
			"\n\tTraceback (most recent call first):\n\t\t" + "\n\t\t".join(frames)
		log("!ERR!", all_error_info)
		print(all_error_info, file=sys.stderr)

if __name__ == "__main__":
	server = HTTPServer('0.0.0.0', 10803)
	server.run()