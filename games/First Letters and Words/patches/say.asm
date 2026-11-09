; SAY.COM - speak the command line through the resident SmoothTalker 3.2
; driver (loaded by SPEECH.EXE from First Letters and Words).
;
; Usage: SAY hEH4lOW
;
; The driver is not an interrupt handler: callers far-call the address
; stored in the INT 7Dh vector, Pascal style (callee pops 12 bytes):
;   push far ptr to length-prefixed string, flag, p1, p2, p3 (0..9 each)

        org 100h

        ; Is the driver loaded? (vector 7Dh non-null)
        xor ax, ax
        mov es, ax
        mov ax, [es:7Dh*4]
        or ax, [es:7Dh*4+2]
        jz no_driver

        ; say(text, flag, p1, p2, p3)
        push ds                 ; segment of text
        mov ax, 80h
        push ax                 ; offset of text (length byte)
        xor ax, ax
        push ax                 ; flag = 0
        mov ax, 5
        push ax                 ; p1
        push ax                 ; p2
        push ax                 ; p3
        call far [es:7Dh*4]
        mov ax, 4C00h
        int 21h

no_driver:
        mov dx, msg
        mov ah, 9
        int 21h
        mov ax, 4C01h
        int 21h

msg     db 'SmoothTalker not loaded, run SPEECH first.', 13, 10, '$'
