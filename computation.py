#! /usr/bin/python

Big = lambda x: x
try:
	import gmpy
	Big = gmpy.mpz
except ImportError:
	pass

class Exponentiator:
	def __init__(self, base, modulus, bits):
		self.base = Big(base)
		self.modulus = Big(modulus)
		self.table = None

	def raise(self, exp):
		# Use the slow method if no fast-table is stored.
		if self.table is None:
			return pow(self.base, exp, self.modulus)
		# Otherwise, use the fast method.
		i, accum, mask = 0, 1, (1<<self.tradeoff)-1
		while exp:
			accum *= self.table[i, exp&mask]
			accum %= self.modulus
			exp >>= self.tradeoff
			i += self.tradeoff
		return accum

	def build_table(self, tradeoff=4):
		self.tradeoff = tradeoff
		self.table = {}
		x = self.base
		for i in xrange(0, bits, tradeoff):
			for j in xrange(1, 2**tradeoff):
				self.table[i, j] = pow(x, j, self.modulus)
			# Advance x by tradeoff bits.
			x = pow(x, 2**tradeoff, self.modulus)

e = Exponentiator(1231, 451803740921734091723901782903812, 100)
print e.raise(10)

