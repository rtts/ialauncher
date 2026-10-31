/* Play the intro of Ascendancy.
 *
 * The FLIC video is taken from data\intro65a.flc in ASCEND02.COB and
 * the PCM music from data\intro00.raw in ASCEND01.COB. The archives
 * start with the number of files, followed by their 50-byte names,
 * and then their offsets in the archive, as 32-bit numbers.
 *
 * The animation is shown in VESA mode 101h, 640x480 with 256 colors,
 * and timed by the timer chip. The music is played by the Sound
 * Blaster from a buffer that its DMA channel loops through, and each
 * half is refilled once the other half is playing, which is noticed
 * by polling, so that no interrupt handler is needed.
 *
 * Build with Open Watcom: wcl386 -bt=dos -l=dos4g intro.c
 */

#include <conio.h>
#include <i86.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define WIDTH 640
#define HEIGHT 480
#define RATE 22050
#define DMA_SIZE 32768
#define HALF (DMA_SIZE / 2)

typedef struct {
    FILE *file;
    long offset, size;
} Entry;

/* Find a file in an archive, and leave the archive open at it. */
static int find(const char *archive, const char *name, Entry *entry)
{
    unsigned long count, i, offsets[2];
    char entry_name[51] = { 0 };
    FILE *file = fopen(archive, "rb");

    if (!file || fread(&count, 4, 1, file) != 1)
        return 0;
    for (i = 0; i < count; i++) {
        fread(entry_name, 50, 1, file);
        if (stricmp(entry_name, name) == 0)
            break;
    }
    if (i == count) {
        fclose(file);
        return 0;
    }
    fseek(file, 4 + count * 50 + i * 4, SEEK_SET);
    fread(offsets, 4, 2, file);
    if (i + 1 == count) {
        fseek(file, 0, SEEK_END);
        offsets[1] = ftell(file);
    }
    entry->file = file;
    entry->offset = offsets[0];
    entry->size = offsets[1] - offsets[0];
    fseek(file, entry->offset, SEEK_SET);
    return 1;
}

/* Allocate conventional memory, which the DMA controller and the VESA
 * BIOS can reach, and return it at its linear address. */
static unsigned char *dos_alloc(unsigned bytes)
{
    union REGS r;

    memset(&r, 0, sizeof r);
    r.w.ax = 0x100;
    r.w.bx = (bytes + 15) >> 4;
    int386(0x31, &r, &r);
    return r.w.cflag ? NULL : (unsigned char *)((unsigned long)r.w.ax << 4);
}

/* Time */

static volatile unsigned long *bios_ticks = (unsigned long *)0x46c;

/* Count the timer chip down by one instead of two, at the same rate, so
 * that its counter tells how far the current tick is. */
static void timer_init(void)
{
    _disable();
    outp(0x43, 0x34);
    outp(0x40, 0);
    outp(0x40, 0);
    _enable();
}

static void timer_done(void)
{
    _disable();
    outp(0x43, 0x36);
    outp(0x40, 0);
    outp(0x40, 0);
    _enable();
}

/* Return the time in milliseconds, never earlier than before. */
static double now(void)
{
    static double last;
    unsigned long ticks;
    unsigned count;
    double ms;

    do {
        ticks = *bios_ticks;
        _disable();
        outp(0x43, 0);
        count = inp(0x40);
        count |= inp(0x40) << 8;
        _enable();
    } while (ticks != *bios_ticks);
    ms = (ticks * 65536.0 + ((65536 - count) & 0xffff)) / 1193.182;
    if (ms > last)
        last = ms;
    return last;
}

/* Music */

static unsigned sb_port = 0x220, sb_dma = 1;
static int sb_ok;
static unsigned char *dma_buffer;
static Entry music;
static long music_total, halves_played;
static int playing_half;

static void dsp_write(int value)
{
    long i;

    for (i = 0; i < 100000 && inp(sb_port + 0xc) & 0x80; i++)
        ;
    outp(sb_port + 0xc, value);
}

static int dsp_read(void)
{
    long i;

    for (i = 0; i < 100000; i++)
        if (inp(sb_port + 0xe) & 0x80)
            return inp(sb_port + 0xa);
    return -1;
}

static int dsp_reset(void)
{
    int i;

    outp(sb_port + 6, 1);
    for (i = 0; i < 100; i++)
        inp(sb_port + 6);
    outp(sb_port + 6, 0);
    return dsp_read() == 0xaa;
}

/* Fill half of the buffer with music, and then silence. */
static void fill(int half)
{
    unsigned char *buffer = dma_buffer + half * HALF;
    long got = fread(buffer, 1, music.size < HALF ? music.size : HALF,
                     music.file);

    music.size -= got;
    memset(buffer + got, 0x80, HALF - got);
}

static void music_start(void)
{
    static const unsigned page_ports[] = { 0x87, 0x83, 0x81, 0x82 };
    unsigned long address;
    char *blaster = getenv("BLASTER");
    char *p;
    int major;

    for (p = blaster; p && *p; p++) {
        if (*p == 'A' || *p == 'a')
            sb_port = strtoul(p + 1, NULL, 16);
        else if (*p == 'D' || *p == 'd')
            sb_dma = strtoul(p + 1, NULL, 10);
    }
    if (sb_dma > 3 || !dsp_reset())
        return;

    /* A buffer that doesn't cross a 64K boundary, which DMA can't. */
    dma_buffer = dos_alloc(2 * DMA_SIZE);
    if (!dma_buffer)
        return;
    address = (unsigned long)dma_buffer;
    if ((address & 0xffff) + DMA_SIZE > 0x10000)
        address = (address | 0xffff) + 1;
    dma_buffer = (unsigned char *)address;
    fill(0);
    fill(1);

    outp(0x0a, 4 | sb_dma);                     /* mask the channel */
    outp(0x0c, 0);                              /* reset the flip-flop */
    outp(0x0b, 0x58 | sb_dma);                  /* auto-init, to the card */
    outp(sb_dma * 2, address & 0xff);
    outp(sb_dma * 2, address >> 8 & 0xff);
    outp(page_ports[sb_dma], address >> 16);
    outp(sb_dma * 2 + 1, (DMA_SIZE - 1) & 0xff);
    outp(sb_dma * 2 + 1, (DMA_SIZE - 1) >> 8);
    outp(0x0a, sb_dma);                         /* unmask it */

    dsp_write(0xe1);                            /* version */
    major = dsp_read();
    dsp_read();
    if (major >= 4) {                           /* exact rate */
        dsp_write(0x41);
        dsp_write(RATE >> 8);
        dsp_write(RATE & 0xff);
    } else {                                    /* time constant */
        dsp_write(0x40);
        dsp_write(256 - 1000000 / RATE);
    }
    dsp_write(0xd1);                            /* speaker on */
    dsp_write(0x48);                            /* block size */
    dsp_write((HALF - 1) & 0xff);
    dsp_write((HALF - 1) >> 8);
    dsp_write(0x1c);                            /* auto-init 8-bit output */
    sb_ok = 1;
}

/* Refill the half that has just been played, and return whether music
 * is still playing. */
static int music_service(void)
{
    unsigned count;
    int half;

    if (!sb_ok)
        return 0;
    outp(0x0c, 0);
    count = inp(sb_dma * 2 + 1);
    count |= inp(sb_dma * 2 + 1) << 8;
    half = (DMA_SIZE - 1 - count) >= HALF;
    if (half != playing_half) {
        inp(sb_port + 0xe);                     /* acknowledge the card */
        fill(playing_half);
        playing_half = half;
        halves_played++;
    }
    return halves_played * HALF < music_total;
}

static void music_stop(void)
{
    if (!sb_ok)
        return;
    dsp_write(0xd0);                            /* pause */
    dsp_write(0xd3);                            /* speaker off */
    dsp_reset();
    outp(0x0a, 4 | sb_dma);
}

/* Video */

static unsigned char screen[WIDTH * HEIGHT];
static unsigned char palette[768];
static int palette_changed;
static unsigned bank_step = 1;

#pragma pack(push, 1)
static struct {
    unsigned long edi, esi, ebp, reserved, ebx, edx, ecx, eax;
    unsigned short flags, es, ds, fs, gs, ip, cs, sp, ss;
} rmi;
#pragma pack(pop)

/* Switch to 640x480 with 256 colors, with a 64K window at A0000h. */
static int video_start(void)
{
    unsigned char *info = dos_alloc(256);
    union REGS r;
    struct SREGS s;
    unsigned granularity;

    if (!info)
        return 0;
    memset(&rmi, 0, sizeof rmi);
    rmi.eax = 0x4f01;                           /* mode information */
    rmi.ecx = 0x101;
    rmi.es = (unsigned long)info >> 4;
    memset(&r, 0, sizeof r);
    segread(&s);
    r.w.ax = 0x300;                             /* through real mode */
    r.w.bx = 0x10;
    r.x.edi = (unsigned)&rmi;
    int386x(0x31, &r, &r, &s);
    if ((rmi.eax & 0xffff) != 0x4f)
        return 0;
    granularity = *(unsigned short *)(info + 4);
    if (granularity)
        bank_step = 64 / granularity;

    memset(&r, 0, sizeof r);
    r.w.ax = 0x4f02;
    r.w.bx = 0x101;
    int386(0x10, &r, &r);
    return r.w.ax == 0x4f;
}

static void video_stop(void)
{
    union REGS r;

    memset(&r, 0, sizeof r);
    r.w.ax = 3;
    int386(0x10, &r, &r);
}

static void show(void)
{
    union REGS r;
    long offset;
    int i;

    if (palette_changed) {
        outp(0x3c8, 0);
        for (i = 0; i < 768; i++)
            outp(0x3c9, palette[i]);
        palette_changed = 0;
    }
    for (offset = 0; offset < WIDTH * HEIGHT; offset += 65536) {
        memset(&r, 0, sizeof r);
        r.w.ax = 0x4f05;
        r.w.dx = (offset >> 16) * bank_step;
        int386(0x10, &r, &r);
        memcpy((void *)0xa0000, screen + offset,
               WIDTH * HEIGHT - offset < 65536 ? WIDTH * HEIGHT - offset
                                               : 65536);
    }
}

/* FLC chunks */

static void set_colors(unsigned char *p, int shift)
{
    int packets = *(unsigned short *)p, color = 0, count;

    for (p += 2; packets--;) {
        color += *p++;
        count = *p++;
        if (!count)
            count = 256;
        for (; count-- && color < 256; color++, p += 3) {
            palette[color * 3] = p[0] >> shift;
            palette[color * 3 + 1] = p[1] >> shift;
            palette[color * 3 + 2] = p[2] >> shift;
        }
    }
    palette_changed = 1;
}

static void byte_run(unsigned char *p)
{
    unsigned char *line;
    int y, x, count;

    for (y = 0; y < HEIGHT; y++) {
        line = screen + y * WIDTH;
        p++;                                    /* obsolete packet count */
        for (x = 0; x < WIDTH;) {
            count = (signed char)*p++;
            if (count > 0) {
                memset(line + x, *p++, count);
                x += count;
            } else if (count < 0) {
                memcpy(line + x, p, -count);
                p -= count;
                x -= count;
            } else {
                break;
            }
        }
    }
}

static void delta(unsigned char *p)
{
    int lines = *(unsigned short *)p, y = 0, x, packets, count;
    short word;
    unsigned char *line;

    for (p += 2; lines--; y++) {
        for (;;) {
            word = *(short *)p;
            p += 2;
            if ((word & 0xc000) == 0xc000)      /* skip lines */
                y -= word;
            else if ((word & 0xc000) == 0x8000) /* last pixel of the line */
                screen[y * WIDTH + WIDTH - 1] = word & 0xff;
            else
                break;
        }
        line = screen + y * WIDTH;
        for (packets = word, x = 0; packets--;) {
            x += *p++;
            count = (signed char)*p++;
            if (count > 0) {
                memcpy(line + x, p, count * 2);
                p += count * 2;
                x += count * 2;
            } else {
                for (; count++; x += 2) {
                    line[x] = p[0];
                    line[x + 1] = p[1];
                }
                p += 2;
            }
        }
    }
}

static void frame(unsigned char *p, int chunks)
{
    unsigned long size;
    int type;

    for (; chunks--; p += size) {
        size = *(unsigned long *)p;
        type = *(unsigned short *)(p + 4);
        switch (type) {
        case 4: set_colors(p + 6, 2); break;     /* 256 levels */
        case 11: set_colors(p + 6, 0); break;    /* 64 levels */
        case 7: delta(p + 6); break;
        case 13: memset(screen, 0, sizeof screen); break;
        case 15: byte_run(p + 6); break;
        case 16: memcpy(screen, p + 6, sizeof screen); break;
        }
        if (size < 6)
            break;
    }
}

static int key_pressed(void)
{
    if (!kbhit())
        return 0;
    if (!getch())
        getch();
    return 1;
}

int main(void)
{
    Entry flic;
    unsigned char header[128], *data = NULL;
    unsigned long size, data_size = 0, frames, speed, i;
    double start;
    int stop = 0;

    if (!find("ASCEND02.COB", "data\\intro65a.flc", &flic)
        || !find("ASCEND01.COB", "data\\intro00.raw", &music)) {
        puts("The intro wasn't found in the archives.");
        return 1;
    }
    fread(header, sizeof header, 1, flic.file);
    frames = *(unsigned short *)(header + 6);
    speed = *(unsigned long *)(header + 16);
    fseek(flic.file, flic.offset + *(unsigned long *)(header + 80), SEEK_SET);
    music_total = music.size;

    if (!video_start()) {
        puts("VESA mode 101h isn't available.");
        return 1;
    }
    timer_init();
    music_start();
    start = now();

    for (i = 0; i < frames && !stop;) {
        if (fread(header, 16, 1, flic.file) != 1)
            break;
        size = *(unsigned long *)header;
        if (size < 16)
            break;
        if (size > data_size) {
            data_size = size;
            data = realloc(data, data_size);
        }
        fread(data, size - 16, 1, flic.file);
        if (*(unsigned short *)(header + 4) != 0xf1fa)
            continue;                           /* not a frame */
        frame(data, *(unsigned short *)(header + 6));
        while (now() < start + i * speed && !stop) {
            music_service();
            stop = key_pressed();
        }
        show();
        i++;
    }
    while (!stop && music_service())
        stop = key_pressed();

    music_stop();
    timer_done();
    video_stop();
    return 0;
}
