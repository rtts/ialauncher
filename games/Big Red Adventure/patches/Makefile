all: introfix.com sbfix.com midifix.com
%.com: %.asm
	nasm -f bin -o $@ $<
clean:
	$(RM) introfix.com sbfix.com midifix.com
