import time
import copy
import threading
import Config

vagus_instances = {} #id-> (timestamp,eol,source_address)
lock = threading.Lock()


def update_vagus_instance(vagus_id,end_of_life,source_address):
	with lock:
		vagus_instances[vagus_id] = (time.time(),end_of_life,source_address)


def expire():
	now = time.time()
	with lock:
		for k in list(vagus_instances.keys()):
			if vagus_instances[k][1]<now:
				del vagus_instances[k]

def get_vagus_dict():
	expire()
	d = copy.deepcopy(vagus_instances)
	if Config.identity not in d:
		#ensure we are always present
		d[Config.identity] = (time.time(), time.time()+Config.announcement_interval_max*2/1000.0,None)
	return d
