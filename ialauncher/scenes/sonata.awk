BEGIN {
    VOICES = 3
    PAIRS = 256
    SAMPLE_RATE = 1193182 / 64
    LOWEST = 28
}

/^#/ { next }

{
    if ($1 < start) {
        print "Note at " $1 " ms is out of order" > "/dev/stderr"
        exit 1
    }
    for (v = 0; v < VOICES; v++) if (busy[v] <= $1) break
    if (v == VOICES) {
        print "More than " VOICES " voices at " $1 " ms" > "/dev/stderr"
        exit 1
    }
    if ($3 - LOWEST < 1 || $3 - LOWEST > 63) {
        print "Note " $3 " is out of range" > "/dev/stderr"
        exit 1
    }
    if ($2 < 1 || $2 > 65535) {
        print "Length " $2 " ms is out of range" > "/dev/stderr"
        exit 1
    }
    busy[v] = $1 + $2
    if (busy[v] > end) end = busy[v]
    pair = ($1 - start) " " $2
    start = $1
    if (!(pair in index_of)) {
        if (pairs == PAIRS) {
            print "More than " PAIRS " pairs of waits and lengths" > "/dev/stderr"
            exit 1
        }
        index_of[pair] = pairs
        order[pairs++] = pair
    }
    events[count++] = index_of[pair] * 256 + ($3 - LOWEST) * 4 + v
}

END {
    print "static const unsigned short __far sonata[] = {"
    for (i = 0; i < count; i++) print "    " events[i] ","
    print "};"
    print "static const unsigned short __far waits[] = {"
    for (i = 0; i < pairs; i++) { split(order[i], parts); print "    " parts[1] "," }
    print "};"
    print "static const unsigned short __far lengths[] = {"
    for (i = 0; i < pairs; i++) { split(order[i], parts); print "    " parts[2] "," }
    print "};"
    print "#define SONATA_MS " end "ul"
    print "static const unsigned short steps[64] = {"
    for (p = LOWEST; p < LOWEST + 64; p++) {
        step = int(440 * 2 ^ ((p - 69) / 12) * 65536 / SAMPLE_RATE + 0.5)
        print "    " (step > 65535 ? 0 : step) ","
    }
    print "};"
}
