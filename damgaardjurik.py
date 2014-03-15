#! /usr/bin/python

import random

rng = random.SystemRandom()

def miller_rabin(n, k=32):
	"""miller_rabin(n, k=32) -> bool

	If n is prime, returns True.
	Otherwise, returns True with probability 4**(-k).
	"""
	nm = [n-1, n-2]
	d, s = nm[0], 0
	while not d&1:
		d >>= 1
		s += 1
	for _ in xrange(k):
		a = random.randint(2, nm[1])
		x  = pow(a, d, n)
		if x == 1 or x == nm[0]:
			continue
		for _ in xrange(s):
			x = (x**2) % n
			if x == 1:
				return False
			elif x == nm[0]:
				break
		else:
			return False
	return True

def modular_inverse(a, m):
	"""modular_inverse(a, m) -> int

	Returns b such that (a*b)%m == 1
	"""
	def egcd(a, b):
		if a == 0:
			return (b, 0, 1)
		g, y, x = egcd(b % a, a)
		return g, x - (b // a) * y, y
	g, x, y = egcd(a, m)
	assert g == 1, "No modular inverse exists!"
	return x % m

def bit_prime(bits):
	"""bit_prime(bits) -> probable prime of given bit length"""
	while True:
		p = rng.getrandbits(bits)
		p |= 1<<(bits-1)
		if miller_rabin(p):
			return p

class DamgaardJurik:
	"""
	Provides Damgaard-Jurik encryption.
	An instance is given two parameters, byte_length, and s.
	Each encryption is of length byte_length*(s+1), and each
	message may be up to byte_length*s bytes long.
	"""
	def __init__(self, byte_length, s):
		self.byte_length, self.s = byte_length, s
		self.p, self.q = bit_prime(self.byte_length*4), bit_prime(byte_length*4)
		self.n = self.p * self.q
		self.l = (self.p-1)*(self.q-1)
		self.ns = self.n**s
		self.nsp = self.ns * self.n
		self.g = self.n + 1
		self.d = modular_inverse(self.l, self.ns)*self.l

	def encrypt(self, x):
		t = rng.getrandbits(self.byte_length*(self.s+1)*8)
		t %= self.nsp
		t = pow(t, self.ns, self.nsp)
		u = pow(self.g, x, self.nsp)
		return (t*u) % self.nsp

	def decrypt(self, x):
		x = pow(x, self.d, self.nsp)
		i = 0
		for j in xrange(1, self.s+1):
			modulus = self.n**j
			v = ((x % (modulus*self.n)) - 1) / self.n
			kfac = 1
			w = i
			for k in xrange(2, j+1):
				kfac *= k
				i -= 1
				w *= i
				w %= modulus
				v -= ((n**(k-1)) % w) * modular_inverse(kfac, modulus)
				v %= modulus
			i = v
		return i

def pack_int(x):
	bytelen = ((x.bit_length()+7)/8)
	s = ("%%0%ix" % (bytelen*2) % x).decode("hex")
	return s

def unpack_int(s):
	return int(s.encode("hex"), 16)

if __name__ == "__main__":
	dj = DamgaardJurik(128, 1)
	x = dj.encrypt(123)
	y = dj.encrypt(321)
	print x
	print y
	print dj.decrypt(x)
	print dj.decrypt(y)
	m = (x*y)%dj.nsp
	print dj.decrypt(m)

