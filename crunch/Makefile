
CPPFLAGS=-Wall -g -lgmp -pthread -std=c++0x

all: cruncher

cruncher: cruncher.o Makefile
	g++ $(CPPFLAGS) -o $@ $<

simple_test: simple_test.o Makefile
	g++ $(CPPFLAGS) -o $@ $<

.PHONY: clean
clean:
	rm -f cruncher cruncher.o

