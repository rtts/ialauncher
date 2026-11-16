; Register Heavy Water Jogger
;
; The game stores a number at startup, and compares it with 55c1h to
; decide whether it's registered. Shareware copies have 5208h, which
; shows the ShareWare notice, the registration address, "Print Order
; Form Now?" and a three second delay, and adds a nag during the game.
; This patch stores 55c1h instead, so the game runs as registered.
;
;     original                          patched
;
;     0754 mov  word [206h], 5208h      0754 mov  word [206h], 55c1h
;
; JOGGER.EXE is packed with EXEPACK, which leaves this place as it is,
; after a header of 200h bytes.

        org     100h

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the number
        xor     cx, cx
        mov     dx, 200h + 758h
        int     21h
        mov     ah, 40h                 ; replace it
        mov     cx, 2
        mov     dx, registered
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

exe:    db      "JOGGER.EXE", 0
registered:
        dw      55c1h
