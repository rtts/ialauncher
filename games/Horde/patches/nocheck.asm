; Skip the copy protection screen in The Horde.
;
; The game, even with the shipped crack, requires two clicks on the
; compass. The function that shows it makes sure a shared resource is
; loaded, then loads the screen, runs the check, frees the screen, and
; finally switches to the next state:
;
;     2ff0f:  cmp     dword [8e60h], 0        ; shared resource loaded?
;     ...
;     2ff27:  mov     [8e60h], eax
;     2ff2c:  mov     eax, 9610301h           ; load the screen
;     ...
;     2ffce:  call    2fb98h                  ; the check itself
;     ...
;     3000c:  mov     eax, 4                  ; next state
;     30011:  call    3985ch
;
; Jump from 2ff2c straight to 3000c, so the resource still gets loaded
; and the game still moves on. The code object starts at file offset
; 35414h.

        org     100h

offset  equ     35414h + 2ff2ch - 10000h

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the screen
        mov     cx, offset >> 16
        mov     dx, offset & 0ffffh
        int     21h
        mov     ah, 40h                 ; jump over it
        mov     cx, 5
        mov     dx, jump
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

exe:    db      "HORDE.EXE", 0
jump:   db      0e9h
        dd      3000ch - (2ff2ch + 5)   ; jmp near to the next state
