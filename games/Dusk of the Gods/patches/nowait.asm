; Start the intro of Dusk of the Gods without waiting for a key.
;
; Before the intro, the game shows a poem in a border of runes, until a
; key is pressed or 59 seconds have passed. The rest of the intro goes
; by on its own. This patch makes that 100 ticks, five and a half
; seconds, so the intro continues without a key.
;
;     original                          patched
;
;     47e1 mov  ax, 1     ; or a key    47e1 mov  ax, 1
;     47e4 push ax                      47e4 push ax
;     47e5 mov  ax, 438h  ; 59 seconds  47e5 mov  ax, 100   ; 5.5 seconds
;     47e8 push ax                      47e8 push ax
;     47e9 call 0000:0d5a ; wait        47e9 call 0000:0d5a

        org     100h

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the number of ticks
        xor     cx, cx
        mov     dx, 1800h + 47e6h
        int     21h
        mov     ah, 40h                 ; replace it
        mov     cx, 2
        mov     dx, ticks
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

exe:    db      "\DUSKGOD\RUNTIME.1", 0
ticks:  dw      100                     ; 18.2 a second
