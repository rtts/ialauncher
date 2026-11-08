; Install El-Fish to C:\ELFISH unattended
;
; INSTALL.EXE is a script interpreter by Vladimir Pokhilko, friend of
; Alexey Pajitnov, creator of Tetris. When it starts, it interprets
; the .PRG file with the same basename as itself. This file replaces
; the original INSTALL.PRG, so running INSTALL now runs this script
; instead.
;
@prod = "ELFISH"
@path = "C:\ELFISH"
@source = "DATA"
@prefix = "XX"
@bakext = "EF~"
@PACKMODE = 6        ; high resolution with sound
#MKDIR
#CHDIR @path
#UNPACK 100000 ELFISH.PKD
#EXIT
#END
