; Skip the main menu in Escape from Delirium.
;
; The game consists of rooms, and each room has one or more entry
; scripts. It starts in room 93, which shows the logo, and then
; continues in room 92, entry 1, which fades in the menu and waits for a
; click. Clicking "Intro / New Game" goes to room 80, entry 2, from where
; the scripts chain through the rest of the intro (opcode 2Dh is "go to
; room, entry"):
;
;     R80/2 -> R91/1 (newspaper) -> R78/1 -> R80/1 -> R78/2 -> R75/1
;
; Room 92, entry 1 ends like this (opcode 26h always takes 9 bytes, and
; 44h 00h waits for one frame):
;
;     26 04 00 00 01 00 00 00 00      Esc goes to room 0, entry 1 (quit)
;     26 02 00 00 00 00 00 00 00      show the mouse pointer
;     44 32                           wait 50 frames
;
; So replace those 20 bytes with the same number of bytes that go
; to room 80, entry 2 once the menu has faded in:
;
;     26 02 00 00 00 00 00 00 00      show the mouse pointer
;     44 64                           wait 100 frames
;     44 00  44 00  44 00             wait one frame, three times
;     2d 50 02                        go to room 80, entry 2

        org     100h

offset  equ     17f60h + 92653dh + 82cbh

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the end of the script
        mov     cx, offset >> 16
        mov     dx, offset & 0ffffh
        int     21h
        mov     ah, 40h                 ; replace it
        mov     cx, script.end - script
        mov     dx, script
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

exe:    db      "\DELIRIUM\DELIRIUM.EXE", 0
script: db      26h, 02h, 0, 0, 0, 0, 0, 0, 0
        db      44h, 100, 44h, 0, 44h, 0, 44h, 0
        db      2dh, 80, 2
.end:
