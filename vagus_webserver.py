#!/usr/bin/env python
from __future__ import print_function
import sys
if sys.version_info[0]<3:
	from BaseHTTPServer import HTTPServer
	from BaseHTTPServer import BaseHTTPRequestHandler
	from SocketServer import ThreadingMixIn
	import urlparse
else:
	from http.server import HTTPServer
	from http.server import BaseHTTPRequestHandler
	from socketserver import ThreadingMixIn
	import urllib.parse as urlparse

import argparse
import logging
import logging.config
import socket
import cgi
import time


def do_command(cmd):
	s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	try:
		s.connect(("localhost",8720))
		s.send((cmd+"\n").encode("utf-8"))
		result = ""
		while True:
			r = s.recv(1000000)
			if len(r)==0: #socket closed, but we don't expect that
				return None
			result += r.decode("utf-8")
			if result=="\n" or (len(result)>=2 and result[-2:]=="\n\n"):
				break
		return result
	except socket.error as ex:
		logger.debug("Got exception when trying to talk to vagus: %s",ex)
		pass
	finally:
		s.close()
	return None


def get_cluster_list():
	r = do_command("getclusters")
	if not r or len(r)==0:
		return None
	if r=="\n":
		return []
	return r.split('\n')[0:-2]

def get_instance_list(cluster_id):
	r = do_command("poll %s"%cluster_id)
	if not r or len(r)==0:
		return None
	if r=="\n":
		return []
	#do we want to split/parse into instance-id + extra_information? Nah...
	return r.split('\n')[0:-2]

def get_instance_listx(cluster_id):
	r = do_command("pollx %s"%cluster_id)
	if not r or len(r)==0:
		return None
	if r=="\n":
		return []
	#do we want to split/parse into instance-id + extra_information? Nah...
	l = []
	for line in r.split('\n')[0:-2]:
		instance_id = line.split(':')[0]
		vagus_id = line.split(':')[1]
		lifetime = float(line.split(':')[2])
		if len(line.split(':'))>3:
			extra_info = line.partition(':')[2].partition(':')[2].partition(':')[2]
		else:
			extra_info = ""
		l.append( (vagus_id,instance_id,lifetime,extra_info) )
	return l

def get_vagus_list():
	r = do_command("getvaguslist")
	if not r or len(r)==0:
		return None
	if r=="\n":
		return []
	#parse into id+lastseen+timeout
	l = []
	for line in r.split("\n"):
		if len(line.split(":"))>=4:
			(vagus_id,last_seen,end_of_life) = line.split(":")[0:3]
			address = line.partition(':')[2].partition(':')[2].partition(':')[2]
			last_seen = int(last_seen)
			end_of_life = int(end_of_life)
			l.append((vagus_id,last_seen,end_of_life,address))
	return l



def sort_instance_list_for_display(instance_list):
	#note: Modifies list in-place
	#we want the instances to be sorted but we have to check if they should be numeriacally or alphamerically sorted
	all_numeric = True
	for i in instance_list:
		try:
			_ = int(i[1])
		except ValueError:
			all_numeric = False
			break
	if all_numeric:
		#sort by vagus_id+identifier, but with identifier treated as a number
		instance_list.sort(key=lambda e: (e[0],int(e[1])))
	else:
		instance_list.sort()

class Handler(BaseHTTPRequestHandler):
	def log_message(self,format,*args):
		logger.info("%s" % (format%args))

	def do_GET(self):	
		parsed_url = urlparse.urlparse(self.path)
		parameters = cgi.parse_qs(parsed_url.query)
		#print "parameters=",parameters
		if parsed_url.path.find("..")!=-1:
			self.send_response(404)
			self.end_headers()
			return
		if parsed_url.path=="/":
			return self.serve_root()
		# /cluster/$cluster_id$
		s = parsed_url.path.split("/")
		if len(s)==3 and s[1]=="cluster":
			return self.serve_cluster(s[2])
		if len(s)==3 and s[1]=="cluster_details":
			return self.serve_cluster_details(s[2])
		self.send_response(404)
		self.end_headers()
	
	def serve_vagus_talk_error(self,msg):
		self.send_response(500)
		self.send_header("Content-type", "text/html; charset=utf-8")
		self.end_headers()
		output = []
		output.append('<html>')
		output.append('<body>')
		output.append('<p>%s</p>'%msg)
		output.append('</body>')
		output.append('</html>')
		self.wfile.write('\n'.join(output).encode("utf-8"))
	
	def serve_root(self):
		cluster_list = get_cluster_list()
		if cluster_list is None:
			return self.serve_vagus_talk_error("Could not get cluster list from vagus")
		vagus_list = get_vagus_list()
		if vagus_list is None:
			return self.serve_vagus_talk_error("Could not get vagus list from vagus")
		
		#sort vagus instance list by name
		vagus_list.sort()
		
		self.send_response(200)
		self.send_header("Content-type", "text/html; charset=utf-8")
		self.send_header("cache-control","max-age=0")
		self.end_headers()
		output = []
		output.append('<!DOCTYPE html>')
		output.append('<html>')
		output.append('<head>')
		output.append('<title>Vagus: Overview</title>')
		output.append('<meta name="viewport" content="width=device-width, initial-scale=1.0"/>')
		#output.append('<link rel="stylesheet" type="text/css" href="default.css" title="Default"/>')
		output.append('</head>')
		output.append('<body>')
		
		output.append('<h1>Known clusters (%d)</h1>'%(len(cluster_list)))
		output.append('<ul>')
		for cluster in cluster_list:
			output.append('<li><a href="/cluster/%s">%s</a> (<a href="/cluster_details/%s">details</a>)'%(cluster,cluster,cluster))
		output.append('</ul>')
		
		output.append('<h1>Known Vagus processes (%d)</h1>'%(len(vagus_list)))
		output.append('<table>')
		output.append('    <tr><th>Identity</th><th>Last seen</th><th>end-of-life</th><th>Most recent address</th></tr>')
		for vagus in vagus_list:
			output.append('    <tr>')
			output.append('        <td>%s</td>'%vagus[0])
			last_seen_str = time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(vagus[1]/1000))
			output.append('        <td>%s</td>'%last_seen_str)
			end_of_life_str = time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(vagus[2]/1000))
			output.append('        <td>%s</td>'%end_of_life_str)
			output.append('        <td>%s</td>'%vagus[3])
			output.append('    </tr>')
		output.append('</table>')
			
		output.append('</body>')
		output.append('</html>')
		self.wfile.write('\n'.join(output).encode("utf-8"))
	
	def serve_cluster(self,cluster_id):
		instance_list = get_instance_list(cluster_id)
		if instance_list is None:
			return self.serve_vagus_talk_error("Could not get instance list from vagus")
		sort_instance_list_for_display(instance_list)
		
		self.send_response(200)
		self.send_header("Content-type", "text/html; charset=utf-8")
		self.send_header("cache-control","max-age=0")
		self.end_headers()
		output = []
		output.append('<html>')
		output.append('<head>')
		output.append('<title>Vagus: instances in %s</title>'%(cluster_id))
		output.append('<meta name="viewport" content="width=device-width, initial-scale=1.0"/>')
		#output.append('<link rel="stylesheet" type="text/css" href="default.css" title="Default"/>')
		output.append('</head>')
		output.append('<body>')
		
		output.append('<h1>Alive instances (%d)</h1>'%(len(instance_list)))
		output.append('<ul>')
		for instance in instance_list:
			output.append('<li>%s</li>'%(instance))
		output.append('</ul>')
			
		output.append('</body>')
		output.append('</html>')
		self.wfile.write('\n'.join(output).encode("utf-8"))
	
	def serve_cluster_details(self,cluster_id):
		instance_list = get_instance_listx(cluster_id)
		if instance_list is None:
			return self.serve_vagus_talk_error("Could not get instance list from vagus")
		sort_instance_list_for_display(instance_list)
		
		#count the number of instances in each vagus-instance
		instance_count = {}
		for instance in instance_list:
			if instance[0] not in instance_count:
				instance_count[instance[0]] = 0
			instance_count[instance[0]] += 1
		
		self.send_response(200)
		self.send_header("Content-type", "text/html; charset=utf-8")
		self.send_header("cache-control","max-age=0")
		self.end_headers()
		output = []
		output.append('<html>')
		output.append('<head>')
		output.append('<title>Vagus: instances in %s</title>'%(cluster_id))
		output.append('<meta name="viewport" content="width=device-width, initial-scale=1.0"/>')
		#output.append('<link rel="stylesheet" type="text/css" href="default.css" title="Default"/>')
		output.append('</head>')
		output.append('<body>')
		
		output.append('<h1>Alive instances (%d)</h1>'%(len(instance_list)))
		output.append('<ul>')
		previous_vagus_instance_id = None
		for instance in instance_list:
			if instance[0]!=previous_vagus_instance_id:
				if previous_vagus_instance_id is not None:
					output.append('    </ul></li>')
				output.append('<li>%s (%d instances)'%(instance[0], instance_count[instance[0]]))
				output.append('    <ul>')
				previous_vagus_instance_id = instance[0]
			output.append('    <li>%s:%s:%s:%s</li>'%(instance[0],instance[1],instance[2],instance[3]))
		if previous_vagus_instance_id is not None:
			output.append('    </ul></li>')
		output.append('</ul>')
		
		output.append('</body>')
		output.append('</html>')
		self.wfile.write('\n'.join(output).encode("utf-8"))
	


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
	"""Handle requests in a separate thread."""
	pass


parser = argparse.ArgumentParser(description="Vagus web interface")
parser.add_argument("--loggingconf",type=str,default="logging.dev.conf")
parser.add_argument("--port",type=int,default=8724)
args=parser.parse_args()


logging.config.fileConfig(args.loggingconf)

logger = logging.getLogger(__name__)
logger.info("vagus_webserver starting")

httpd = ThreadedHTTPServer(("", args.port), Handler)
logger.info("vagus_webserver ready")
httpd.serve_forever()

