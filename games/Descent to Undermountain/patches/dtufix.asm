; Stop the intro of Descent to Undermountain from stalling in DOSBox Staging.
;
; Fixes https://github.com/dosbox-staging/dosbox-staging/issues/3635
;
; The movie player keeps time with counter 2 of the PIT, the timer chip
; that also drives the PC speaker. The game sets it up once, in mode 2,
; counting down from 65536 at 1.19 MHz and starting over when it reaches
; zero, and keeps it running with the speaker disconnected. After that,
; a callback that runs many times a second (at 105330h) latches the
; count, subtracts it from the previous one, and adds the difference to
; a running total of elapsed ticks. The player waits on that total
; before each frame and each piece of audio.
;
; Before latching, the callback makes sure the counter is still in mode
; 2. It asks the PIT for the counter's status with the read-back command
; and, if the mode is wrong, sends a new mode byte. Then it writes the
; count, 65536, again. In mode 2, writing just the count doesn't disturb
; a countdown in progress, so on the hardware of the time this kept the
; counter running smoothly.
;
; But the read-back command, 0e4h, asks for the status of counter 1, not
; counter 2 (that would be 0e8h). It worked anyway on the hardware it
; was made for, which apparently returned the status from any counter's
; port. DOSBox-X returns it the same way since its fix for this game, but
; DOSBox Staging doesn't latch a status at all, so the game reads a byte
; of the running count instead. That byte passes the check only by
; chance, about once every 64 calls. All other times the game sends the
; mode byte and restarts the countdown, and either way DOSBox Staging
; loses track of the counter. In a test program that runs the callback's
; code in a loop for 3 seconds and compares the total with the BIOS clock,
; the game's clock ran 36% fast. Sending the mode byte every time was
; only right at one speed, and 7 to 11 times too fast at others. Writing
; only the count made it 41 times too fast.
;
; The count never needs to be written again, and the mode doesn't either:
; the game sets both up before it registers the callback, and nothing
; else uses counter 2. So this patch skips straight to latching the
; count, which leaves the counter running undisturbed. The test program's
; clock then stays within 0.04% of the BIOS clock, at 20000, 100000 and
; 300000 cycles alike.
;
;     original                             patched
;
;     105332 in   al, 61h  ; speaker off   105332 in   al, 61h
;     ...                                  ...
;     10533a mov  al, 0e4h ; read-back     10533a jmp  105350h
;     10533c out  43h, al
;     10533e in   al, 42h  ; status
;     105340 and  al, 3fh
;     105342 cmp  al, 34h  ; mode 2?
;     105344 je   10534ah
;     105346 mov  al, 0b4h ; mode 2
;     105348 out  43h, al
;     10534a mov  al, 0    ; count 65536
;     10534c out  42h, al
;     10534e out  42h, al
;     105350 mov  al, 80h  ; latch         105350 mov  al, 80h
;     105352 out  43h, al                  105352 out  43h, al
;
; DTUGAME.EXE is a DOS/4GW executable. The code at 105330h is on its
; 246th page of 4 KB, which starts at file offset 15fe00h, so 10533ah is
; at 16013ah.

        org     100h

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the read-back
        mov     cx, 16h
        mov     dx, 013ah
        int     21h
        mov     ah, 40h                 ; replace it with the jump
        mov     cx, 2
        mov     dx, jump
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

exe:    db      "DTUGAME.EXE", 0
jump:   db      0ebh, 105350h - (10533ah + 2)
