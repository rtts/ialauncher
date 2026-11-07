/* Show the full-screen pictures of Duke Nukem 1 before the game starts.
 *
 * The pictures are 320x200 EGA images of 32000 bytes: four planes of
 * 8000 bytes each, in the order blue, green, red and intensity, that
 * use the default EGA palette. Each one is copied to its plane in mode
 * 0Dh and shown for three seconds. Esc stops the intro.
 *
 * Like the game, the pictures fade in and out by switching the 16
 * palette registers from black to their colors one at a time, and back,
 * with 20 ms in between. Since the registers are numbered after the
 * planes, this makes the planes seem to appear one by one. Such short
 * pauses are timed with the counter of the timer chip.
 *
 * Run it from the game directory, which has the files of all three
 * episodes, since it ends with the endings of the first two. (END.DN3
 * is an alternative title screen instead.)
 *
 * Build with Open Watcom: wcl -bt=dos -ms intro.c
 */

#include <conio.h>
#include <dos.h>
#include <i86.h>
#include <stdio.h>
#include <string.h>

#define PLANE 8000
#define SHOW_MS 3000
#define STEP_MS 20
#define PIT_PER_MS 1193                         /* 1193182 Hz */
#define ESC 27

static const char *pictures[] = {
    "DN.DN1", "CREDITS.DN1", "BADGUY.DN1", "DUKE.DN1",
    "END.DN1", "END.DN2",
};
#define COUNT (sizeof pictures / sizeof *pictures)
static unsigned char buffer[4 * PLANE];
static volatile unsigned long __far *bios_ticks = MK_FP(0x40, 0x6c);

static void set_mode(int mode)
{
    union REGS r;

    r.w.ax = mode;
    int86(0x10, &r, &r);
}

/* Set the mode of the timer chip's first counter. Mode 34h counts down
 * by one instead of two, at the same rate, so that the counter tells how
 * far the current tick is, and 36h is the usual one of the BIOS. */
static void timer_mode(int mode)
{
    _disable();
    outp(0x43, mode);
    outp(0x40, 0);
    outp(0x40, 0);
    _enable();
}

/* Return the time in timer chip counts, which wraps after an hour. */
static unsigned long now(void)
{
    unsigned long ticks;
    unsigned count;

    do {
        ticks = *bios_ticks;
        _disable();
        outp(0x43, 0);                          /* latch counter 0 */
        count = inp(0x40);
        count |= inp(0x40) << 8;
        _enable();
    } while (ticks != *bios_ticks);
    return (ticks << 16) + (unsigned)(0 - count);
}

/* Set a palette register to one of the 64 EGA colors. */
static void set_register(int index, int color)
{
    union REGS r;

    r.w.ax = 0x1000;
    r.h.bl = index;
    r.h.bh = color;
    int86(0x10, &r, &r);
}

/* The color of a register in the default palette of mode 0Dh, in which
 * the intensity bit is the low green bit of the EGA colors. */
static int default_color(int index)
{
    return index < 8 ? index : index + 8;
}

static int load(const char *filename)
{
    FILE *file;
    size_t got;

    file = fopen(filename, "rb");
    if (!file)
        return 0;
    got = fread(buffer, 1, sizeof buffer, file);
    fclose(file);
    return got == sizeof buffer;
}

static void show(void)
{
    unsigned char __far *screen = MK_FP(0xa000, 0);
    int plane;

    for (plane = 0; plane < 4; plane++) {
        outp(0x3c4, 2);                         /* map mask */
        outp(0x3c5, 1 << plane);
        _fmemcpy(screen, buffer + plane * PLANE, PLANE);
    }
    outp(0x3c5, 0xf);
}

/* Wait for the given number of milliseconds, and return whether Esc
 * was pressed. Other keys are ignored. */
static int wait(long ms)
{
    unsigned long start = now();
    int key;

    while (now() - start < ms * PIT_PER_MS) {
        if (kbhit()) {
            key = getch();
            if (key == 0)
                getch();
            else if (key == ESC)
                return 1;
        }
    }
    return 0;
}

/* Switch the palette registers to their colors, or to black, one by
 * one, and return whether Esc was pressed. */
static int fade(int in)
{
    int i;

    for (i = 0; i < 16; i++) {
        if (wait(STEP_MS))
            return 1;
        set_register(i, in ? default_color(i) : 0);
    }
    return 0;
}

int main(void)
{
    int i, j, shown = 0;

    timer_mode(0x34);
    for (i = 0; i < COUNT; i++) {
        if (!load(pictures[i]))
            continue;
        if (!shown++)
            set_mode(0xd);
        for (j = 0; j < 16; j++)
            set_register(j, 0);
        show();
        if (fade(1) || wait(SHOW_MS) || fade(0))
            break;
    }
    timer_mode(0x36);
    if (shown)
        set_mode(3);
    return 0;
}
