
CPPFLAGS=-Wall -O3 -g -lgmp -pthread -std=c++0x

all: cruncher

cruncher: cruncher.o Makefile
	g++ $(CPPFLAGS) -o $@ $<

.PHONY: clean
clean:
	rm -f cruncher cruncher.o

