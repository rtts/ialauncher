; Start The Big Red Adventure's intro without the title screen.
;
; The publisher logos now end by jumping to SEE INTRO. When the intro
; ends, the title screen works as usual. The menu now shows the mouse
; cursor instead of hiding it, because the skipped title screen didn't
; show it.
;
;     original                             patched
;
;     1369b mov  [0x318d4], 0 ; logos done 1369b mov  [0x318d4], 0
;     136a5 mov  eax, 0x33c14              136a5 mov  eax, 0x33c14
;     136aa call 0x2289f      ; black      136aa jmp  0x139b8
;     ...                                  ...
;     139b8 mov  edi, 0x31932 ; SEE INTRO  139b8 mov  edi, 0x31932
;     ...                                  ...
;     13b61 call 0x27709      ; hide mouse 13b61 call 0x276ff ; show mouse
;
; The addresses are those of the 32-bit code in ADV.EXE, whose first
; page starts at 0xae00 in the file, at address 0x10000. The patch
; avoids the relocated addresses at 0x136a6, 0x136b2 and 0x13b67, which
; DOS/4GW would overwrite.

        org     100h

        mov     ax, 3d01h               ; open for writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax                  ; file handle
        mov     dx, 0ae00h + 136aah - 10000h
        mov     si, jump
        mov     cx, 5
        call    write
        mov     dx, 0ae00h + 13b62h - 10000h
        mov     si, show
        mov     cx, 1
        call    write
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

write:  push    cx                      ; write cx bytes from si at offset dx
        mov     ax, 4200h               ; seek from the start
        xor     cx, cx
        int     21h
        pop     cx
        mov     ah, 40h                 ; write
        mov     dx, si
        int     21h
        ret

exe:    db      "ADV.EXE", 0
jump:   db      0e9h                    ; jmp near to SEE INTRO
        dd      139b8h - (136aah + 5)
show:   db      (276ffh - (13b61h + 5)) & 0ffh ; call 0x276ff
