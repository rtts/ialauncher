@echo off
rem Unpack 3-D Body Adventure into the current directory, from the
rem floppy files in C:\. This is install.bat from disk 1, without the
rem disk prompts and without running setup afterwards.
md drivers
copy c:\0.zip 0.zip>nul
c:\transfer 0.zip  > nul
del 0.zip
ren 0 setup.scr
ren 1 alt.cnf
ren 2 kagroup.exe
ren 3 kalogo.adl
ren 4 kalogo.rld
ren 5 knowledg.voc
ren 6 sbtest.com
ren 7 gm1.bnk
ren 8 gm2.bnk
ren 9 ultrasnd.exe
ren 10 ultramid.ini
ren 11 vgacapt.exe
ren 12 mouse.com
ren 13 moustest.exe
ren 14 kawin.exe
ren 15 kawin.txt
copy 16 drivers\adlib.drv>nul
del 16
copy 17 drivers\adlibdig.drv>nul
del 17
copy 18 drivers\adlibg.drv>nul
del 18
copy 19 drivers\algdig.drv>nul
del 19
copy 20 drivers\ariadig.drv>nul
del 20
copy 21 drivers\ariaxmid.drv>nul
del 21
copy c:\1.zip 1.zip>nul
c:\transfer 1.zip  > nul
del 1.zip
c:\appendf 22 drivers\ariaxmid.drv
del 22
copy 23 drivers\cvxsnd.drv>nul
del 23
copy 24 drivers\disney.drv>nul
del 24
copy 25 drivers\gravisdg.drv>nul
del 25
copy 26 drivers\gravismu.drv>nul
del 26
copy 27 drivers\lantsnd.drv>nul
del 27
copy 28 drivers\msftdig.drv>nul
del 28
copy 29 drivers\msftmus.drv>nul
del 29
copy 30 drivers\pasdig.drv>nul
del 30
copy 31 drivers\pasfm.drv>nul
del 31
copy 32 drivers\pasopl.drv>nul
del 32
copy 33 drivers\pcspkr.drv>nul
del 33
copy 34 drivers\roland.drv>nul
del 34
copy 35 drivers\sbdig.drv>nul
del 35
copy 36 drivers\sbfm.drv>nul
del 36
copy 37 drivers\sbp2fm.drv>nul
del 37
copy 38 drivers\sbpdig.drv>nul
del 38
copy 39 drivers\tansltl.drv>nul
del 39
copy 40 drivers\vmsnd.drv>nul
del 40
ren 41 vrsd.386
ren 42 3dbody.pif
ren 43 3dbody.ico
ren 44 ka.ad
ren 45 ka.adl
copy c:\2.zip 2.zip>nul
c:\transfer 2.zip  > nul
del 2.zip
c:\appendf 46 ka.adl
del 46
ren 47 ka.bml
ren 48 ka.com
ren 49 ka.db
ren 50 ka.iml
copy c:\3.zip 3.zip>nul
c:\transfer 3.zip  > nul
del 3.zip
c:\appendf 51 ka.iml
del 51
copy c:\4.zip 4.zip>nul
c:\transfer 4.zip  > nul
del 4.zip
c:\appendf 52 ka.iml
del 52
copy c:\5.zip 5.zip>nul
c:\transfer 5.zip  > nul
del 5.zip
c:\appendf 53 ka.iml
del 53
copy /b c:\6.zip .\temp.gz>nul
copy /b .\temp.gz+c:\6.mor .\6.zip>nul
del .\temp.gz
c:\transfer 6.zip >nul
del 6.zip
c:\appendf 54 ka.iml
del 54
copy c:\7.zip 7.zip>nul
c:\transfer 7.zip  > nul
del 7.zip
c:\appendf 55 ka.iml
del 55
copy c:\8.zip 8.zip>nul
c:\transfer 8.zip  > nul
del 8.zip
c:\appendf 56 ka.iml
del 56
copy c:\9.zip 9.zip>nul
c:\transfer 9.zip  > nul
del 9.zip
c:\appendf 57 ka.iml
del 57
copy c:\10.zip 10.zip>nul
c:\transfer 10.zip  > nul
del 10.zip
c:\appendf 58 ka.iml
del 58
copy c:\11.zip 11.zip>nul
c:\transfer 11.zip  > nul
del 11.zip
c:\appendf 59 ka.iml
del 59
copy c:\12.zip 12.zip>nul
c:\transfer 12.zip  > nul
del 12.zip
c:\appendf 60 ka.iml
del 60
copy /b c:\13.zip .\temp.gz>nul
copy /b .\temp.gz+c:\13.mor .\13.zip>nul
del .\temp.gz
c:\transfer 13.zip >nul
del 13.zip
c:\appendf 61 ka.iml
del 61
copy c:\14.zip 14.zip>nul
c:\transfer 14.zip  > nul
del 14.zip
c:\appendf 62 ka.iml
del 62
copy c:\15.zip 15.zip>nul
c:\transfer 15.zip  > nul
del 15.zip
c:\appendf 63 ka.iml
del 63
copy c:\16.zip 16.zip>nul
c:\transfer 16.zip  > nul
del 16.zip
c:\appendf 64 ka.iml
del 64
ren 65 ka.inl
ren 66 ka.lch
ren 67 ka.lnk
ren 68 ka.ndx
ren 69 ka.not
ren 70 ka.rld
copy c:\17.zip 17.zip>nul
c:\transfer 17.zip  > nul
del 17.zip
c:\appendf 71 ka.rld
del 71
ren 72 ka.skp
ren 73 ka.snd
copy c:\18.zip 18.zip>nul
c:\transfer 18.zip  > nul
del 18.zip
c:\appendf 74 ka.snd
del 74
copy /b c:\19.zip .\temp.gz>nul
copy /b .\temp.gz+c:\19.mor .\19.zip>nul
del .\temp.gz
c:\transfer 19.zip >nul
del 19.zip
c:\appendf 75 ka.snd
del 75
copy c:\20.zip 20.zip>nul
c:\transfer 20.zip  > nul
del 20.zip
c:\appendf 76 ka.snd
del 76
ren 77 ka.str
ren 78 ka.tnl
copy c:\21.zip 21.zip>nul
c:\transfer 21.zip  > nul
del 21.zip
c:\appendf 79 ka.tnl
del 79
ren 80 ka.txt
copy c:\22.zip 22.zip>nul
c:\transfer 22.zip  > nul
del 22.zip
c:\appendf 81 ka.txt
del 81
ren 82 ka.wfl
copy c:\23.zip 23.zip>nul
c:\transfer 23.zip  > nul
del 23.zip
c:\appendf 83 ka.wfl
del 83
ren 84 kav.pgm
copy c:\24.zip 24.zip>nul
c:\transfer 24.zip  > nul
del 24.zip
c:\appendf 85 kav.pgm
del 85
ren 86 small.fnt
ren 87 standard.fnt
ren 88 wf.exe
ren 89 zrun.exe
copy c:\25.zip 25.zip>nul
c:\transfer 25.zip  > nul
del 25.zip
c:\appendf 90 zrun.exe
del 90
copy c:\26.zip 26.zip>nul
c:\transfer 26.zip  > nul
del 26.zip
c:\appendf 91 zrun.exe
del 91
ren 92 zsc.arc
ren 93 cmp.arc
copy c:\27.zip 27.zip>nul
c:\transfer 27.zip  > nul
del 27.zip
c:\appendf 94 cmp.arc
del 94
copy c:\28.zip 28.zip>nul
c:\transfer 28.zip  > nul
del 28.zip
c:\appendf 95 cmp.arc
del 95
ren 96 cmd.arc
ren 97 bum.arc
ren 98 clk.arc
ren 99 txt.arc
ren 100 fixed.pal
