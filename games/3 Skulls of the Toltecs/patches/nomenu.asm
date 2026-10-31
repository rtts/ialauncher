; Start 3 Skulls of the Toltecs without displaying the menu first.
;
; The game's script starts by showing the menu, which waits for PLAY to
; be clicked, and ignores the keyboard. The script command that shows
; it calls the menu with the script's position, and continues from the
; position the menu returns, which PLAY leaves as it is. So nomenu
; replaces that call in PICTURE.EXE with nops, and the game continues
; as if PLAY was clicked. F10 still shows the menu during the game.

        org     100h

        mov     ax, 3d02h               ; open for reading and writing
        mov     dx, exe
        int     21h
        jc      done
        mov     bx, ax
        mov     ax, 4200h               ; move to the call
        mov     cx, 13a20h >> 16
        mov     dx, 13a20h & 0ffffh
        int     21h
        mov     ah, 40h                 ; replace it
        mov     cx, 5
        mov     dx, nops
        int     21h
        mov     ah, 3eh                 ; close
        int     21h
done:   ret

exe:    db      "\3SKULLS\PICTURE.EXE", 0
nops:   db      90h, 90h, 90h, 90h, 90h
