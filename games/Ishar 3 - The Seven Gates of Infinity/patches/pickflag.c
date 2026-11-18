/* Click the Union Jack on the language screen of Ishar 3.
 *
 * After the Silmarils setup, the game shows four flags and waits for a
 * click on one of them. It ignores the keyboard there, so autotype can't
 * get past it.
 *
 * START.EXE runs under a DOS extender, which installs the game's mouse
 * handler with INT 33h function 0Ch from real mode (file offset 47FBh).
 * The mouse driver then calls that handler on every event, with the
 * event in ax, the buttons in bx and the position in cx and dx. The game
 * never asks the driver for the position or the buttons, so calling the
 * handler is all it takes to click.
 *
 * This TSR hooks INT 33h to learn the handler and its event mask. Some
 * time after the game installs it, the TSR calls the handler three
 * times: to move to the Union Jack, to press the left button and to
 * release it. The game sets the horizontal range to 0-639 and the
 * vertical range to 0-199, so the flag, at 128,137 on the 320x200
 * screen, is at 256,137.
 *
 * The game replaces the timer interrupt, so the TSR counts ticks of the
 * periodic interrupt of the real-time clock (IRQ8, INT 70h) instead, as
 * holdkeys.asm in Advanced Destroyer Simulator does. After the click, it
 * switches the periodic interrupt off and restores the clock's settings.
 *
 * Build with Open Watcom: wcl -bt=dos -ms -s -zu pickflag.c
 */

#include <conio.h>
#include <dos.h>
#include <i86.h>
#include <stdlib.h>

#define SECONDS 5                               /* after the handler */
#define RATE 13
#define HZ (32768 >> (RATE - 1))
#define HOLD (HZ / 4)                           /* a quarter of a second */
#define X 256
#define Y 137

static const struct {
    unsigned char wait, event, buttons;
} events[] = {
    { SECONDS * HZ, 1, 0 },                     /* move */
    { HOLD, 2, 1 },                             /* left button down */
    { HOLD, 4, 0 },                             /* left button up */
};
#define COUNT (sizeof events / sizeof *events)

static void (__interrupt __far *old33)(void);
static void (__far *handler)(void);             /* the game's mouse handler */
static unsigned mask;                           /* the events it wants */
static unsigned next;                           /* the next event to send */
static unsigned char countdown;                 /* ticks until then, or 0 */
static unsigned char reg_a, reg_b;              /* the clock's settings */

extern unsigned _STACKTOP;

/* Call the game's handler like the mouse driver does. */
static void call_handler(unsigned event, unsigned buttons, unsigned x,
                         unsigned y);
#pragma aux call_handler = \
    "push bp" \
    "push ds" \
    "xor si, si" \
    "xor di, di" \
    "call dword ptr handler" \
    "pop ds" \
    "pop bp" \
    parm [ax] [bx] [cx] [dx] \
    modify [ax bx cx dx si di es]

static unsigned char read_cmos(unsigned char index)
{
    outp(0x70, index);
    return inp(0x71);
}

static void write_cmos(unsigned char index, unsigned char value)
{
    outp(0x70, index);
    outp(0x71, value);
}

static void __interrupt __far int33(union INTPACK r)
{
    if (r.w.ax == 0x0c) {                       /* set event handler */
        handler = MK_FP(r.w.es, r.w.dx);
        mask = r.w.cx;
        if (next == 0)                          /* not clicked yet */
            countdown = events[0].wait;
    }
    _chain_intr(old33);
}

static void __interrupt __far rtc(void)
{
    unsigned event;

    read_cmos(0x0c);                            /* acknowledge it */
    outp(0xa0, 0x20);                           /* slave PIC */
    outp(0x20, 0x20);                           /* master PIC */
    if (countdown == 0 || --countdown)
        return;
    event = events[next].event & mask;
    if (event)
        call_handler(event, events[next].buttons, X, Y);
    if (++next < COUNT) {
        countdown = events[next].wait;
    } else {                                    /* done: restore the clock */
        write_cmos(0x0a, reg_a);
        write_cmos(0x0b, reg_b);
    }
}

int main(void)
{
    old33 = _dos_getvect(0x33);
    _dos_setvect(0x33, int33);
    _dos_setvect(0x70, rtc);                    /* the clock's IRQ8 */
    _disable();
    reg_a = read_cmos(0x0a) & 0x7f;             /* without update-in-progress */
    reg_b = read_cmos(0x0b);
    write_cmos(0x0a, 0x20 | RATE);              /* 32768 Hz time base */
    write_cmos(0x0b, reg_b | 0x40);             /* periodic interrupt on */
    read_cmos(0x0c);                            /* clear a pending one */
    outp(0xa1, inp(0xa1) & ~0x01);              /* unmask IRQ8 */
    outp(0x21, inp(0x21) & ~0x04);              /* and the cascade */
    _enable();
    _dos_keep(0, FP_SEG(&_STACKTOP) - _psp + (_STACKTOP + 15) / 16);
    return 0;
}
