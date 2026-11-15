; Skip copy protection in Quarantine.
;
; Before the title, the game asks for the flesh ratio factor of a
; pedestrian hit by a car, from a table in the manual. SKIPIT.EXE is an
; LE executable; its code object starts at 2a600h in the file. At 24eh
; in that object, the game calls the copy protection and goes on only
; if it returns nonzero:
;
;     024e e8 f1 79 03 00       call    37c44h
;     0253 85 c0                test    eax, eax
;     0255 75 0d                jnz     264h
;
; The patch replaces the call with an instruction of the same length
; that returns 1 without showing the screen:
;
;     024e b8 01 00 00 00       mov     eax, 1

        org     100h

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the call
        mov     cx, (2a600h + 24eh) >> 16
        mov     dx, (2a600h + 24eh) & 0ffffh
        int     21h
        mov     ah, 40h                 ; replace it
        mov     cx, 5
        mov     dx, pass
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

exe:    db      "SKIPIT.EXE", 0
pass:   db      0b8h, 1, 0, 0, 0        ; mov eax, 1
