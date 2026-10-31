export INCLUDE := $(WATCOM)/h
export PATH := $(PATH):$(WATCOM)/binw

intro.exe: intro.c
	wcl386 -q -bt=dos -l=dos4g -ox -fe=$@ $<
	$(RM) intro.o
clean:
	$(RM) intro.exe
