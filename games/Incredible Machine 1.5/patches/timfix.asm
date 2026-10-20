; Skip copy protection in The Even More! Incredible Machine.
;
; Before the first puzzle, the game asks for three parts listed on a random
; page of the manual. The screen is a function that only returns once the
; right parts are clicked. The patch makes the call to it land on the retf
; of the function just before it, so it returns at once:
;
;     original                             patched
;
;     f945 push cs                         f945 push cs
;     f946 call 0xf9e2                     f946 call 0xf9e1
;     ...                                  ...
;     f9e1 retf                            f9e1 retf
;     f9e2 push bp                         f9e2 push bp
;
; The call's target is stored relative to the next instruction, so only one
; byte changes: 0x99 (0xf9e2 - 0xf949) becomes 0x98.
;
; TIM.EXE is packed with LZEXE, so the offsets above are into the unpacked
; code. Luckily, LZEXE stored the 0x99 as is, at offset 0x913a of TIM.EXE,
; and nothing later in the file repeats it, so changing it there changes
; just that one byte of the unpacked code.

        org     100h

        mov     ax, 3d01h               ; open for writing
        mov     dx, fname
        int     21h
        mov     bx, ax                  ; file handle
        mov     ax, 4200h               ; seek from the start
        mov     cx, 0
        mov     dx, 913ah
        int     21h
        mov     ah, 40h                 ; write
        mov     cx, 1
        mov     dx, patch
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
        ret

fname:  db      "TIM.EXE", 0
patch:  db      98h
