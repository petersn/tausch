
CPPFLAGS=-Wall -g -lgmp -ldl -pthread -std=c++0x -I/home/snp/local/openssl-1.0.1h/include

all: cruncher

cruncher: cruncher.o Makefile
	g++ $(CPPFLAGS) -o $@ $<

simple_test: simple_test.o Makefile
	g++ $(CPPFLAGS) -o $@ $<

bn_tester: bn_tester.o Makefile
	g++ $(CPPFLAGS) -o $@ $< ../lib/libcrypto.a

.PHONY: clean
clean:
	rm -f cruncher cruncher.o

