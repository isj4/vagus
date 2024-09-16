import InstanceRegistry
import VagusRegistry
import Config
import struct
import logging
import time
import os, subprocess

logger = None



def process_message(message,source_address):
	global logger
	if not logger:
		logger = logging.getLogger(__name__)
	logger.debug("Handling message")
	if not message:
		return
	if len(message)<5+4+1:
		return
	if message[0:5].decode("utf-8")!="vagus":
		return
	(signature,length,message_type) = struct.unpack("!5siB",message[0:10])
	payload = message[10:]
	if length!=len(message):
		logger.warn("incorrect length")
		return
	
	logger.debug("Got valid vagus message, type=0x%x, length=%d", message_type, length)
	
	if message_type==1:
		process_announcement(payload,source_address)
	else:
		logger.info("Got invalid vagus message")


def process_announcement(payload,source_address):
	if len(payload)<8:
		logger.debug("Got invalid payload")
		return
	p = 0
	(announcement_end_of_life,) = struct.unpack("!I",payload[p:p+4])
	p += 4
	(vagus_id_length,) = struct.unpack("!B",payload[p:p+1])
	p += 1
	if len(payload)-p < vagus_id_length:
		logger.debug("Got invalid payload: invalid vagus_id_length %d",vagus_id_length)
		return
	vagus_id = payload[p:p+vagus_id_length].decode("utf-8")
	p += vagus_id_length
	(cluster_id_length,) = struct.unpack("!B",payload[p:p+1])
	p += 1
	if len(payload)-p < cluster_id_length:
		logger.debug("Got invalid payload")
		return
	cluster_id = payload[p:p+cluster_id_length].decode("utf-8")
	p += cluster_id_length
	instance_information = []
	while p<len(payload):
		if len(payload)-p < 6:
			logger.debug("Got invalid payload")
			return
		(instance_id_length,) = struct.unpack("!B",payload[p:p+1])
		p += 1
		if len(payload)-p < instance_id_length:
			logger.debug("Got invalid payload, instance_id_length=%d",instance_id_length)
			return
		instance_id = payload[p:p+instance_id_length].decode("utf-8")
		p += instance_id_length
		if len(payload)-p < 8+1:
			logger.debug("Got invalid payload, len(payload)=%d, p=%d",len(payload),p)
			return
		(instance_end_of_life,) = struct.unpack("!Q",payload[p:p+8])
		instance_end_of_life = instance_end_of_life/1000.0
		p += 8
		(extra_information_length,) = struct.unpack("!B",payload[p:p+1])
		p += 1
		if len(payload)-p < extra_information_length:
			logger.debug("Got invalid payload")
			return
		extra_information = payload[p:p+extra_information_length].decode("utf-8")
		p += extra_information_length
		if extra_information=="":
			extra_information = None
		instance_information.append((instance_id,instance_end_of_life,extra_information))
	logger.debug("Got announcement from %s, %d instances", vagus_id, len(instance_information))
	
	if announcement_end_of_life < time.time():
		logger.info("Got expired announcement from %s (announcement_end_of_life=%f now=%f)", vagus_id, announcement_end_of_life, time.time())
		if os.access("./got_expired_announcement.sh",os.X_OK):
			try:
				subprocess.call("./got_expired_announcement.sh");
			except:
				pass
		return
	
	VagusRegistry.update_vagus_instance(vagus_id,announcement_end_of_life,source_address)
	
	if vagus_id==Config.identity:
		logger.debug("Got announcement from ourselves")
		return
	
	#update the global registry
	for i in instance_information:
		InstanceRegistry.update_nonlocal_instance(vagus_id,cluster_id,i[0],i[1],i[2])
	
