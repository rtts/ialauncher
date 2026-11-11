; Stop the Big Red Adventure MIDI driver from dividing by zero.
;
; SBMIDI.EXE reads a song's tempo and ticks per beat from its header,
; and sets the timer to tempo * ticks / 60 interrupts a second. But the
; header of five songs is off by one byte, such as POTIOMKY.MSC for the
; Odessa steps, and their ticks read as 0xc000 instead of 0xc0. The
; driver multiplies with only 16 bits, 140 * 0xc000 = 0x690000 becomes
; 0, and setting the timer to 0 interrupts a second fails with "Runtime
; error 200", a division by zero.
;
; ADLIBMSC.EXE replaces ticks over 255 with 0xc0, which all other songs
; use. This patch has the same effect, by never storing the header's
; ticks, so they stay 0xc0 from when the driver started.
;
;     original                             patched
;
;     05a6 call 0xe4d   ; read ticks       05a6 call 0xe4d
;     05a9 mov  [0x74], ax                 05a9 nop
;                                          05aa nop
;                                          05ab nop
;     05ac call 0xe04                      05ac call 0xe04
;
; The addresses are those of the code in SBMIDI.EXE, which starts at
; 0x120 in the file.

        org     100h

        mov     ax, 3d01h               ; open for writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the store
        xor     cx, cx
        mov     dx, 120h + 5a9h
        int     21h
        mov     ah, 40h                 ; replace it
        mov     cx, 3
        mov     dx, nops
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

exe:    db      "SBMIDI.EXE", 0
nops:   db      90h, 90h, 90h
