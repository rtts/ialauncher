export INCLUDE := $(WATCOM)/h
export PATH := $(PATH):$(WATCOM)/binl

intro.exe: intro.c
	wcl -q -bt=dos -ms -ox -fe=$@ $<
	$(RM) intro.o
clean:
	$(RM) intro.exe
