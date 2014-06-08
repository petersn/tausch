// Cruncher.

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
#include <gmp.h>

using namespace std;
#include <vector>
#include <map>

struct Computation;

struct Subscription {
	mpz_t modulus;
	// Maps stream number to a base.
	map<uint64_t, mpz_t> bases;
};

struct Computation {
	Subscription* sub;
	mpz_t accum;

	computation_t(Subscription* sub) : sub(sub) {
		mpz_init_set_ui(accum, 1);
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

// Global storage.
pthread_mutex_t global_lock;
#define LOCK pthread_mutex_lock(&global_lock)
#define UNLOCK pthread_mutex_unlock(&global_lock)

// Maps subscription number to a subscription.
map<uint64_t, subscription_t*> subscriptions;

void* process_thread(void* cookie) {
	int pid = *(int*)cookie;
	delete (int*)cookie;

	// Grab the global lock.
	while (1) {
		LOCK;

	}

	return NULL;
}

int main(int argc, char** argv) {
	if (argc != 4) {
		fprintf(stderr, "Usage: cruncher <host> <port> <nthreads>\n");
		exit(2);
	}
	int sockfd = create_connection(argv[1], argv[2]);
	printf("Connected.\n");

	// Initialize the global lock and grab it.
	assert(pthread_mutex_init(&global_lock, NULL) == 0);
	LOCK;

	// Spawn worker threads.
	vector<pthread_t> threads;
	threads.resize(atoi(argv[2]));
	for (unsigned int i=0; i<threads.size(); i++)
		pthread_create(&threads[i], NULL, process_thread, (void*)new int(i));

	#define READ_BUFFER_LENGTH 65536
	char* buf = new char[READ_BUFFER_LENGTH+1];
	// Make sure the whole buffer is null terminated.
	buf[READ_BUFFER_LENGTH] = 0;
	int buf_i = 0;

	#define READ_FIELD \
	do { \
		buf_i = 0; \
		while (buf_i < READ_BUFFER_LENGTH) { \
			buf[buf_i] = 0;
			read(sockfd, buf+buf_i, 1); \
			if (buf[buf_i++] == 0) \
				break; \
			buf_i++; \
		} \
	} while (0)

	mpz_t temp_mpz;
	mpz_init(temp_mpz);

	// Wait for commands from the server.
	while (1) {
		char type;
		read(sockfd, &type, 1);
		uint64_t sub_id = 0;
		uint64_t stream_id = 0;
		uint64_t round_number = 0;
		#define FILL(x) read(sockfd, &x, sizeof x)
		switch (type) {
			case 's':
				// Add/update a subscription.
				FILL(sub_id);
				READ_FIELD; // Read in the modulus.
				mpz_set_str(temp_mpz, buf, 16);
				
			case 'a':
				// Add a new entry into a subscription.
				FILL(sub_id);
				FILL(stream_id);
				READ_FIELD; // Read in the base.
				mpz_set_str(temp_mpz, buf, 16);
				break;
			case 'b':
				// Remove a subscription pair.
				FILL(sub_id);
				break;
			case 'c':
				// Issue a computation.
				FILL(stream_id);
				FILL(round_number);
				break;
			case 'r':
				// Read out an answer.
				FILL(sub_id);
				FILL(round_number);
				break;
			case 'i':
				// Return status information.
				break;
			default:
				assert(0);
		}
	}

	return 0;
}

