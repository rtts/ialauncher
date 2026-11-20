CC = owcc
CFLAGS = -bdos -mcmodel=c -Wc,-3 -fno-stack-check -Os -s \
	-Wall -I$(WATCOM)/h

stars.exe: stars.c sonata.txt sonata.awk
	awk -f sonata.awk sonata.txt > sonata.h
	$(CC) $(CFLAGS) -o $@ $<
	rm -f stars.o sonata.h

clean:
	rm -f stars.exe stars.o sonata.h
