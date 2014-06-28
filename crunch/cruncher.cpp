// === Cruncher ===
// Copyright 2014, Peter Schmidt-Nielsen.
// Licensed under the MIT license.
//
// This program connects to the server, and waits to be issued work.
// The entire purpose is to evaluate the homomorphic matrix multiplication on a (potentially) sparse submatrix.
// The allowed commands from the server to this program are documented:
// In each case, "abc": string literal, I: 8 byte integer, Z: null terminated string hex number.
//   "s" I:subid Z:m -- Add a subscription with the given subscription ID, and the given modulus m.
//   "a" I:subid I:streamid Z:base -- Add an entry to the given subscription corresponding to the given stream ID, with the given base.
//   "d" I:subid -- Remove a given subscription.
//   "c" I:streamid I:round Z:datum -- In the given round, the given stream reads the given datum.
// The following commands return data back to the server:
//   "r" I:round -- Returns: I:numoffields <fields>, with each field being I:subid Z:result.
//   "i" -- Returns some basic information.
//
// The computation is performed by a pool of worker threads.

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <stdint.h>
#include <assert.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netdb.h>
#include <pthread.h>
#include <semaphore.h>
#include <gmp.h>

using namespace std;
#include <iostream>
#include <vector>
#include <map>

// Specifies the maximum number of bytes in a variable length field in a command recieved over the network.
#define READ_BUFFER_LENGTH 65536

typedef uint64_t RoundNum;
typedef uint64_t SubId;
typedef uint64_t StreamId;

struct Subscription;
struct Entry;
struct Computation;

// Global storage.
namespace global {
	int thread_count;
	int bits_per_field;
	int default_tradeoff;
	// Maps subscription number to a subscription.
	map<SubId, Subscription*> subscriptions;
	// Maps a round and subid to a computation object.
	map<RoundNum, map<SubId, Computation*>> computations;

	// Data used for communication between the workers and the main thread.
	StreamId job_stream_id;
	RoundNum job_round_number;
	mpz_t* job_datum;

	// This lock synchronizes reads and writes to subscriptions and computations.
	pthread_rwlock_t globals_rwlock;
	// These semaphores are used to send jobs to worker threads, and signal the main thread that the job data has been read respectively.
	sem_t job_available, job_read_complete; 
}
#define READ_LOCK_GLOBALS pthread_rwlock_rdlock(&global::globals_rwlock)
#define WRITE_LOCK_GLOBALS pthread_rwlock_wrlock(&global::globals_rwlock)
#define UNLOCK_GLOBALS pthread_rwlock_unlock(&global::globals_rwlock)

struct Subscription {
	mpz_t modulus;
	// Maps stream number to an entry.
	map<StreamId, Entry*> entries;

	Subscription(mpz_t _modulus) {
		mpz_init_set(modulus, _modulus);
	}

	~Subscription() {
		mpz_clear(modulus);
		for (auto it = entries.begin(); it != entries.end(); it++) {
			delete it->second;
		}
	}
};

struct Entry {
	mpz_t base;
	int tradeoff;
	int table_length;
	mpz_t* precomputed_table;
	Subscription* parent;

	Entry(Subscription* parent, mpz_t _base) : tradeoff(0), table_length(0), precomputed_table(NULL), parent(parent) {
		mpz_init_set(base, _base);
	}

	~Entry() {
		mpz_clear(base);
		free_table();
	}

	void free_table() {
		if (precomputed_table == NULL)
			return;
		for (int i = 0; i < table_length; i++)
			mpz_clear(precomputed_table[i]);
		tradeoff = 0;
		table_length = 0;
		precomputed_table = NULL;
		delete* precomputed_table;
	}

	inline int get_required_chunks() {
		// The number of required chunks is ceil(bits_per_field / tradeoff)
		return (global::bits_per_field + tradeoff - 1) / tradeoff;
	}

	inline int get_nums_per_chunk() {
		// Each chunk has one number per non-zero bit pattern of up to tradeoff bits.
		return (1 << tradeoff) - 1;
	}

	void rebuild_table(int new_tradeoff) {
		free_table();
		tradeoff = new_tradeoff;
		// A tradeoff value of zero disables the precomputed table mode.
		if (tradeoff == 0)
			return;
		int required_chunks = get_required_chunks();
		int nums_per_chunk = get_nums_per_chunk();
		precomputed_table = new mpz_t[required_chunks * nums_per_chunk];
		mpz_t x, y;
		mpz_init_set(x, base);
		mpz_init(y);
		for (int chunk = 0; chunk < required_chunks; chunk++) {
			mpz_set_ui(y, 1);
			for (int i = 0; i < nums_per_chunk; i++) {
				mpz_mul(y, x, y);
				mpz_mod(y, y, parent->modulus);
				mpz_init_set(precomputed_table[chunk*nums_per_chunk + i], y);
			}
			// Advance x by tradeoff bits.
			mpz_powm_ui(x, x, 1 << tradeoff, parent->modulus);
		}
		mpz_clear(x);
		mpz_clear(y);
	}

	void exponentiate(mpz_t dest, mpz_t datum) {
//		gmp_printf("Exponentiating: %Zd ** %Zd mod %Zd\n", base, datum, parent->modulus);
		// If no table is built, run a vanilla modular exponentiation.
		if (tradeoff == 0) {
			mpz_powm(dest, base, datum, parent->modulus);
			return;
		}
		// Otherwise, let's use our table.
		// A copy of datum, to avoid mutating our input.
		mpz_t _datum;
		mpz_init_set(_datum, datum);
		int required_chunks = get_required_chunks();
		int nums_per_chunk = get_nums_per_chunk();
		int table_index = 0;
		mp_limb_t bit_mask = (1 << tradeoff) - 1;
		mpz_set_ui(dest, 1);
		for (int chunk = 0; chunk < required_chunks; chunk++) {
			// Get the bit pattern for this chunk.
			mp_limb_t bits = mpz_getlimbn(_datum, 0) & bit_mask;
			// Right shift the bits.
			mpz_tdiv_q_2exp(_datum, _datum, tradeoff);
			if (bits != 0) {
				// Multiply in the appropriate table entry.
				// The subtraction of 1 is because we don't need a table entry for the zero bit pattern.
				mpz_mul(dest, dest, precomputed_table[table_index + bits - 1]);
				mpz_mod(dest, dest, parent->modulus);
			}
			table_index += nums_per_chunk;
		}
	}

};

struct Computation {
	Subscription* sub;
	mpz_t* accums;

	Computation(Subscription* sub) : sub(sub) {
		// Allocate one accumulator per thread, so that multiple threads can work on the computation at the same time.
		// In the end, the answer is the product of these accumulators.
		accums = new mpz_t[global::thread_count];
		for (int i = 0; i < global::thread_count; i++)
			mpz_init_set_ui(accums[i], 1);
	}

	~Computation() {
		for (int i = 0; i < global::thread_count; i++)
			mpz_clear(accums[i]);
		delete* accums;
	}

	void process_datum(int thread_index, StreamId stream, mpz_t datum) {
		Entry* entry = sub->entries[stream];
		mpz_t local;
		mpz_init(local);
		entry->exponentiate(local, datum);
//		gmp_printf("Computed additional: %Zd\n", local);
		mpz_mul(accums[thread_index], accums[thread_index], local);
		mpz_mod(accums[thread_index], accums[thread_index], sub->modulus);
		mpz_clear(local);
	}

	void produce_result(mpz_t output) {
		mpz_set_ui(output, 1);
		// Multiply all the thread-specific accumulators together.
		for (int i = 0; i < global::thread_count; i++) {
			mpz_mul(output, output, accums[i]);
			mpz_mod(output, output, sub->modulus);
		}
	}
};

int create_connection(const char* hostname, const char* service) {
	int fd;
	struct addrinfo* res = NULL;
	getaddrinfo(hostname, service, NULL, &res);
	fd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
	if (connect(fd, res->ai_addr, res->ai_addrlen) != 0) {
		freeaddrinfo(res);
		perror(hostname);
		exit(1);
	}
	freeaddrinfo(res);
	return fd;
}

void* process_thread(void* cookie) {
	int thread_index = *(int*)cookie;
	delete (int*)cookie;
	mpz_t datum;
	mpz_init(datum);

	while (1) {
		// Grab a job.
		sem_wait(&global::job_available);
		// Read in the job.
		StreamId stream_id = global::job_stream_id;
		RoundNum round_number = global::job_round_number;
		mpz_set(datum, *global::job_datum);
		// Release the global lock, indicating that the global job data can be mutated, and used to issue another job to a different thread.
		sem_post(&global::job_read_complete);
		// Find each subscription object, and build the computation required.
//		gmp_printf("Performing job: stream=%i round=%i datum=%Zd\n", stream_id, round_number, datum);
		READ_LOCK_GLOBALS;
		for (auto it = global::subscriptions.begin(); it != global::subscriptions.end(); it++) {
			SubId sub_id = it->first;
			Computation* comp = global::computations[round_number][sub_id];
			comp->process_datum(thread_index, stream_id, datum);
		}
		UNLOCK_GLOBALS;
	}

	mpz_clear(datum);
	return NULL;
}

int main(int argc, char** argv) {
	if (argc != 4) {
		fprintf(stderr, "Usage: cruncher <host> <port> <nthreads>\n");
		exit(2);
	}
	int sockfd = create_connection(argv[1], argv[2]);
	printf("Connected.\n");

	assert(sem_init(&global::job_available, 0, 0) == 0);
	assert(sem_init(&global::job_read_complete, 0, 0) == 0);
	assert(pthread_rwlock_init(&global::globals_rwlock, NULL) == 0);

	// Set some reasonable defaults.
	global::bits_per_field = 2048;
	global::default_tradeoff = 0;

	global::thread_count = atoi(argv[3]);
	printf("Using %i threads.\n", global::thread_count);

	// Spawn worker threads.
	vector<pthread_t> threads;
	threads.resize(global::thread_count);
	for (int i=0; i<global::thread_count; i++)
		pthread_create(&threads[i], NULL, process_thread, (void*)new int(i));

	char* buf = new char[READ_BUFFER_LENGTH+1];
	// Make sure the whole buffer is null terminated.
	buf[READ_BUFFER_LENGTH] = 0;
	int buf_i = 0;

	#define READ_FIELD \
		do { \
			buf_i = 0; \
			while (buf_i < READ_BUFFER_LENGTH) { \
				buf[buf_i] = 0; \
				read(sockfd, buf+buf_i, 1); \
				if (buf[buf_i++] == 0) \
					break; \
			} \
		} while (0)

	mpz_t temp_mpz;
	mpz_init(temp_mpz);

	// Wait for commands from the server in an infinite loop.
	while (1) {
		char type = -1;
		if (read(sockfd, &type, 1) != 1)
			break;
		SubId sub_id = 0;
		StreamId stream_id = 0;
		RoundNum round_number = 0;
		#define FILL(x) read(sockfd, &x, sizeof x)
		switch (type) {
			case 's':
				// Add a subscription.
				FILL(sub_id);
				READ_FIELD; // Read in the modulus.
				mpz_set_str(temp_mpz, buf, 16);
//				gmp_printf("Adding subscription: sub=%i mod=%Zd\n", sub_id, temp_mpz);
				// Create the subscription.
				WRITE_LOCK_GLOBALS;
				global::subscriptions[sub_id] = new Subscription(temp_mpz);
				UNLOCK_GLOBALS;
				break;
			case 'a':
				// Add a new entry into a subscription.
				FILL(sub_id);
				FILL(stream_id);
				READ_FIELD; // Read in the base.
				mpz_set_str(temp_mpz, buf, 16);
//				gmp_printf("Adding entry: sub=%i stream=%i base=%Zd\n", sub_id, stream_id, temp_mpz);
				WRITE_LOCK_GLOBALS;
				// Make sure the sub_id is real.
				if (global::subscriptions.count(sub_id) == 1) {
					Subscription* sub = global::subscriptions[sub_id];
					// Delete a previous entry, if it exists.
					if (sub->entries.count(stream_id) == 1)
						delete sub->entries[stream_id];
					Entry* entry = sub->entries[stream_id] = new Entry(sub, temp_mpz);
					// TODO: Rebuilding the table is expensive!
					// Eventually, move this to a worker thread.
					entry->rebuild_table(global::default_tradeoff);
				}
				UNLOCK_GLOBALS;
				break;
			case 'd':
				// Remove a subscription.
				FILL(sub_id);
				WRITE_LOCK_GLOBALS;
				if (global::subscriptions.count(sub_id) == 1) {
					delete global::subscriptions[sub_id];
					global::subscriptions.erase(global::subscriptions.find(sub_id));
				}
				UNLOCK_GLOBALS;
				break;
			case 'c': {
				// Issue a computation.
				FILL(stream_id);
				FILL(round_number);
				READ_FIELD; // Read in the datum.
				mpz_set_str(temp_mpz, buf, 16);
//				gmp_printf("Computation: stream=%i round=%i datum=%Zd\n", stream_id, round_number, temp_mpz);
				// Create any new computation objects required.
				WRITE_LOCK_GLOBALS;
				map<SubId, Computation*>& comps = global::computations[round_number];
				for (auto it = global::subscriptions.begin(); it != global::subscriptions.end(); it++) {
					// Create a computation object for this subscription in this round number.
					if (comps.count(it->first) == 0)
						comps[it->first] = new Computation(it->second);
				}
				UNLOCK_GLOBALS;

				// Fill up the global job description.
				global::job_stream_id = stream_id;
				global::job_round_number = round_number;
				global::job_datum = &temp_mpz;
				sem_post(&global::job_available);
				sem_wait(&global::job_read_complete);
				break;
			}
			case 'r': {
				// Read out completed answers.
				FILL(round_number);
//				gmp_printf("Replying: round=%lu\n", round_number);
				WRITE_LOCK_GLOBALS;
				map<SubId, Computation*>& comps = global::computations[round_number];
				uint64_t field = comps.size();
//				gmp_printf("Lengths: %i %i\n", global::computations.size(), comps.size());
				write(sockfd, &field, 8);
				for (auto it = comps.begin(); it != comps.end(); it++) {
					field = it->first;
					write(sockfd, &field, 8);
					it->second->produce_result(temp_mpz);
					int bytes = gmp_snprintf(buf, READ_BUFFER_LENGTH, "%Zx", temp_mpz);
					assert(bytes < READ_BUFFER_LENGTH);
					write(sockfd, buf, bytes+1);
				}
				UNLOCK_GLOBALS;
				break;
			}
			case 'i':
				// Return status information.
				write(sockfd, "Status.\n", 8);
				break;
			default:
				fprintf(stderr, "Got invalid command character: %i\n", type);
				assert(0);
		}
	}

	printf("Exiting.\n");
	close(sockfd);
	return 0;
}

