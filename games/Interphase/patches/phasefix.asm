; Skip the copy protection in Interphase, keeping the sound.
;
; The archive comes with the original INTERPHS.EXE, renamed to
; interphs.ex_, which exits right away, and a cracked INTERPHS.EXE. The
; crack replaces the jz after loading the sound samples with a jump past
; the copy protection, which also skips the setup in between:
;
;     3a1b:  cmp     byte [2706h], 0         ; AdLib?
;     3a20:  jz      3a48h                   ; crack: jmp 4288h
;     3a22:  ...                             ; convert the AdLib samples
;     3a48:  xor     ax, ax                  ; reset the mouse
;     3a4a:  int     33h
;     3a4c:  ...
;     3a52:  call    7c53h                   ; timer handler, plays samples
;     3a55:  call    7baah                   ; keyboard handler
;     3a58:  ...
;     3a72:  push    ds                      ; the copy protection
;     ...
;     4288:  call    7df6h                   ; the game
;
; So the cracked game has no sound and no keyboard handler. This patch
; leaves the setup alone and jumps from 3a72 to 4288 instead. The code
; starts at file offset 200h.

        org     100h

offset  equ     200h + 3a72h

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the copy protection
        mov     cx, offset >> 16
        mov     dx, offset & 0ffffh
        int     21h
        mov     ah, 40h                 ; jump over it
        mov     cx, 3
        mov     dx, jump
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

exe:    db      "INTERPHS.EXE", 0
jump:   db      0e9h
        dw      4288h - (3a72h + 3)     ; jmp near to the game
