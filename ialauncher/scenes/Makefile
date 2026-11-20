CC = owcc
CFLAGS = -bdos -mcmodel=c -Wc,-3 -fno-stack-check -Os -s \
	-Wall -I$(WATCOM)/h

stars.exe: stars.c sonata.txt sonata.awk
	awk -f sonata.awk sonata.txt | sort -n -k1,1 -k2,2 | \
		awk -v table=1 -f sonata.awk > sonata.h
	$(CC) $(CFLAGS) -o $@ $<
	rm -f stars.o sonata.h

clean:
	rm -f stars.exe stars.o sonata.h
