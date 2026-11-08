; Skip copy protection in Emmanuelle.
;
; After the title screen, the game asks for the colour of two boxes on
; the colour chart that came with it. The patch skips the screen
; entirely, the same way as in 20,000 Leagues Under the Sea, which uses
; the same engine.
;
; The screen is a script in INIT.TOT, which EMMA.COM interprets. In
; these scripts, opcode 1Ch is a list of things to do, each either the
; offset of more script (big-endian) or an FFh operation. The list at
; 0x2232 is the copy protection:
;
;     2232 1c 07            do these 7 things:
;     2234 1f 2a              (more script)
;     2236 ff 04 00           (an FFh operation)
;     2239 1b eb              print "Consult the colour chart ..."
;     223b 1d 72              print the box's letter
;     223d 1d 5f              print the box's number
;     223f 09 59              (more script)
;     2241 1e 23              let the player pick a colour
;
; Each colour is a test: opcode 21h compares a variable to the colour,
; and continues with one offset if they're equal, or the other if not:
;
;     1dc3 21 01 00 03 00 00 01 1f 05 01 1f 1d
;
; For the first box, a mismatch leads to the second box (0x1f1d), so a
; match (0x1f05) is the wrong answer. For the second box, a mismatch
; leads to the start of the game (0x1f0d). The patch replaces the text,
; the third thing on the list, with the start of the game, and makes it
; the last thing on the list:
;
;     2232 1c 07                           2232 1c 03
;     ...
;     2239 1b eb                           2239 1f 0d
;
; Unlike in 20,000 Leagues, the game does return to this list, and
; would otherwise show the box's letter and number on the next screen
; and wait for a colour forever.

        org     100h

        mov     ax, 3d01h               ; open for writing
        mov     dx, fname
        int     21h
        mov     bx, ax                  ; file handle
        mov     ax, 4200h               ; seek from the start
        mov     cx, 0
        mov     dx, 2233h
        int     21h
        mov     ah, 40h                 ; write
        mov     cx, 8
        mov     dx, patch
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
        ret

fname:  db      "INIT.TOT", 0
patch:  db      03h, 1fh, 2ah, 0ffh, 04h, 00h, 1fh, 0dh
