CC = owcc
CFLAGS = -bdos -mcmodel=c -Wc,-3 -fno-stack-check -Os -s \
	-Wall -I$(WATCOM)/h

stars.exe: stars.c
	$(CC) $(CFLAGS) -o $@ $<
	rm -f stars.o

clean:
	rm -f stars.exe stars.o
