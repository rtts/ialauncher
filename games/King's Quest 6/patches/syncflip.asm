; Fix glitchy opening movie in King's Quest 6.
;
; Sierra had a habit: every new piece of technology debuted in King's
; Quest first. King's Quest 1 introduced AGI and its animated pseudo-3D
; screens, King's Quest 4 introduced SCI, King's Quest 5 brought VGA and
; the point-and-click icon bar, and King's Quest 6 opened with a fully
; rendered intro, streamed from CD as .SEQ movies. The rest of the
; catalog would get the polished version of whatever King's Quest had
; pioneered a year or so later.
;
; To play those movies, VGA320.DRV switches the VGA card into Mode X,
; the unchained 256-color mode that has room for several pages of
; 320x200 pixels. The game draws the next frame into a hidden page and
; then asks the driver to flip it into view. Function 15 of the driver
; does the flip by writing the new display start address into two CRTC
; registers:
;
;     1bea:  push    dx
;            push    ax
;            mov     dx, 3d4h
;            mov     al, 0ch                 ; start address, high byte
;            out     dx, al
;            mov     dx, 3d5h
;            mov     al, bh
;            out     dx, al
;            mov     dx, 3d4h
;            mov     al, 0dh                 ; start address, low byte
;            out     dx, al
;            mov     dx, 3d5h
;            mov     al, bl
;            out     dx, al
;            pop     ax
;            pop     dx
;            ret
;
; Whenever it feels like it. The VGA card only picks up the start address
; once per frame, at the start of vertical retrace. If that moment falls
; between the two writes, the card displays from half an old address and
; half a new one, which is to say from somewhere random. And when the
; function returns, the old page is still on screen until the next
; retrace, but the game already thinks it's hidden and starts drawing the
; next frame right into it. Behold: King Graham's family, shredded.
;
; By the time Leisure Suit Larry 6 came out a year later, Sierra had
; fixed it. Larry's VGA320.DRV waits for the start of vertical retrace
; before writing the start address, and again afterwards:
;
;     1e95:  push    dx
;            push    ax
;            mov     dx, 3dah                ; input status
;     1e9a:  in      al, dx
;            and     al, 8                   ; in vertical retrace?
;            jnz     1e9ah                   ; wait for it to end
;     1e9f:  in      al, dx
;            and     al, 8
;            jz      1e9fh                   ; wait for the next one
;            pop     ax
;            pop     dx
;            ret
;
; The first wait keeps the two writes well clear of the moment the card
; reads them. The second makes sure the new page is actually on screen
; before the game starts scribbling on the old one.
;
; And here's the beautiful part: SCI drivers all speak the same
; interface, so you can take VGA320.DRV from Leisure Suit Larry 6, drop
; it into the King's Quest 6 directory, and the movie plays perfectly.
; No patching, no disassembling, just a file copied from one game to
; another. Graham's family, rescued by Larry Laffer. That is the more
; general solution, and the one to reach for if you ever run into this
; in another SCI 1.1 game: try the video driver from a later one.

        org     100h

table   equ     44h + 15 * 2            ; function 15 in the function table

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, driver
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to function 15
        xor     cx, cx
        mov     dx, table
        int     21h
        mov     ah, 3fh                 ; read it
        mov     cx, 2
        mov     dx, entry
        int     21h
        cmp     word [entry], 1beah     ; the original?
        jne     close
        mov     ax, 4200h               ; move back
        xor     cx, cx
        mov     dx, table
        int     21h
        mov     ah, 40h                 ; point it at the wrapper
        mov     cx, 2
        mov     dx, newentry
        int     21h
        mov     ax, 4200h               ; move to the end of the driver
        xor     cx, cx
        mov     dx, flip
        int     21h
        mov     ah, 40h                 ; append the wrapper
        mov     cx, payload_end - flip
        mov     dx, section.payload.start
        int     21h
close:  mov     ah, 3eh                 ; close
        int     21h
done:   ret

driver:   db      "VGA320.DRV", 0
newentry: dw      flip
entry:    dw      0

        section payload follows=.text vstart=1c89h

flip:   call    retrace
        call    1beah                   ; the original function 15
        call    retrace
        ret

retrace:
        push    dx
        push    ax
        mov     dx, 3dah                ; input status
.out:   in      al, dx
        test    al, 8                   ; in vertical retrace?
        jnz     .out                    ; wait for it to end
.in:    in      al, dx
        test    al, 8
        jz      .in                     ; wait for the next one
        pop     ax
        pop     dx
        ret
payload_end:
