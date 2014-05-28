#! /usr/bin/python
"""
Tausch server.
"""

handshake_string = "tausch\1\0\0\0"

import SocketServer, traceback, socket, threading, os, time, struct, json, Queue, random, logging

rng = random.SystemRandom()

# This lock synchronizes access to the Context.
main_lock = threading.Lock()

class Context:
	config = {
		# Round length in seconds.
		"interval": 60.0,
	}

	def __init__(self):
		self.users = set()
		self.start_time = time.time()

	def get_general_info(self):
		return {
			"users": len(self.users),
			"time": time.time(),
			"start_time": self.start_time,
			"config": self.config,
		}

	def new_user(self, handler):
		print "New user:", handler
		self.users.add(handler)

	def del_user(self, handler):
		print "Del user:", handler
		self.users.remove(handler)

	def get_workload(self, handler):
		return ""

	def put_workload(self, handler, dataset):
		print "Work completed."

	def begin_new_round(self):
		# Compute the workloads for each stream.
		# These lists of selectors are indexed by stream.
		self.workload_by_uuid = {}
		for user in self.users:
			for index, sub in user.subscriptions.iteritems():
				for uuid, selector in sub.iteritems():
					if uuid not in self.workload_by_uuid:
						self.workload_by_uuid = []
					self.workload_by_uuid[uuid].append((user, index, selector))

class Stream:
	def __init__(self):
		self.blocks = []

class Subscription:
	def __init__(self):
		self.blocks = []
		self.selectors = {}

ctx = Context()

class CoordinatorThread(threading.Thread):
	def run(self):
		while True:
			time.sleep(1)
			with main_lock:
				ctx.begin_new_round()
				# If the workload is empty, wait.
				if ctx.workload_by_uuid
			time.sleep(100)

CoordinatorThread().start()

class TauschServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
	allow_reuse_address = True

class TauschHandler(SocketServer.StreamRequestHandler):
	def handle(self):
		# Perform the handshake.
		self.send(handshake_string)
		reply = self.rfile.read(len(handshake_string))
		if reply != handshake_string:
			return

		# Basic user information.
		self.balance = 0.0
		self.trust = 0.0
		self.config = {
			"max_conns": 0,
			"max_opers": 0,
			"tune_opers_per_conn": 1.0,
#			"short_tag": "",
#			"long_tag": "",
		}
		self.streams = {}
		self.subscriptions = {}
		# Reset all cached user state.
		self.cmd_amnesia()

		# Report ourself to Context.
		with main_lock:
			ctx.new_user(self)

		command_dispatch = {
			"a": self.cmd_user_info,
			"b": self.cmd_general_info,
			"c": self.cmd_get_stream_updates,
			"d": self.cmd_amnesia,
			"e": self.cmd_set_var,
			"f": self.cmd_get_var,
			"g": self.cmd_new_stream,
			"h": self.cmd_del_stream,
			"i": self.cmd_new_subscription,
			"j": self.cmd_del_subscription,
			"k": self.cmd_set_selector,
			"l": self.cmd_get_workload,
			"m": self.cmd_put_workload,
			"n": self.cmd_block_to_stream,
			"o": self.cmd_blocks_from_subscription,
		}

		# Begin processing commands.
		self.good = True
		while self.good:
			command = self.rfile.read(1)
			if command not in command_dispatch:
				return
			command_dispatch[command]()

	def finish(self):
		with main_lock:
			ctx.del_user(self)

	def send(self, s):
		self.wfile.write(s)
		self.wfile.flush()

	def send_blob(self, s):
		if not isinstance(s, str):
			s = json.dumps(s)
		self.send(self.length_encode(s))

	def length_encode(self, s):
		return struct.pack("<I", len(s)) + s

	def get_blob(self, maxlen):
		length, = struct.unpack("<I", self.rfile.read(4))
		if length > maxlen:
			print "Lengths:", length, maxlen
			print "Protocol violation."
			self.good = False
			return
		return self.rfile.read(length)

	def cmd_user_info(self):
		with main_lock:
			s = json.dumps({
				"balance": self.balance,
				"config": self.config,
				"streams": self.streams.keys(),
				"subscriptions": [(k, len(v.blocks)) for k, v in self.subscriptions.iteritems()],
			})
		self.send_blob(s)

	def cmd_general_info(self):
		with main_lock:
			info = ctx.get_general_info()
		self.send_blob(info)

	def cmd_get_stream_updates(self):
		with main_lock:
			new_streams = set()
			for user in ctx.users:
				new_streams.update(user.streams.iterkeys())
		diffs = []
		# Find the deleted streams.
		for stream in self.known_streams:
			if stream not in new_streams:
				diffs.append("d" + stream.decode("hex"))
		# Find the new streams.
		for stream in new_streams:
			if stream not in self.known_streams:
				diffs.append("a" + stream.decode("hex"))
		# Update our cache.
		self.known_streams = new_streams
		# Send the user the list of diffs.
		s = "".join(diffs)
		self.send_blob(s)

	def cmd_amnesia(self):
		self.known_streams = set()

	def cmd_set_var(self):
		var = self.get_blob(16)
		value = self.get_blob(8192)
		success = var in self.config
		if success:
			# Attempt to cast the value to the appropriate type.
			try:
				self.config[var] = type(self.config[var])(value)
			except ValueError:
				success = False
		self.send_blob("01"[success])

	def cmd_get_var(self):
		var = self.get_blob(16)
		value = str(self.config.get(var, ""))
		self.send_blob(value)

	def cmd_new_stream(self):
		raw_uuid = os.urandom(20)
		uuid = raw_uuid.encode("hex")
		with main_lock:
			self.streams[uuid] = Stream()
		self.send_blob(raw_uuid)

	def cmd_del_stream(self):
		uuid = self.get_blob(20).encode("hex")
		with main_lock:
			self.send_blob("01"[uuid in self.streams])
			if uuid in self.streams:
				self.streams.pop(uuid)

	def cmd_new_subscription(self):
		index = len(self.subscriptions)
		self.subscriptions[index] = Subscription()
		self.send_blob(struct.pack("<I", index))

	def cmd_del_subscription(self):
		s = self.get_blob(4)
		if len(s) != 4:
			print "Protocol violation."
			self.good = False
			return
		index, = struct.unpack("<I", s)
		with main_lock:
			self.send_blob("01"[index in self.subscriptions])
			if index in self.subscriptions:
				self.subscriptions.pop(index)

	def cmd_set_selector(self):
		s, raw_uuid = self.get_blob(4), self.get_blob(20)
		if len(s) != 4 or len(raw_uuid) != 20:
			print "Protocol violation."
			self.good = False
			return
		index, = struct.unpack("<I", s)
		uuid = raw_uuid.encode("hex")
		selector = self.get_blob(4096)
		with main_lock:
			flag = index in self.subscriptions and \
				uuid in self.known_streams
			self.send_blob("01"[flag])
			if flag:
				self.subscriptions[index].selectors[uuid] = selector

	def cmd_get_workload(self):
		with main_lock:
			workload = ctx.get_workload(self)
		self.send_blob(workload)

	def cmd_put_workload(self):
		dataset = self.get_blob(2**20)
		with main_lock:
			success = ctx.put_workload(self, dataset)
		self.send_blob("01"[success])

	def cmd_block_to_stream(self):
		raw_uuid = self.get_blob(20)
		if len(raw_uuid) != 20:
			print "Protocol violation."
			self.good = False
			return
		uuid = raw_uuid.encode("hex")
		block = self.get_blob(4096)
		with main_lock:
			self.send_blob("01"[uuid in self.streams])
			if uuid in self.streams:
				self.streams[uuid].blocks.append(block)

	def cmd_blocks_from_subscription(self):
		s = self.get_blob(4)
		if len(s) != 4:
			print "Protocol violation."
			self.good = False
			return
		index, = struct.unpack("<I", s)
		with main_lock:
			self.send_blob("01"[index in self.subscriptions])
			if index in self.subscriptions:
				sub = self.subscriptions[index]
				s = "".join(map(self.length_encode, sub.blocks))
				sub.blocks = []
				self.send_blob(s)

HOST = ""
PORT = 50506
TauschServer((HOST, PORT), TauschHandler).serve_forever()

