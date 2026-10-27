; Skip copy protection in Bible Builder.
;
; The original floppy had sector 714 damaged on purpose. At startup,
; the game checks that it can't read that sector. The patch makes the
; game skip the check by making the jump past it unconditional:
;
;     original                             patched
;
;     87df call 0x866d                     87df call 0x866d
;     87e2 or ax, ax                       87e2 or ax, ax
;     87e4 jz 0x880a                       87e4 jmp short 0x880a
;
; Only the opcode changes: 0x74 (jz) becomes 0xeb (jmp short).
;
; BB.EXE is packed with EXEPACK, so the offsets above are into the unpacked
; code. EXEPACK left this part of the code as is, so the 0x74 is at offset
; 0x89e4 of BB.EXE, right after the 0x200-byte header.

        org     100h

        mov     ax, 3d01h               ; open for writing
        mov     dx, fname
        int     21h
        mov     bx, ax                  ; file handle
        mov     ax, 4200h               ; seek from the start
        mov     cx, 0
        mov     dx, 89e4h
        int     21h
        mov     ah, 40h                 ; write
        mov     cx, 1
        mov     dx, patch
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
        ret

fname:  db      "BB.EXE", 0
patch:  db      0ebh
