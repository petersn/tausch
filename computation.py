#! /usr/bin/python

import random, time, multiprocessing

Big = lambda x: x
try:
	import gmpy
	Big = gmpy.mpz
except ImportError:
	pass

def extended_gcd(a, b): 
	"""extended_gcd(a, b) -> (x, y) such that a*x+b*y == 1"""
	x0, x1 = 1, 0
	y0, y1 = 0, 1
	while b:
		q = a / b
		a, b = b, a - q * b
		x0, x1 = x1, x0 - q * x1
		y0, y1 = y1, y0 - q * y1
	return x0, y0

class Exponentiator:
	def __init__(self, base, modulus, bits=None):
		self.base = Big(base)
		self.modulus = Big(modulus)
		self.bits = bits
		self.table = None

	def exp(self, exp):
		# Use the slow method if no table is stored.
		if self.table is None:
			return pow(self.base, exp, self.modulus)
		# Otherwise, use the fast method.
		i, accum, mask = 0, 1, (1 << self.tradeoff)-1
		while exp:
			key = exp & mask
			if key:
				accum = (accum * self.table[i, key]) % self.modulus
			exp >>= self.tradeoff
			i += self.tradeoff
		return accum

	def build_table(self, tradeoff=8):
		assert self.bits is not None, "must set bits in constructor to build table"
		self.tradeoff = tradeoff
		self.table = {}
		x = self.base
		for i in xrange(0, self.bits, tradeoff):
			v = 1
			for j in xrange(1, 2**tradeoff):
				v = (v * x) % self.modulus
				self.table[i, j] = v
			# Advance x by tradeoff bits.
			x = pow(x, 2**tradeoff, self.modulus)

class EngineProcess:
	def __init__(self, output, config):
		self.entry_count = 0
		self.queue = multiprocessing.Queue()
		self.proc = multiprocessing.Process(target=self.process, args=(self.queue, output, config))
		self.proc.start()

	def add_entry(self, entry_ref, base, modulus):
		self.entry_count += 1
		self.queue.put(("add", entry_ref, base, modulus))

	def rm_entry(self, entry_ref):
		self.entry_count -= 1
		self.queue.put(("rm", entry_ref))

	def compute(self, entry_ref, result_ref, exponent):
		self.queue.put(("compute", entry_ref, result_ref, exponent))

	@staticmethod
	def process(queue, output, config):
		table = {}
		while True:
			msg = queue.get()
			if msg[0] == "add":
				exp = table[msg[1]] = Exponentiator(msg[2], msg[3], config["bits"])
				exp.build_table(tradeoff=config["tradeoff"])
			elif msg[0] == "rm":
				table.pop(msg[1])
			elif msg[0] == "compute":
				result = table[msg[1]].exp(msg[3])
				output.put((msg[2], result))
			else:
				assert False

class Engine:
	def __init__(self, bits, tradeoff=8):
		self.results = multiprocessing.Queue()
		config = {"bits": bits, "tradeoff": tradeoff}
		self.pool = [EngineProcess(self.results, config) for _ in xrange(multiprocessing.cpu_count())]
		self.entry_ref = 0
		self.result_ref = 0
		self.entry_mapping = {}

	def add_entry(self, base, modulus):
		self.entry_ref += 1
		# Add the entry to the pool worker with the fewest.
		p = min(self.pool, key=lambda p: p.entry_count)
		p.add_entry(self.entry_ref, base, modulus)
		self.entry_mapping[self.entry_ref] = p
		return self.entry_ref

	def rm_entry(self, entry_ref):
		self.entry_mapping.pop(entry_ref).rm_entry(entry_ref)

	def compute(self, entry_ref, exponent):
		self.result_ref += 1
		self.entry_mapping[entry_ref].compute(entry_ref, self.result_ref, exponent)
		return self.result_ref

	def quit(self):
		for p in self.pool:
			p.proc.terminate()

if __name__ == "__main__":
	BITS = 2048
	ROUNDS = 100
	TRADEOFF = 12
	BASES = 64
	CALLS_PER_BASE = 2000

	print "=== Benchmarking ==="
	print "Using %i-bit moduli." % BITS
	print "Using tables with %i-bit chunks." % TRADEOFF

	b = Big(random.getrandbits(BITS))
	m = Big(random.getrandbits(BITS))
	b %= m
	exp = Exponentiator(b, m, BITS)
	e = Big(random.getrandbits(BITS))

	start = time.time()
	for _ in xrange(ROUNDS):
		v0 = exp.exp(e)
	slow = time.time() - start

	start = time.time()
	exp.build_table(tradeoff=TRADEOFF)
	build = time.time() - start

	start = time.time()
	for _ in xrange(ROUNDS):
		v1 = exp.exp(e)
	fast = time.time() - start

	assert v0 == v1

	table_ops = ROUNDS / fast
	print "Default op/s:", ROUNDS / slow
	print "Table-%i op/s:" % TRADEOFF, table_ops
	print "Ratio:", slow / fast
	print "Build time:", build
	print
	print "=== Multiprocess Benchmarking ==="
	print "Using %i processes." % multiprocessing.cpu_count()
	print "Using %i bases, and %i exponentiations per base." % (BASES, CALLS_PER_BASE)

	eng = Engine(BITS, tradeoff=TRADEOFF)
	indexes = []
	for _ in xrange(BASES):
		b = random.getrandbits(BITS)
		m = random.getrandbits(BITS)
		b %= m
		indexes.append(eng.add_entry(b, m))
	print "All tables built." 
	start = time.time()
	r = []
	for _ in xrange(CALLS_PER_BASE):
		for ind in indexes:
			r.append(eng.compute(ind, random.getrandbits(BITS)))
	output = {}
	for _ in r:
		r_ind, v = eng.results.get()
		output[r_ind] = v
	eng.quit()
	total_time = time.time() - start

	total_ops = (BASES * CALLS_PER_BASE) / total_time
	print "Total op/s:", total_ops
	print "Ratio:", total_ops / table_ops
	print "Efficiency:", (total_ops / (multiprocessing.cpu_count() * table_ops)) * 100

