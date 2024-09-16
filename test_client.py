#!/usr/bin/env python
from __future__ import print_function
import sys
import time
import socket

if len(sys.argv)<2:
	print("Usage: %s <cluster name> <instance> [<extra_info>]"%sys.argv[0], file=sys.stderr)
	sys.exit(1)

cluster = sys.argv[1]
identifer = sys.argv[2]
extra_info = sys.argv[3] if len(sys.argv)>3 else None
if sys.version[0]<'3':
	cluster = unicode(cluster,"utf-8")
	identifer = unicode(identifer,"utf-8")
	if extra_info is not None:
		extra_info = unicode(extra_info,"utf-8")


while True:
	s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	try:
		print("Connecting")
		s.connect(("localhost",8720))
		
		print("Connected")
		while True:
			print("sending keepalive")
			if extra_info is None:
				cmd = "keepalive "+cluster+":"+identifer+":5000\n"
			else:
				cmd = "keepalive "+cluster+":"+identifer+":5000:"+extra_info+"\n"
			s.send(cmd.encode("utf-8"))
			time.sleep(0.5)
	except socket.error as ex:
		pass
	finally:
		s.close()
	time.sleep(10)

