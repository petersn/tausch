// Simplest exponentiation test.

#include <stdio.h>
#include <sys/time.h>
#include <gmp.h>

#include <openssl/bio.h>
#include <openssl/bn.h>
#include <openssl/rand.h>
#include <openssl/err.h>

#define EXP_ITERS 300

#define DT ((stop.tv_sec + stop.tv_usec*1e-6) - (start.tv_sec + start.tv_usec*1e-6))
#define STATS(iters) do { \
		printf("Total time: %f\n", elapsed); \
		printf("Ops:        %i\n", iters); \
		printf("Ops/s:      %f\n", iters / elapsed); \
	} while (0)


//#define NUM_BITS (BN_BITS*2)
#define NUM_BITS 2048

static const char rnd_seed[] = "string to make the random number generator think it has entropy";

int main(int argc, char** argv) {
	struct timeval start, stop; 
	printf("Benchmarking exp: %i\n", NUM_BITS);

	BN_CTX *ctx;
	BIO *out=NULL;
	int i,ret;
	unsigned char c;
	BIGNUM *r_mont,*r_mont_const,*r_recp,*r_simple,*a,*b,*m;
	RAND_seed(rnd_seed, sizeof rnd_seed);
	ERR_load_BN_strings();

	BN_MONT_CTX* bn_mont_ctx = BN_MONT_CTX_new();
	BN_MONT_CTX_init(bn_mont_ctx);

	ctx=BN_CTX_new();
	if (ctx == NULL) return 1;
	r_mont=BN_new();
	r_mont_const=BN_new();
	r_recp=BN_new();
	r_simple=BN_new();
	a=BN_new();
	b=BN_new();
	m=BN_new();
	out=BIO_new(BIO_s_file());
	if (out == NULL) return 2;
	BIO_set_fp(out,stdout,BIO_NOCLOSE);

//	RAND_bytes(&c,1);
//	c=(c%BN_BITS)-BN_BITS2;
	BN_rand(m,NUM_BITS,0,1);
	BN_MONT_CTX_set(bn_mont_ctx, m, ctx);

	double elapsed = 0.0;
	int ii = EXP_ITERS;
	while (ii--) {
//		RAND_bytes(&c,1);
//		c=(c%BN_BITS)-BN_BITS2;
		BN_rand(a,NUM_BITS,0,0);

//		RAND_bytes(&c,1);
//		c=(c%BN_BITS)-BN_BITS2;
		BN_rand(b,NUM_BITS/2,0,0);

		BN_mod(a,a,m,ctx);
		BN_mod(b,b,m,ctx);

		char* s_a = BN_bn2dec(a);
		char* s_b = BN_bn2dec(b);
		char* s_m = BN_bn2dec(m);

		mpz_t g_a, g_b, g_m, g_r;
		mpz_init_set_str(g_a, s_a, 10);
		mpz_init_set_str(g_b, s_b, 10);
		mpz_init_set_str(g_m, s_m, 10);
		mpz_init(g_r);
		mpz_powm(g_a, g_a, g_b, g_m);

		gettimeofday(&start, NULL);
		BN_mod_exp_mont(r_mont,a,b,m,ctx,bn_mont_ctx);
		gettimeofday(&stop, NULL);
		elapsed += DT;

		char* s_r = BN_bn2dec(r_mont);
		mpz_init_set_str(g_r, s_r, 10);
		if (mpz_cmp(g_r, g_a) != 0)
			gmp_printf("ERROR!!! Results differ between two bignum libraries.\nbn:  %s\ngmp: %Zd\n", s_r, g_a); 
	}
//		mpz_powm(x, x, y, z);
	STATS(EXP_ITERS);

	return 0;
}

