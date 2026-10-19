; Show the answer on the 5th Fleet v1.0 copy protection screen.
;
; The developers left a master password in the game to get past this screen
; themselves. This patch uses the space that password takes up to show the
; answer instead: it keeps the screen but adds the ship's class name after the
; page number. (Page 22) thus becomes (Page 22: Arleigh Burke ), and the
; question answers itself.
;
;
; How the game picks the ship
; ---------------------------
;
; The ship is picked by a routine in the copy protection overlay (file offset
; 0x8a95d). It reads a random record from TRMSRF.DAT, a 2-byte count followed
; by 0x129-byte records:
;
;     0x000  class name, the expected answer  "Arleigh Burke"
;     0x063  picture name in TRM.GXL          "ABURKE"
;     0x127  page in the manual               22
;
; It draws the picture, then fills in "(Page   )". In C, that part reads:
;
;     record = &table->records[index];          // [bp+6], [bp-4]
;     sprintf(buffer, "%d", record->page);      // buffer at [bp-0xa]
;     DrawText(248, 367, buffer, 1, 0, -1);
;
; The game is compiled with Borland C++ for the large memory model, so every
; pointer is a far pointer (segment:offset) and every argument is pushed onto
; the stack from right to left, segment before offset. The caller removes the
; arguments afterwards by adding their size to sp.
;
;
; Original and patched code
; -------------------------
;
;     original                             patched
;
;     8aa6c les  bx, [bp+6]                8aa6c les  bx, [bp+6]
;     8aa6f les  bx, es:[bx+2]             8aa6f les  bx, es:[bx+2]
;     8aa73 mov  ax, [bp-4]           (1)  8aa73 imul ax, [bp-4], 0x129
;     8aa76 imul ax, ax, 0x129
;     8aa7a add  bx, ax                    8aa78 add  bx, ax
;                                     (2)  8aa7a push es
;                                     (2)  8aa7b push bx
;     8aa7c push word es:[bx+0x127]        8aa7c push word es:[bx+0x127]
;     8aa81 push ds                        8aa81 push ds
;     8aa82 push 0x357b               (3)  8aa82 push 0x3596
;     8aa85 push ss                        8aa85 push ss
;     8aa86 lea  ax, [bp-0xa]         (4)  8aa86 lea  ax, [bp-0x22]
;     8aa89 push ax                        8aa89 push ax
;     8aa8a call 0:0x2f9d             (5)  8aa8a call 0:0x2f9d
;     8aa8f add  sp, 0xa              (2)  8aa8f add  sp, 0xe
;     8aa92 push -1                        8aa92 push -1
;     8aa94 push 0                         8aa94 push 0
;     8aa96 push 1                         8aa96 push 1
;     8aa98 push ss                        8aa98 push ss
;     8aa99 lea  ax, [bp-0xa]         (4)  8aa99 lea  ax, [bp-0x22]
;     8aa9c push ax                        8aa9c push ax
;     8aa9d push 0x16f                     8aa9d push 0x16f
;     8aaa0 push 0xf8                      8aaa0 push 0xf8
;     8aaa3 call 0x300:0x372          (5)  8aaa3 call 0x300:0x372
;
; The changes:
;
;     (1) imul has a three-operand form that multiplies a memory operand by
;         an immediate and stores the result in a register. It replaces the
;         mov and the two-operand imul, and is 2 bytes shorter.
;
;     (2) Those 2 bytes make room for push es and push bx, which pass es:bx
;         as an extra sprintf argument. The record starts with the class
;         name, so es:bx is also a far pointer to the name. Pushed first, it
;         is the last argument, matching the %s at the end of the format.
;         sprintf now takes 7 words (14 bytes) of arguments, so the caller
;         removes 0xe bytes instead of 0xa.
;
;     (3) The format string becomes "%d: %s )". There is no room for it next
;         to "%d", so it overwrites the master password JMBMKGMVPDDP at
;         ds:0x3596 (file offset 0x59446), which then no longer works.
;
;     (4) The 4-byte buffer at [bp-0xa] is too small, so the text goes to
;         [bp-0x22], which held "ABURKE.pcx" and is free once the picture is
;         drawn. The longest result, "55: Boris Chilikin )", takes 21 of the
;         28 bytes up to [bp-6], leaving the ship index at [bp-4] alone.
;
;     (5) The far calls stay where they are. The overlay loader fixes up
;         their segments when it loads the code, so moving them would break
;         both calls. The patch therefore rewrites the 30 bytes before the
;         first call and the 20 bytes between the two. Both are padded with
;         nops to exactly their original size, and nasm fails if one grows
;         beyond it.
;
;
; The patcher
; -----------
;
; FLEETFIX.COM opens FLEET.EXE and works through a table of patches, each a
; file offset (low word, then high byte), a length and the bytes to write.
; An entry with a high byte of 0 ends the table; all patches lie above
; 0x10000, so no real entry has one. It uses three DOS functions, called
; through int 21h with the function number in ah:
;
;     3Dh  open the file named at ds:dx for writing (al = 1), returning
;          the handle in ax, or setting the carry flag on error
;     42h  seek handle bx to cx:dx from the start of the file (al = 0)
;     40h  write cx bytes from ds:dx to handle bx
;
; A .COM program can quit with ret: DOS starts it with a 0 on the stack, and
; offset 0 of its segment holds an int 20h, which ends the program. DOS then
; closes the file.

        org     100h

        mov     ax, 3d01h               ; open, write only
        mov     dx, fname
        int     21h
        jc      done
        xchg    bx, ax                  ; bx = file handle
        mov     si, patches
next:   lodsw                           ; ax = offset low word
        xchg    dx, ax
        lodsb                           ; al = offset high byte
        cbw
        xchg    cx, ax
        jcxz    done                    ; end of the table
        mov     ax, 4200h               ; seek from the start
        int     21h
        lodsb                           ; al = length
        mov     cl, al
        mov     ah, 40h                 ; write
        mov     dx, si
        add     si, cx
        int     21h
        jmp     next
done:   ret

patches:
        dw      0aa6ch                  ; offset 0x8aa6c
        db      8, code1.end - code1
code1:  les     bx, [bp+6]
        les     bx, [es:bx+2]
        imul    ax, [bp-4], 0x129       ; (1)
        add     bx, ax
        push    es                      ; (2)
        push    bx                      ; (2)
        push    word [es:bx+0x127]
        push    ds
        push    word 0x3596             ; (3)
        push    ss
        lea     ax, [bp-0x22]           ; (4)
        push    ax
        times   0x1e - ($ - code1) nop  ; (5)
.end:

        dw      0aa8fh                  ; offset 0x8aa8f
        db      8, code2.end - code2
code2:  add     sp, byte 0xe            ; (2)
        push    byte -1
        push    byte 0
        push    byte 1
        push    ss
        lea     ax, [bp-0x22]           ; (4)
        push    ax
        push    word 0x16f
        push    word 0xf8
        times   0x14 - ($ - code2) nop  ; (5)
.end:

        dw      9446h                   ; offset 0x59446
        db      5, format.end - format
format: db      "%d: %s )", 0           ; (3)
.end:

        dw      0                       ; end of the table
        db      0

fname:  db      "FLEET.EXE", 0
