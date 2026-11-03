; Skip copy protection in 20,000 Leagues Under the Sea.
;
; After the title screen, the game asks for the colour of two boxes on
; the colour chart that came with it. This copy was already cracked: all
; colours count as the right one. The patch skips the screen entirely.
;
; The screen is a script in BOADER0.TOT, which LOADER.COM interprets. In
; these scripts, opcode 1Ch is a list of things to do, each either the
; offset of more script (big-endian) or an FFh operation. The list at
; 0x634 is the copy protection:
;
;     0634 1c 06            do these 6 things:
;     0636 03 31              (more script)
;     0638 ff 04 00           (an FFh operation)
;     063b 00 10              print "Consult the colour chart ..."
;     063d 01 79              print the box's letter
;     063f 01 6b              print the box's number
;     0641 02 3a              let the player pick a colour
;
; Picking a colour leads to the second box (0x324), and picking a colour
; there leads to the start of the game (0xa6c). The patch replaces the
; text, the third thing on the list, with the start of the game:
;
;     063b 00 10                           063b 0a 6c
;
; The game never returns to this list, so the rest of it doesn't run.

        org     100h

        mov     ax, 3d01h               ; open for writing
        mov     dx, fname
        int     21h
        mov     bx, ax                  ; file handle
        mov     ax, 4200h               ; seek from the start
        mov     cx, 0
        mov     dx, 63bh
        int     21h
        mov     ah, 40h                 ; write
        mov     cx, 2
        mov     dx, patch
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
        ret

fname:  db      "BOADER0.TOT", 0
patch:  db      0ah, 6ch
