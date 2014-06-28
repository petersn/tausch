#! /usr/bin/python

import socket, struct, time

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("", 50002))
s.listen(1)
conn, addr = s.accept()
fd = conn.makefile()
def S(*x):
	msg = "".join(struct.pack("<q", i) if isinstance(i, int) else i for i in x)
	print "Sending:", repr(msg)
	fd.write(msg)
	fd.flush()
def Z(x):
	return "%x" % x + "\0"
def read_results():
	count, = struct.unpack("<q", fd.read(8))
	results = []
	for i in xrange(count):
		sub, = struct.unpack("<q", fd.read(8))
		s = ""
		while not s.endswith("\0"): s += fd.read(1)
		results.append((sub, int(s[:-1], 16)))
	return results
print "Connected by", addr
S("s", 1, Z(1000))
S("a", 1, 2, Z(2))
S("c", 2, 3, Z(4)) 
S("r", 3)
print read_results()
conn.close()

