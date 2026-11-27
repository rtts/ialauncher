; Play Tandy sound in Maniac Mansion.
;
; Every sound has a PC speaker part and a Tandy part, and the game has
; a player for each. Which one it uses depends on the word at [1c52h],
; which is only set when the BIOS says the machine is a Tandy 1000:
;
;     551:  mov     bx, 0ffffh
;     554:  mov     es, bx
;     556:  mov     bx, 0eh
;     559:  cmp     byte [es:bx], 0ffh      ; model byte of a PC?
;     55d:  jnz     57fh
;     55f:  mov     bx, 0fc00h
;     562:  mov     es, bx
;     564:  sub     bx, bx
;     566:  cmp     byte [es:bx], 21h       ; Tandy signature?
;     56a:  jnz     57fh
;     56c:  mov     byte [0e3d3h], 15h      ; Tandy graphics
;     571:  mov     al, 1
;     573:  mov     [17beh], al
;     576:  mov     [0de49h], al
;     579:  mov     word [1c52h], 1         ; Tandy sound
;     57f:  ...
;
; The patch replaces the check with just the last line, so the game keeps
; its EGA or VGA graphics and plays sound through the Tandy chip, which
; DOSBox provides with "tandy on". The code starts at file offset 200h.

        org     100h

offset  equ     200h + 551h

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the check
        mov     cx, offset >> 16
        mov     dx, offset & 0ffffh
        int     21h
        mov     ah, 40h                 ; replace it
        mov     cx, patch.end - patch
        mov     dx, patch
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

exe:    db      "MANIAC.EXE", 0
patch:  mov     word [1c52h], 1         ; Tandy sound
        jmp     short patch + 57fh - 551h
.end:
