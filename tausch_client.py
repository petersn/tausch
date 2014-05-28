#! /usr/bin/python
"""
Tausch client.
"""

import socket, json, struct, pprint
import damgaardjurik

handshake_string = "tausch\1\0\0\0"

class ProtocolError(Exception): pass

class TauschClient:
	def __init__(self, sock):
		self.dj = damgaardjurik.DamgaardJurik(128, 1)
		self.sock = sock
		self.fd = sock.makefile()
		# Perform the handshake.
		self.fd.write(handshake_string)
		version = self.fd.read(len(handshake_string))
		if version != handshake_string:
			raise ProtocolError("server version: %r, our version: %r" % (version, handshake_string))
		self.stream_set = set()

	@staticmethod
	def connect(host, port=50506):
		sock = socket.socket()
		sock.connect((host, port))
		return TauschClient(sock)

	def send(self, s):
		self.fd.write(s)
		self.fd.flush()

	def send_blob(self, s):
		self.fd.write(struct.pack("<I", len(s)))
		self.send(s)

	def get_blob(self):
		length, = struct.unpack("<I", self.fd.read(4))
		return self.fd.read(length)

	def get_json_blob(self):
		s = self.get_blob()
		return json.loads(s)

	def get_stream_updates(self):
		self.send("c")
		diffs = self.get_blob()
		for i in xrange(0, len(diffs), 21):
			diff = diffs[i:i+21]
			stream = diff[1:].encode("hex")
			if diff[0] == "a":
				print "Add stream:", stream
				self.stream_set.add(stream)
			elif diff[0] == "d":
				print "Del stream:", stream
				# Let the exception happen, for debugging.
				self.stream_set.remove(stream)
			else: assert False

	def get_user_info(self):
		self.send("a")
		return ctx.get_json_blob()

	def get_general_info(self):
		self.send("b")
		return ctx.get_json_blob()

	def set_var(self, var, value):
		value = str(value)
		self.fd.write("e")
		self.send_blob(var)
		self.send_blob(value)
		return self.get_blob() == "1"

	def get_var(self, var):
		self.fd.write("f")
		self.send_blob(var)
		return self.get_blob()

	def new_stream(self):
		self.send("g")
		return self.get_blob().encode("hex")

	def del_stream(self, uuid):
		self.fd.write("h")
		self.send_blob(uuid.decode("hex"))
		return self.get_blob() == "1"

	def new_subscription(self):
		self.send("i")
		return struct.unpack("<I", self.get_blob())[0]

	def del_subscription(self, index):
		self.fd.write("j")
		self.send_blob(stuct.pack("<I", index))
		return self.get_blob() == "1"

	def set_selector(self, index, uuid, coefficient):
		assert len(uuid) == 40, "UUIDs must be 40 hex digits."
		self.fd.write("k")
		self.send_blob(struct.pack("<I", index))
		self.send_blob(uuid.decode("hex"))
		ciphertext = damgaardjurik.pack_int(self.dj.encrypt(coefficient))
		self.send_blob(ciphertext)
		return self.get_blob() == "1"

	def get_workload(self):
		self.send("l")
		workload = self.get_blob()

	def put_workload(self, dataset):
		self.fd.write("m")
		self.send_blob(dataset)
		return self.get_blob() == "1"

	def block_to_stream(self, index, block):
		self.fd.write("n")
		self.send_blob(struct.pack("<I", index))
		self.send_blob(block)
		return self.get_blob() == "1"

	def blocks_from_subscription(self, index):
		self.fd.write("o")
		self.send_blob(struct.pack("<I", index))
		success = self.get_blob() == "1"
		if success:
			s = self.get_blob()
			blocks = []
			while s:
				length, = struct.unpack("<I", s[:4])
				blocks.append(s[4:4+length])
				s = s[4+length:]
			return blocks

if __name__ == "__main__":
	ctx = TauschClient.connect("localhost")
	print ctx.set_var("max_conns", 5)
	uuid = ctx.new_stream()
	print "Stream UUID:", uuid
	print "Sub index:", ctx.new_subscription()
	pprint.pprint(ctx.get_user_info())
	pprint.pprint(ctx.get_general_info())
	ctx.get_stream_updates()
	print ctx.stream_set
	print "Selector success:", ctx.set_selector(0, uuid, 2)

