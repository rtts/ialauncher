; Start Altered Destiny without asking whether it was played before.
;
; The game asks "Have you played Altered Destiny before?", with the
; answers "No, I'm yours" and "Yes, skip intro". Replace the move that
; that prepares the question with a jump to where "No, I'm yours" leads,
; so the game plays the intro.

        org     100h

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the question
        mov     cx, 33be7h >> 16
        mov     dx, 33be7h & 0ffffh
        int     21h
        mov     ah, 40h                 ; jump over it
        mov     cx, 2
        mov     dx, jump
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

exe:    db      "\ADESTINY\EXE.EXE", 0
jump:   db      0ebh, 33c45h - (33be7h + 2) ; jmp short to "No, I'm yours"
