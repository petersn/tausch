#! /usr/bin/python

import numpy

def split_up(M):
	n = M.shape[0]
	return M[:n/2,:n/2], M[:n/2,n/2:], M[n/2:,:n/2], M[n/2:,n/2:]

muls, adds, negs = 0, 0, 0

def strassen(A, B):
	global muls, adds, negs
	if A.shape == B.shape == (1,1):
		muls += 1
		return A.dot(B)
	A11, A12, A21, A22 = split_up(A)
	B11, B12, B21, B22 = split_up(B)
	ss = A11.shape[0] * A11.shape[1]
	M1 = strassen(A11 + A22, B11 + B22)
	M2 = strassen(A21 + A22, B11)
	M3 = strassen(A11, B12 - B22)
	M4 = strassen(A22, B21 - B11)
	M5 = strassen(A11 + A12, B22)
	M6 = strassen(A21 - A11, B11 + B12)
	M7 = strassen(A12 - A22, B21 + B22)	
	C11 = M1 + M4 - M5 + M7
	C12 = M3 + M5
	C21 = M2 + M4
	C22 = M1 - M2 + M3 + M6
	adds += 13 * ss
	negs += 4 * ss
	R = numpy.empty(A.shape)
	n = A.shape[0]
	R[:n/2,:n/2] = C11
	R[:n/2,n/2:] = C12
	R[n/2:,:n/2] = C21
	R[n/2:,n/2:] = C22
	return R

def best_counts(n):
	ops1 = strassen_counts(n)
	ops2 = naive_counts(n)
	return min((ops1, ops2), key=cost) 

def strassen_counts(n, pure_strassen=False):
	"""strassen_counts(n) -> (multiplications, additions, negations)"""
	if n == 1:
		return (1, 0, 0)
	ss = n**2 / 4
	m, a, i = strassen_counts(n/2, pure_strassen=True) if pure_strassen else best_counts(n/2)
	m, a, i = 7*m, 7*a, 7*i
	a += 13 * ss
	i += 4 * ss
	return m, a, i

def naive_counts(n):
	"""naive_counts(n) -> (multiplications, additions, negations)"""
	return (n**3, (n - 1) * n**2, 0)

def random_matrix(n):
	M = numpy.empty((n, n))
	for i in xrange(n):
		for j in xrange(n):
			M[i,j] = numpy.random.randint(5)
	return M

def cost(ops):
	muls, adds, negs = ops
	mul_speed = 262.718862
	add_speed = 237226.808080
	neg_speed = 39140.574841
	return ops[0] / mul_speed +  ops[1] / add_speed + ops[2] / neg_speed

#A, B = random_matrix(8), random_matrix(8)
#print A
#print B
#X = A.dot(B)
#Y = strassen(A, B)
#print muls, adds, negs

for N in xrange(1, 21):
#	print "Strassen:", strassen_counts(2**N, pure_strassen=True)
#	print "Naive:   ", naive_counts(2**N)
#	print "Mixed:   ", strassen_counts(2**N)
#	print "Best:    ", best_counts(2**N)
	print "[%7i] Best-win: x%.1f" % (2**N, cost(naive_counts(2**N))/cost(strassen_counts(2**N)))

