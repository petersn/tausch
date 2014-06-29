// Simplest exponentiation test.

#include <gmp.h>
#include <sys/time.h>
#include <stdio.h>

#define EXP_ITERS 500
#define MUL_ITERS 1000000
#define TARGET_MEM_IN_MiB ((float)(1<<15))
#define TARGET_BYTES_PER_SECOND 2048.0
#define MAX_TRADEOFF 21
#define THREADING_BOOST 8.0

#define TARGET_S_PER_ROUND (128.0 / TARGET_BYTES_PER_SECOND)

#define DT ((stop.tv_sec + stop.tv_usec*1e-6) - (start.tv_sec + start.tv_usec*1e-6))
#define STATS(iters) do { \
		printf("Total time: %f\n", DT); \
		printf("Ops:        %i\n", iters); \
		printf("Ops/s:      %f\n", iters / DT); \
	} while (0)


int main(int argc, char** argv) {
	struct timeval start, stop; 
	printf("Benchmarking 2048-bit ** 2048-bit modulo 2048-bit exponentiation.\n");
	mpz_t x, y, z;
	mpz_init_set_ui(x, 7);
	mpz_init_set_ui(y, 3);
	mpz_init_set_ui(z, 5);
	mpz_pow_ui(x, x, 729);
	mpz_pow_ui(y, y, 1292);
	mpz_pow_ui(z, z, 882);
	gettimeofday(&start, NULL);
	int i = EXP_ITERS;
	while (i--)
		mpz_powm(x, x, y, z);
	gettimeofday(&stop, NULL);
	STATS(EXP_ITERS);
	double native_rate = EXP_ITERS / DT;

	printf("Benchmarking 2048-bit * 2048-bit modulo 2048-bit multiplication.\n");
	gettimeofday(&start, NULL);
	i = MUL_ITERS;
	while (i--) {
		mpz_mul(x, x, y);
		mpz_mod(x, x, z);
	}
	gettimeofday(&stop, NULL);
	STATS(MUL_ITERS);

	double rate = MUL_ITERS / DT;
	printf("\n=== Derived statistics:\n");
	printf("Naive resultant exp speed: x%.2f\n", rate / 3072 / native_rate);
	printf("With acceleration tables:\n");
	double total_speed[MAX_TRADEOFF];
	double memory_per_entry[MAX_TRADEOFF];
	for (int i = 1; i < MAX_TRADEOFF; i++) {
		double muls_needed = (2048.0 / i) * (1 - 1.0/(1<<i));
		double mem_expand = (2048.0 / i) * ((1<<i) - 1);
		double mem_mib = (mem_expand * 256.0) / (1<<20);
		printf("  %2i-bit: x%.2f (%.2f MiB/entry)", i, (rate / muls_needed) / native_rate, mem_mib);
		if (i%2 == 0)
			printf("\n");
		total_speed[i] = rate / muls_needed;
		memory_per_entry[i] = mem_mib;
	}

	printf("\n=== Parameter search:\n");
	printf("Assuming:\n");
	printf("  Target data rate: %.1f bytes/s\n", TARGET_BYTES_PER_SECOND);
	printf("  System memory: %.1f MiB\n", TARGET_MEM_IN_MiB);
	printf("  Threading boost: x%.1f\n", THREADING_BOOST);

	int last_tradeoff, users;
	for (users = 1; ; users++) {
		double muls_per_s = users * users / TARGET_S_PER_ROUND;
		bool flag = false;
		for (int i = 1; i < MAX_TRADEOFF; i++) {
			if (total_speed[i]*THREADING_BOOST >= muls_per_s && memory_per_entry[i] * users * users < TARGET_MEM_IN_MiB) {
				flag = true;
				last_tradeoff = i;
			}
		}
		if (not flag)
			break;
	}
	printf("Last workable parameters:\n");
	printf("Users: %i, with %i-bit tables.\n", users-1, last_tradeoff);

	return 0;
}

