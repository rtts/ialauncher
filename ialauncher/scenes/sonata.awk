BEGIN {
    VOICES = 3
    SAMPLE_RATE = 1193182 / 64
}

/^#/ { next }

!table {
    for (v = 0; v < VOICES; v++) if (busy[v] <= $1) break
    if (v == VOICES) {
        print "More than " VOICES " voices at " $1 " ms" > "/dev/stderr"
        exit 1
    }
    busy[v] = $1 + $2
    print $1, 1, v, $3
    print $1 + $2, 0, v, 0
}

table {
    if (!rows++) print "static const unsigned short __far sonata[][2] = {"
    print "    {" $1 - last ", " $3 * 256 + $4 "},"
    last = $1
}

END {
    if (!table) exit
    print "};"
    print "static const unsigned short steps[128] = {"
    for (p = 0; p < 128; p++) {
        step = int(440 * 2 ^ ((p - 69) / 12) * 65536 / SAMPLE_RATE + 0.5)
        print "    " (step > 65535 ? 0 : step) ","
    }
    print "};"
}
