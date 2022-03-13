from __future__ import print_function
try:
	import SocketServer as socketserver
except:
	import socketserver
import threading
import logging
import socket

class CommandRequestHandler(socketserver.StreamRequestHandler):
	def handle(self):
		self.server.logger.debug("Got connection from %s", self.client_address)
		try:
			while True:
				data = self.rfile.readline()
				if len(data)==0: #socket closed?
					break
				command_line = data.decode("utf-8").rstrip("\r\n")
				response = self.server.command_callback(command_line)
				if response==None:
					break
				self.wfile.write(response.encode("utf-8"))
		except IOError as ex:
			pass
		self.server.logger.debug("Lost connection from %s", self.client_address)



class AddrReuseTCPServer(socketserver.ThreadingTCPServer):
	def __init__(self, server_address, RequestHandlerClass):
		self.allow_reuse_address = True
		self. address_family = socket.AF_INET6
		socketserver.TCPServer.__init__(self,server_address,RequestHandlerClass)


class TCPCommandLineServer(AddrReuseTCPServer):
	def __init__(self, port, command_callback):
		AddrReuseTCPServer.__init__(self,("",port), CommandRequestHandler)
		self.command_callback = command_callback
		self.logger = logging.getLogger(__name__)
	

	
if __name__ == "__main__":
	import socket, time
	class ServeThread(threading.Thread):
		def __init__(self,tcp_server):
			threading.Thread.__init__(self)
			self.tcp_server = tcp_server
		def run(self):
			self.tcp_server.serve_forever()
	
	last_command=None
	def test_callback(command_line):
		global last_command
		last_command = command_line
		print("test_callback: command_line=",command_line)
		return "ok:"+command_line
	
	server = TCPCommandLineServer(8720,test_callback)
	thread = ServeThread(server)
	thread.start()
	
	s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	s.connect(("localhost",8720))
	
	s.send("hello\n")
	time.sleep(0.5)
	assert last_command=="hello"
	s.setblocking(0)
	assert s.recv(1024) == "ok:hello"
	
	s.send("hello2\n")
	time.sleep(0.5)
	assert last_command=="hello2"
	s.setblocking(0)
	assert s.recv(1024) == "ok:hello2"
	
	s.close()
	
	server.shutdown()
