; Start Inca 2 without displaying the menu first.
;
; INTRO.TOT ends by loading MENU.TOT, which shows the DEMO and GAME
; menu, waits for a click, and ignores the keyboard. The menu loop calls
; the routine at 5D9Fh that waits for the click, and then switches on
; the result. Clicking GAME runs the block at 6411h, which sets the
; first scene to INCAN010 and ends the loop. So nomenu changes that
; call to call 6411h instead, and the game continues as if GAME was
; clicked.
;
; MENU.TOT is compressed inside INTRO.STK, but the two bytes of the
; call's offset are stored as literals, and nothing else refers to them.

        org     100h

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, stk
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the call's offset
        mov     cx, 71074h >> 16
        mov     dx, 71074h & 0ffffh
        int     21h
        mov     ah, 40h                 ; replace it
        mov     cx, 2
        mov     dx, offset
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

stk:    db      "INTRO.STK", 0
offset: dw      6411h
