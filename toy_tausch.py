#! /usr/bin/python
"""
Tausch server/client implementation.
"""

import damgaardjurik
import socket

version = (0, 1)

version_string = "tausch v%i.%i" % version

class User:
	def __init__(self, parent, uid):
		self.uid = uid
		self.selectors = {}
		self.block_queue = []
		self.result_queue = []
		# These two set the maximum number of connections
		# and operations the user is willing to perform
		# in a single round.
		self.max_conns = 0
		self.max_opers = 0
		self.modulus = 1

	def selector(self, uid, block):
		self.selectors[uid] = damgaardjurik.unpack_int(block)

	def set_var(self, var, value):
		try:
			value = int(value)
		except ValueError:
			return False
		if value < 0: return False
		if var == "max_conns":
			self.max_conns = value
		elif var == "max_opers":
			self.max_opers = value
		else: return False
		return True

	def get_var(self, var):
		if var == "max_conns":
			return str(self.max_conns)
		elif var == "max_opers":
			return str(self.max_opers)
		return None

	def set_modulus(self, data):
		self.modulus = damgaardjurik.unpack_int(data)

	def add_block(self, block):
		self.block_queue.append(block)

	def get_result(self):
		if not self.result_queue:
			return None
		return self.result_queue.pop(0)

class TauschServer:
	config = {
		# Damgaard-Jurik parameters.
		"dj_bytes": 128,
		"dj_s": 1,
	}

	def __init__(self):
		self.user_index = 0
		self.users = {}

	def new_user(self):
		u = self.users[self.user_index] = User(self, self.user_index)
		self.user_index += 1
		return u

	def process_round(self):
		# Remove one block from each user's queue.
		blocks = {}
		for u in self.users.values():
			if u.block_queue:
				blocks[u.uid] = damgaardjurik.unpack_int(u.block_queue.pop(0))
		print "Got %i blocks for this round." % len(blocks)
		# Process the subscriptions.
		for u in self.users.values():
			accum = 1
			for uid, base in u.selectors.items():
				if uid not in blocks: continue
				print "Processing %i -- %i" % (u.uid, uid)
				accum *= pow(base, blocks[uid], u.modulus)
				accum %= u.modulus
			print "New result for %i" % u.uid
			u.result_queue.append(damgaardjurik.pack_int(accum))

class TauschClient:
	def __init__(self, sock):
		self.dj = damgaardjurik.DamgaardJurik(128, 1)
		self.sock = sock
		self.sock_file = self.sock.makefile()
		# Perform the handshake.
		server_version = self.sock_file.readline().strip()
		assert server_version == version_string, \
			"server is of version: %r, we are: %r" % (server_version, version_string)
		self.sock.send("begin\n")
		self.uid = int(self.sock_file.readline().strip())
		self.send_data("modulus", self.dj.nsp)
		self.status()

	@staticmethod
	def connect(host, port=50506):
		sock = socket.socket()
		sock.connect((host, port))
		ctx = TauschClient(sock)
		return ctx

	def send_data(self, command, datum):
		if isinstance(datum, (int, long)):
			datum = damgaardjurik.pack_int(datum)
		self.sock.send("%s %i\n" % (command, len(datum)))
		self.sock.send(datum)

	def status(self):
		assert self.sock_file.readline() == "yes\n"

	def select(self, uid, x):
		selector = self.dj.encrypt(x)
		self.send_data("select %i" % uid, selector)
		self.status()

	def block(self, x):
		self.send_data("block", x)
		self.status()

	def pull(self):
		self.sock.send("pull\n")
		length = int(self.sock_file.readline().strip())
		datum = self.sock_file.read(length)
		x = self.dj.decrypt(damgaardjurik.unpack_int(datum))
		return x

	def round(self):
		self.sock.send("round\n")

if __name__ == "__main__":
	# Emulate two users, transmitting data.
	u1 = TauschClient.connect("localhost")
	u2 = TauschClient.connect("localhost")
	print "UIDs:", u1.uid, u2.uid
	u1.select(u1.uid, 1)
	u1.select(u2.uid, 3)
	u2.select(u1.uid, 7)
	u2.select(u2.uid, 1)
	u1.block(10)
	u2.block(100)
	u1.round()
	m1 = u1.pull()
	m2 = u2.pull()
	print "Results:", m1, m2

