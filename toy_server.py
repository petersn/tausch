#! /usr/bin/python
"""
Tausch protocol.
The server and client send up and back "\\n" delimited strings.
Handshake:

	server sends tausch version string.
	client sends "begin"

The client may now send a commands.
Each command is space delimited.
Valid commands are:

	set var value
	get var

Sets or gets a user configuration variable.
Valid variables are max_conns and max_opers.

	modulus length

Sets the subscription modulus.
Must be followed by length bytes of data.

	time

Gets the time until the end of the round.

	block length

Sends a data block.
Must be followed by length bytes of data.

	select uid length

Sets the subscription selector for a given uid.
Must be followed by length bytes of data.

	pull

Pulls a queued round result for us.

	update

Asks for an update to our cached selectors.

	work

Asks for a dataset to work on.

	submit length

Submits the answers to a completed dataset.
Must be followed by length bytes of data.
"""

import SocketServer, traceback, socket, threading, os, time
import toy_tausch as tausch

ctx = tausch.TauschServer()
ctx_lock = threading.Lock()

#def tausch_background_process():
#	while True:
#		time.sleep(60.0)
#		with ctx_lock:
#			ctx.process_round()

class TauschServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
	allow_reuse_address = True

class TauschHandler(SocketServer.StreamRequestHandler):
	def handle(self):
		print "Opening connection."

		# Begin the handshake by sending our version.
		self.send(tausch.version_string + "\n")
		# Get one line of reply.
		reply = self.rfile.readline().strip()
		# We want the end user to say "begin".
		if reply != "begin":
			print "Invalid handshake."
			return

		# Allocate a user object for us.
		with ctx_lock:
			user = ctx.new_user()

		self.send("%i\n" % user.uid)

		while True:
			request = self.rfile.readline().strip()
			# An empty line closes the connection.
			if not request: break
			print ">>>", repr(request)
			# Parse out the request from the client.
			line = request.split(" ")
			if line[0] == "set":
				with ctx_lock:
					status = user.set_var(line[1], line[2])
				self.send_status(status)
			elif line[0] == "get":
				with ctx_lock:
					value = user.get_var(line[1])
				self.send_status(value is not None)
				if value is not None:
					self.send(value + "\n")
			elif line[0] == "modulus":
				block = self.rfile.read(int(line[1]))
				with ctx_lock:
					user.set_modulus(block)
				self.send_status(True)
			elif line[0] == "time":
				# TODO: Switch this over once rounds work.
				self.send("60.0\n")
#				with ctx_lock:
#					t = ctx.round_time_remaining()
#				self.send("%f\n" % t)
			elif line[0] == "block":
				block = self.rfile.read(int(line[1]))
				with ctx_lock:
					user.add_block(block)
				self.send_status(True)
			elif line[0] == "select":
				uid, length = map(int, line[1:])
				block = self.rfile.read(length)
				with ctx_lock:
					if uid in ctx.users:
						user.selector(uid, block)
						self.send_status(True)
					else:
						self.send_status(False)
			elif line[0] == "pull":
				with ctx_lock:
					block = user.get_result()
				if block is None:
					self.send("0\n")
				else:
					self.send("%i\n" % len(block))
					self.send(block)
			elif line[0] == "round":
				# Debugging routine! Won't be a valid command in the end.
				print "Running round!"
				with ctx_lock:
					ctx.process_round()
			else:
				# The client sent an invalid command.
				self.send_status(False)

		print "Closing connection."

	def send(self, s):
		self.wfile.write(s)
		self.wfile.flush()

	def send_status(self, status):
		if status:
			self.send("yes\n")
		else:
			self.send("no\n")

HOST = ""
PORT = 50506
TauschServer((HOST, PORT), TauschHandler).serve_forever()

