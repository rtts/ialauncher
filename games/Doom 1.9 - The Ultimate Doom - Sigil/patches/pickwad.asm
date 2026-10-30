; Move the Sigil WAD that Boom needs to C:\SIGIL.WAD.
;
; Boom needs SIGIL_COMPAT_v1_21.wad, which replaces episode 3, rather
; than SIGIL_v1_21.wad, which adds an episode 5 that Boom doesn't
; support. John Romero devilishly gave every file in the zip the same
; SIGIL_ prefix, which is all that survives in 8.3 names: DOS sees
; SIGIL_~1 to SIGIL_~4, and DOSBox numbers them in the order the host
; lists the directory, which differs between systems. So pickwad goes
; by size instead: the compat WAD is 4,634,157 bytes.
;
; It uses three DOS functions, called through int 21h with the
; function number in ah:
;
;     4Eh  find the first file matching the pattern at ds:dx
;     4Fh  find the next one; both set the carry flag when there are
;          no more, and put the file's size at ds:9Ah and its name at
;          ds:9Eh
;     56h  rename the file named at ds:dx to the name at es:di

        org     100h

        mov     ah, 4eh                 ; find the first WAD
        xor     cx, cx                  ; with no special attributes
        mov     dx, wads
next:   int     21h
        jc      done                    ; no more WADs
        mov     ah, 4fh                 ; find the next WAD
        cmp     word [9ah], 4634157 & 0ffffh
        jne     next
        cmp     word [9ch], 4634157 >> 16
        jne     next
        mov     ah, 56h                 ; rename
        mov     dx, 9eh
        mov     di, dest
        int     21h
done:   ret

wads:   db      "*.WAD", 0
dest:   db      "\SIGIL.WAD", 0
