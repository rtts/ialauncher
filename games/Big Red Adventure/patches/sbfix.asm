; Stop the Big Red Adventure sound driver from playing garbage.
;
; SBEFF.EXE plays every effect with a single 8-bit DMA transfer on
; channel 1. The game passes it the effect's address in conventional
; memory, and the driver splits that 20-bit address into the page
; register (port 83h), which holds the top 4 bits, and the channel's
; 16-bit address register (port 2), which holds the rest. During the
; transfer the DMA controller only increments the 16-bit address; the
; page register stays the same. So when an effect crosses a 64 KB
; boundary, the address wraps from ffffh to 0 in the same page, and
; the rest of the effect is read from the start of that 64 KB instead
; of the next one.
;
; What plays from there is whatever the start of that 64 KB happens to
; hold: first some older speech that was loaded there, then other data,
; which sounds like noise. It lasts for the rest of the effect's length,
; up to about a second for the longer speech in the intro, and then the
; game continues as if the effect played correctly. Real hardware wraps
; the same way. Whether an effect crosses a boundary depends only on
; where the game's buffers end up in conventional memory. In DOSBox,
; whose DOS uses almost no conventional memory, some of the intro's
; speech does, whatever the memsize, cycles or core. On the computers
; of the time, with DOS and its drivers loaded low, they probably landed
; elsewhere.
;
; Drivers usually avoid this by allocating a DMA buffer that doesn't
; cross a boundary, or by splitting the transfer. This patch adds the
; latter to a copy of SBEFF.EXE: starting an effect now only programs
; the transfer up to the next 64 KB boundary, and remembers the rest.
; When that part ends and the Sound Blaster raises its interrupt, the
; handler plays the rest before doing anything else, from the start of
; the next 64 KB, so the effect continues where it left off.
;
;     original                             patched
;
;     0279 mov  al, 5   ; start DMA        0279 jmp  play
;     ...                                  ...
;     02ec or   byte [0x20], 0 ; looping?  02ec jmp  ended
;     02f1 jz   0x2fa                      02f1 jz   0x2fa
;     ...                                  ...
;     0323 pop  ds      ; return           0323 pop  ds
;
; The added code goes after the driver's stack, at 0xc60, which is
; still part of the memory that the driver keeps when it stays
; resident, up to 0x11c0.

        org     100h

        mov     ax, 3d01h               ; open for writing
        mov     dx, fname
        int     21h
        jc      done
        mov     bx, ax                  ; file handle
        mov     dx, 2
        mov     si, header
        mov     cx, 4
        call    write
        mov     dx, 200h + 279h
        mov     si, jplay
        mov     cx, 3
        call    write
        mov     dx, 200h + 2ech
        mov     si, jended
        mov     cx, 3
        call    write
        mov     dx, 200h + 0c60h
        mov     si, section.added.start
        mov     cx, added_end - play
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

size    equ     200h + 0c60h + (added_end - play)
fname:  db      "SBEFF.EXE", 0
header: dw      size % 200h             ; bytes in the last page
        dw      (size + 1ffh) / 200h    ; pages
jplay:  db      0e9h
        dw      play - (279h + 3)
jended: db      0e9h
        dw      ended - (2ech + 3)

section added follows=.text vstart=0c60h

play:   xor     bx, bx                  ; the effect's address and length
        mov     bl, [24h]
        dec     bx
        shl     bx, 2
        mov     eax, [bx+136h]
        shr     bx, 1
        movzx   ecx, word [bx+0f6h]
        jmp     part

ended:  cmp     word [cs:rest], 0       ; is there a rest to play?
        jne     .rest
        or      byte [20h], 0
        jmp     0x2f1
.rest:  mov     eax, [cs:next]
        movzx   ecx, word [cs:rest]
        call    part
        jmp     0x323

part:   mov     edx, eax                ; play up to the 64 KB boundary
        and     edx, 0ffffh
        neg     edx
        add     edx, 10000h
        mov     word [cs:rest], 0
        cmp     ecx, edx
        jbe     .dma
        sub     ecx, edx
        mov     [cs:rest], cx
        lea     ebx, [eax+edx]
        mov     [cs:next], ebx
        mov     ecx, edx
.dma:   mov     ebx, eax
        mov     al, 5                   ; mask channel 1
        out     0ah, al
        xor     al, al                  ; clear the flip-flop
        out     0ch, al
        mov     al, 49h                 ; single transfer, read, channel 1
        out     0bh, al
        mov     al, bl                  ; address
        out     2, al
        mov     al, bh
        out     2, al
        shr     ebx, 16                 ; page
        mov     al, bl
        out     83h, al
        dec     cx                      ; count
        mov     al, cl
        out     3, al
        mov     al, ch
        out     3, al
        mov     al, 1                   ; unmask channel 1
        out     0ah, al
        mov     al, 14h                 ; 8-bit single-cycle output
        call    0x21f
        mov     al, cl
        call    0x21f
        mov     al, ch
        call    0x21f
        ret

next:   dd      0
rest:   dw      0
added_end:
