#! /usr/bin/python

import socket, struct, time, random

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("", 50002))
s.listen(1)
conn, addr = s.accept()
fd = conn.makefile()
def S(*x):
	msg = "".join(struct.pack("<q", i) if isinstance(i, int) else i for i in x)
#	print "Sending:", repr(msg)
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
SUB_COUNT = 8
STREAM_COUNT = 24
ROUND_COUNT = 48

start_time = time.time()
print "Connected by", addr
for i in xrange(SUB_COUNT):
	print "Filling sub:", i+1
	S("s", i, Z(random.getrandbits(2047)))
	for j in xrange(STREAM_COUNT):
		S("a", i, 1000+j, Z(random.getrandbits(2047)))
print "Sending computations."
for r in xrange(ROUND_COUNT):
	print "For round:", r+1
	for i in xrange(STREAM_COUNT):
		S("c", 1000+i, 1000000+r, Z(random.getrandbits(2047)))
print "Done issuing."
total_results = []
for r in xrange(ROUND_COUNT):
	S("r", 1000000+r)
	data = read_results()
	print "Got data from round:", r+1
	total_results.append(data)
print "Got %i bytes of results." % len(str(total_results))
stop_time = time.time()
conn.close()

tt = stop_time - start_time
to = SUB_COUNT * STREAM_COUNT * ROUND_COUNT
print
print "Total time:", stop_time - start_time
print "Total operations:", to
print "Ops/s:", to / tt

