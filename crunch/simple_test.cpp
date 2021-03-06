// Simplest exponentiation test.

#include <gmp.h>
#include <sys/time.h>
#include <stdio.h>

#define EXP_ITERS 100
#define MUL_ITERS 200000
#define INV_ITERS 100

#define SERVER_COUNT 2000.0
#define TARGET_MEM_IN_MiB (((float)(1<<15))*SERVER_COUNT)
#define TARGET_BYTES_PER_SECOND 1000.0
#define MAX_TRADEOFF 21
#define THREADING_BOOST (8.0*SERVER_COUNT)

#define TARGET_S_PER_ROUND (128.0 / TARGET_BYTES_PER_SECOND)

#define DT ((stop.tv_sec + stop.tv_usec*1e-6) - (start.tv_sec + start.tv_usec*1e-6))
#define STATS(iters) do { \
		printf("Total time: %f\n", DT); \
		printf("Ops:        %i\n", iters); \
		printf("Ops/s:      %f\n", iters / DT); \
	} while (0)

int main(int argc, char** argv) {
	struct timeval start, stop; 
	printf("Benchmarking 2048-bit ** 1024-bit modulo 2048-bit exponentiation.\n");
	mpz_t x, y, z, w;
	mpz_init_set_ui(x, 7);
	mpz_init_set_ui(y, 3);
	mpz_init_set_ui(z, 5);
	mpz_init_set_ui(w, 11);
	mpz_pow_ui(x, x, 729); // 2048 bit
	mpz_pow_ui(y, y, 646); // 1024 bit
	mpz_pow_ui(z, z, 882); // 2048 bit
	mpz_pow_ui(w, w, 592); // 2048 bit
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
		mpz_mul(x, x, w);
		mpz_mod(x, x, z);
	}
	gettimeofday(&stop, NULL);
	STATS(MUL_ITERS);

	printf("Benchmarking 2048-bit modulo 2048-bit modular inversion.\n");
	gettimeofday(&start, NULL);
	i = INV_ITERS;
	while (i--)
		mpz_invert(x, w, z);
	gettimeofday(&stop, NULL);
	STATS(INV_ITERS);

	double rate = MUL_ITERS / DT;
	printf("\n=== Derived statistics:\n");
	printf("Naive resultant exp speed: x%.2f\n", rate / 1536 / native_rate);
	printf("With acceleration tables:\n");
	double total_speed[MAX_TRADEOFF];
	double memory_per_entry[MAX_TRADEOFF];
	for (int i = 1; i < MAX_TRADEOFF; i++) {
		double muls_needed = (1024.0 / i) * (1 - 1.0/(1<<i));
		double mem_expand = (1024.0 / i) * ((1<<i) - 1);
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
	users--;
	printf("Last workable parameters:\n");
	printf("Users: %i, with %i-bit tables.\n", users, last_tradeoff);
	printf("Total effective bandwidth: %.2f MiB/s\n", (users*users*TARGET_BYTES_PER_SECOND) / (float)(1<<20));
	printf("Per user effective bandwidth: %.2f MiB/s\n", (users*TARGET_BYTES_PER_SECOND) / (float)(1<<20));

	return 0;
}

