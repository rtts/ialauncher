export INCLUDE := $(WATCOM)/h
export PATH := $(PATH):$(WATCOM)/binl

pickflag.exe: pickflag.c
	wcl -q -bt=dos -ms -s -zu -ox -k512 -fe=$@ $<
	$(RM) pickflag.o
clean:
	$(RM) pickflag.exe
