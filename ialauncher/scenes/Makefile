CC = owcc
CFLAGS = -bdos -mcmodel=c -march=i386 -Os -s -Wc,-fpi87 \
	-Wall -I$(WATCOM)/h

stars.exe: stars.c
	$(CC) $(CFLAGS) -o $@ $<
	rm -f stars.o

clean:
	rm -f stars.exe stars.o
