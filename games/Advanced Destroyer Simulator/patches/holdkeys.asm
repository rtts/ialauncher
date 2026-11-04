; Press Up and Enter in the menu of Advanced Destroyer Simulator, holding
; each key down for a quarter of a second.
;
; The game installs its own keyboard handler, which keeps a table of the
; keys that are down. The menu looks at that table now and then, so it
; only sees a key that is still down when it looks. autotype releases
; every key after 50 ms, which the menu misses.
;
; This TSR presses the keys itself, through the keyboard controller:
; command D2h makes the 8042 act as if the byte came from the keyboard,
; raising IRQ1 like a real keystroke.
;
; The game replaces the timer interrupt with its own handlers, which
; never chain to the previous one, so the TSR can't count timer ticks.
; It uses the periodic interrupt of the real-time clock (IRQ8, INT 70h)
; instead, which the game leaves alone. After the last key, it switches
; the periodic interrupt off and restores the clock's settings.
;
; DOSBox passes these bytes on as they are, without translating them
; from scancode set 2, so they are set 1 scancodes: the make code when
; the key goes down, and the make code plus 80h when it comes up.

        org     100h

%ifndef SECONDS
%define SECONDS 20                      ; before the first key
%endif
HZ      equ     8                       ; 32768 Hz >> (RATE - 1)
RATE    equ     13
HOLD    equ     HZ / 4                  ; a quarter of a second

        jmp     install

; Ticks to wait, then the byte to send. A wait of 0 ends the list.
keys:   db      SECONDS * HZ, 48h       ; Up down
        db      HOLD, 0c8h              ; Up up
        db      HOLD, 1ch               ; Enter down
        db      HOLD, 9ch               ; Enter up
        db      0

next:   dw      keys                    ; the next key to send
countdown: db   SECONDS * HZ            ; ticks until then
reg_a:  db      0                       ; the clock's settings before
reg_b:  db      0

rtc:    push    ax
        push    bx
        push    ds
        push    cs
        pop     ds
        mov     al, 0ch                 ; acknowledge the interrupt
        out     70h, al
        in      al, 71h
        cmp     byte [countdown], 0     ; already done
        je      .eoi
        dec     byte [countdown]
        jnz     .eoi
        mov     bx, [next]
        mov     al, [bx + 1]
        call    send
        add     bx, 2
        mov     [next], bx
        mov     al, [bx]
        mov     [countdown], al
        or      al, al
        jnz     .eoi
        mov     ah, [reg_a]             ; done: restore the clock
        mov     al, 0ah
        call    write_cmos
        mov     ah, [reg_b]
        mov     al, 0bh
        call    write_cmos
.eoi:   mov     al, 20h
        out     0a0h, al                ; slave PIC
        out     20h, al                 ; master PIC
        pop     ds
        pop     bx
        pop     ax
        iret

; Send al to the keyboard controller as if it came from the keyboard.
send:   mov     ah, al
        call    wait_8042
        mov     al, 0d2h
        out     64h, al
        call    wait_8042
        mov     al, ah
        out     60h, al
        ret

; Wait until the keyboard controller's input buffer is empty.
wait_8042:
        in      al, 64h
        test    al, 2
        jnz     wait_8042
        ret

; Write ah to CMOS register al.
write_cmos:
        out     70h, al
        mov     al, ah
        out     71h, al
        ret

; Everything from here on is freed when the TSR stays resident.
install:
        mov     ax, 2570h               ; INT 70h is the clock's IRQ8
        mov     dx, rtc
        int     21h
        cli
        mov     al, 0ah                 ; save the clock's settings
        out     70h, al
        in      al, 71h
        and     al, 7fh                 ; without update-in-progress
        mov     [reg_a], al
        mov     al, 0bh
        out     70h, al
        in      al, 71h
        mov     [reg_b], al
        mov     ah, 20h | RATE          ; 32768 Hz time base, HZ interrupts
        mov     al, 0ah
        call    write_cmos
        mov     ah, [reg_b]
        or      ah, 40h                 ; enable the periodic interrupt
        mov     al, 0bh
        call    write_cmos
        mov     al, 0ch                 ; clear any pending interrupt
        out     70h, al
        in      al, 71h
        in      al, 0a1h                ; unmask IRQ8 on the slave PIC
        and     al, 0feh
        out     0a1h, al
        in      al, 21h                 ; and the cascade on the master
        and     al, 0fbh
        out     21h, al
        sti
        mov     dx, (install - $$ + 100h + 15) >> 4
        mov     ax, 3100h               ; stay resident
        int     21h
