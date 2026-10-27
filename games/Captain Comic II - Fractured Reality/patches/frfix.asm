; Skip copy protection in Captain Comic II: Fractured Reality.
;
; The first time the game runs on a computer, it asks for the code in a
; random cell of the table in the manual, and saves it in FR.CFG along with
; checksums of the BIOS that identify the computer. The game checks the code
; again later, so instead of skipping the question, the patch skips the screen
; and answers it with the code the game expects:
;
;     original                             patched
;
;     6e19 call 0x6f47  ; draw screen      6e19 jmp short 0x6e25
;     6e1c call 0x774e                     6e1b ...
;     6e1f call 0x6f47
;     6e22 call 0x7057  ; read code
;     6e25 mov ax, [0xabb1]                6e25 mov ax, [0xabb1]
;     ...                                  ...
;     6e4c mov si, 0xabb5 ; typed code     6e4c mov ax, [0xabbb]
;     6e4f mov dx, [0xabbb] ; expected     6e4f jmp short 0x6e71
;     6e53 xor ax, ax                      6e51 ...
;     6e55 ...          ; parse into ax
;     6e71 mov [0x9cf8], ax                6e71 mov [0x9cf8], ax
;
; FR.EXE is packed with EXEPACK, so the offsets above are into the unpacked
; code. EXEPACK left both parts of the code as is, at offsets 0x6f44 and
; 0x6f77 of FR.EXE.

        org     100h

        mov     ax, 3d01h               ; open for writing
        mov     dx, fname
        int     21h
        mov     bx, ax                  ; file handle
        mov     dx, 6f44h
        mov     si, skip
        mov     cx, 2
        call    write
        mov     dx, 6f77h
        mov     si, answer
        mov     cx, 5
        call    write
        mov     ah, 3eh                 ; close
        int     21h
        ret

write:  push    cx                      ; write cx bytes from si at offset dx
        mov     ax, 4200h               ; seek from the start
        xor     cx, cx
        int     21h
        pop     cx
        mov     ah, 40h                 ; write
        mov     dx, si
        int     21h
        ret

fname:  db      "FR.EXE", 0
skip:   jmp     short $+0ch             ; 0x6e19 -> 0x6e25
answer: mov     ax, [0abbbh]
        jmp     short $+22h             ; 0x6e4f -> 0x6e71
