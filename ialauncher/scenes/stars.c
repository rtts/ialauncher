/* Starfield Simulation for MS-DOS.

A simplified DOS version of starfield.py, running in 1024x768 with 256
colors on a VESA video card, playing Beethoven's Moonlight Sonata in 3
voices on the PC speaker.
*/

#include <conio.h>
#include <ctype.h>
#include <dos.h>
#include <i86.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>

#define WIDTH 1024
#define HEIGHT 768
#define VESA_MODE 0x105 /* WIDTH x HEIGHT, 256 colors */
#define VESA_OK 0x004F
#define BANK_SIZE 0x10000ul
#define BANK_LINES (unsigned)(BANK_SIZE / WIDTH)
#define PAGE_BANKS (HEIGHT / BANK_LINES)
#define PAGES 2
#define FPS 60
#define SPEED 10 /* seconds from z = 1 to z = 0 */
#define DEPTH (SPEED * FPS * 100u)
#define WARP 100u /* hundredths */
#define MAX_WARP 100u /* whole warps */
#define DENSITY 500u
#define MAX_DENSITY 5000u
#define CLUSTER 4
#define ESCAPE 27
#define INPUT_STATUS 0x3DA
#define RETRACE 0x08
#define DAC_WRITE 0x3C8
#define DAC_DATA 0x3C9
#define COLORS 256
#define TEXT_COLOR (COLORS - 1) /* white */
#define FONT_HEIGHT 16
#define BIOS_TICKS MK_FP(0x40, 0x6C) /* 18.2 per second since midnight */
#define COMMAND_TAIL MK_FP(_psp, 0x80)
#define MAX_ARGS 64
#define TIMER 8
#define TIMER_STACK 512
#define PIC 0x20
#define END_OF_INTERRUPT 0x20
#define PIT_CONTROL 0x43
#define PIT_COUNTER 0x40
#define PIT_SQUARE_WAVE 0x36
#define PIT_DIVISOR 64 /* 1193182 Hz / 64 = 18643 Hz, as in sonata.awk */
#define PIT_MILLISECOND 1193 /* 1193182 Hz / 1000 */
#define PIT_SPEAKER 0x42
#define PIT_SPEAKER_ONE_SHOT 0x90 /* channel 2, low byte only, mode 0 */
#define SPEAKER 0x61
#define SPEAKER_BITS 0x03 /* timer gate and speaker data */
#define PULSE_STEP ((PIT_DIVISOR - 4) / VOICES) /* shortest pulse is 1 */
#define PULSE_REST (PIT_DIVISOR + 8) /* low all tick, like before playing */
#define FULL_VOLUME 256
#define FADE_IN 10000L /* milliseconds */
#define LEAD_IN 2000 /* milliseconds of rest, while fading in to 20% */
#define VOICES 3
#define SUBPIXEL_BITS 4
#define SUBPIXELS (1 << SUBPIXEL_BITS) /* per pixel */
#define CLOCK 16 /* steps per millisecond */
#define ZOOM 2 /* stars grow from 1 pixel at z = 1 to 1 + ZOOM at z = 1/2 */
#define NEAREST (unsigned)(ZOOM * (unsigned long)DEPTH / (ZOOM + HEIGHT - 1))

#if VOICES != 3
#error The timer interrupt is unrolled for 3 voices
#endif

#include "sonata.h"

#define SONATA_LENGTH (sizeof sonata / sizeof *sonata)
#define SONATA_END (LEAD_IN + SONATA_MS)

/* Prevent "waves" of stars by filling up a the correct rate. */
#define TRAVELLED_NUM (2ul * CLUSTER * CLUSTER)
#define TRAVELLED_DEN ((CLUSTER + 1ul) * (2 * CLUSTER + 1))

/* A star with a fixed x and y, in SUBPIXELS per pixel, and a moving z. */
typedef struct {
    short x, y;
    unsigned short z;
    unsigned char color;
    unsigned char timed; /* arrives when the sonata ends */
} Star;

/* Where a star was drawn on a page, to erase it later. */
typedef struct {
    short left, top, size;
} Square;

/* The video card's own routine to select a bank of video memory, which
   takes the window in BX and the bank in DX. */
#pragma aux window_call __parm [__bx] [__dx] __modify __exact [__ax __bx __dx];
typedef void (__far WindowFunction)(unsigned short window, unsigned short n);
#pragma aux (window_call) WindowFunction;

/* The start of the VESA mode information, up to the number of pages. */
typedef struct {
    unsigned short attributes;
    unsigned char window_a, window_b;
    unsigned short granularity, window_size, segment_a, segment_b;
    WindowFunction *window_function;
    unsigned short pitch, width, height;
    unsigned char char_width, char_height, planes, bits, banks, model;
    unsigned char bank_size, pages;
    unsigned char reserved[226];
} ModeInfo;

static Star *stars;
static unsigned count;
static unsigned density = DENSITY;
static unsigned warp = WARP;
static unsigned long due, last_frame;
static unsigned leftover;
static char line[128];
static char *args[MAX_ARGS];
static ModeInfo mode_info;
static unsigned char __far *window;
static unsigned short bank = 0xFFFF; /* in the window */
static unsigned page; /* the one that's drawn on */
static Square *squares[PAGES];
static unsigned drawn[PAGES]; /* squares */
static void (__interrupt __far *bios_timer)(void);
static unsigned next_event, remaining;
static unsigned long now;
static unsigned char pulses[VOICES + 1];
static unsigned short bios_due, millisecond_due;
static unsigned short phases[VOICES], speeds[VOICES], lasting[VOICES];
static unsigned short interrupted_ss, interrupted_sp;
static unsigned char timer_stack[TIMER_STACK];
static const unsigned char __far *font; /* with /F */
static unsigned long second; /* when counting frames started */
static unsigned frames, rate;

/* Return the machine status word, whose bit 0 is set in protected mode. */
unsigned short smsw(void);
#pragma aux smsw = "smsw ax" value [ax];

/* Briefly enter protected mode and leave it again right away. */
void flip_pe(void);
#pragma aux flip_pe = \
    "cli" \
    "mov eax, cr0" \
    "or al, 1" \
    "mov cr0, eax" \
    "and al, 0xFE" \
    "mov cr0, eax" \
    "sti" \
    modify exact [ax];

/* Trick DOSBox into switching to a dynamic core with more cycles. */
static void boost(void)
{
    if (!(smsw() & 1)) flip_pe();
}

/* Replacement for malloc() to reduce file size (and to learn assembly!) */
unsigned short dos_alloc(unsigned short paragraphs);
#pragma aux dos_alloc = \
    "mov ah, 0x48" \
    "int 0x21" \
    "sbb dx, dx" \
    "not dx" \
    "and ax, dx" \
    parm [bx] \
    value [ax] \
    modify exact [ax bx dx];

/* Allocate a buffer of bytes from DOS, or return NULL. */
static void *allocate(unsigned bytes)
{
    unsigned short segment = dos_alloc((bytes + 15ul) >> 4);

    return segment ? MK_FP(segment, 0) : NULL;
}

/* Return the 8x16 font of the video BIOS. */
const unsigned char __far *rom_font(void);
#pragma aux rom_font = \
    "push bp" \
    "mov ax, 0x1130" \
    "mov bh, 6" \
    "int 0x10" \
    "mov dx, es" \
    "mov ax, bp" \
    "pop bp" \
    value [dx ax] \
    modify [ax bx cx dx es];

/* Switch to the given BIOS video mode. */
static void set_mode(unsigned short mode)
{
    union REGS regs;

    memset(&regs, 0, sizeof regs);
    regs.w.ax = mode;
    int86(0x10, &regs, &regs);
}

/* Switch to VESA_MODE, and return whether it has the layout we draw with:
   whole lines in every bank, room for all pages, and a routine of its own
   to select banks. Setting the mode clears video memory. */
static int set_vesa_mode(void)
{
    union REGS regs;
    struct SREGS sregs;

    segread(&sregs);
    regs.w.ax = 0x4F01;
    regs.w.cx = VESA_MODE;
    sregs.es = FP_SEG(&mode_info);
    regs.w.di = FP_OFF(&mode_info);
    int86x(0x10, &regs, &regs, &sregs);
    if (regs.w.ax != VESA_OK || mode_info.pitch != WIDTH
        || mode_info.granularity != BANK_SIZE / 1024
        || mode_info.pages + 1 < PAGES || !mode_info.window_function) {
        return 0;
    }
    window = MK_FP(mode_info.segment_a, 0);
    regs.w.ax = 0x4F02;
    regs.w.bx = VESA_MODE;
    int86(0x10, &regs, &regs);
    return regs.w.ax == VESA_OK;
}

/* Make color 0 black, TEXT_COLOR white, and give every other color a random
   value that isn't black, with less green: each bit of green is set a
   quarter of the time. */
static void set_palette(void)
{
    unsigned i, red, green, blue;

    outp(DAC_WRITE, 0);
    for (i = 0; i < 3; i++) outp(DAC_DATA, 0);
    for (i = 1; i < TEXT_COLOR; i++) {
        do {
            red = rand() & 63;
            green = rand() & rand() & 63;
            blue = rand() & 63;
        } while (!(red | green | blue));
        outp(DAC_DATA, red);
        outp(DAC_DATA, green);
        outp(DAC_DATA, blue);
    }
    for (i = 0; i < 3; i++) outp(DAC_DATA, 63);
}

/* Make a bank of video memory appear in the window, by calling the card
   directly instead of through the video BIOS. */
static void select_bank(unsigned short number)
{
    if (number == bank) return;
    bank = number;
    mode_info.window_function(0, number);
}

/* Return the milliseconds to wait before a note, since the one before it.
   A note has the index of its wait and length in 8 bits, the pitch in 6
   bits, and the voice in 2 bits. */
static unsigned wait_before(unsigned short note)
{
    return waits[note >> 8];
}

/* Play a note on its voice, for as long as it lasts. */
static void play_note(unsigned short note)
{
    unsigned char voice = note & 3;

    speeds[voice] = steps[note >> 2 & 63];
    lasting[voice] = lengths[note >> 8];
}

/* Stop the notes that end this millisecond. */
static void stop_notes(void)
{
    int voice;

    for (voice = 0; voice < VOICES; voice++) {
        if (lasting[voice] && !--lasting[voice]) {
            speeds[voice] = 0;
            phases[voice] = 0;
        }
    }
}

/* Set the volume, and the speaker pulse for every number of low voices:
   shorter the more voices are low, closer to rest the lower the volume. */
static void set_volume(unsigned level)
{
    int low;

    for (low = 0; low <= VOICES; low++) {
        pulses[low] = PULSE_REST + (1 + low * PULSE_STEP - PULSE_REST)
                                   * (int)level / FULL_VOLUME;
    }
}

/* Stop and play the notes that are due this millisecond. */
static void next_millisecond(void)
{
    stop_notes();
    while (next_event < SONATA_LENGTH && remaining == 0) {
        play_note(sonata[next_event]);
        if (++next_event < SONATA_LENGTH) {
            remaining = wait_before(sonata[next_event]);
        }
    }
    remaining--;
    now++;
    if (now <= FADE_IN) set_volume((unsigned)(now * FULL_VOLUME / FADE_IN));
}

/* Timer interrupt, 18643 times per second: move every voice along its
   square wave, pulse the speaker for as many voices as are low, play the
   notes every millisecond, and call the BIOS timer as often as it would be
   called normally. The C code that plays the notes expects SS to be DGROUP,
   so it runs on a stack of its own, in case DOS was using its stack. */
static void __declspec(naked) __interrupt __far play(void)
{
    _asm {
        push ax
        push bx
        push ds
        mov ax, seg phases
        mov ds, ax
        xor bx, bx
        mov ax, speeds
        add phases, ax
        js voice1
        inc bx
    voice1:
        mov ax, speeds + 2
        add phases + 2, ax
        js voice2
        inc bx
    voice2:
        mov ax, speeds + 4
        add phases + 4, ax
        js speaker
        inc bx
    speaker:
        mov al, pulses[bx]
        out PIT_SPEAKER, al
        add millisecond_due, PIT_DIVISOR
        cmp millisecond_due, PIT_MILLISECOND
        jb bios
        sub millisecond_due, PIT_MILLISECOND
        mov interrupted_ss, ss
        mov interrupted_sp, sp
        mov ax, ds
        mov ss, ax
        mov sp, offset timer_stack + TIMER_STACK
        pushad
        push es
        push fs
        push gs
        cld
        call next_millisecond
        pop gs
        pop fs
        pop es
        popad
        push ss
        pop ds
        mov ss, interrupted_ss
        mov sp, interrupted_sp
    bios:
        add bios_due, PIT_DIVISOR
        jnc acknowledge
        pushf
        call dword ptr bios_timer
        jmp done
    acknowledge:
        mov al, END_OF_INTERRUPT
        out PIC, al
    done:
        pop ds
        pop bx
        pop ax
        iret
    }
}

/* Set the rate of the timer interrupt. */
static void set_timer(unsigned short divisor)
{
    _disable();
    outp(PIT_CONTROL, PIT_SQUARE_WAVE);
    outp(PIT_COUNTER, divisor & 0xFF);
    outp(PIT_COUNTER, divisor >> 8);
    _enable();
}

/* Start playing the sonata from the beginning. */
static void start_music(void)
{
    set_volume(0);
    outp(PIT_CONTROL, PIT_SPEAKER_ONE_SHOT);
    outp(PIT_SPEAKER, PULSE_REST);
    outp(SPEAKER, inp(SPEAKER) | SPEAKER_BITS);
    next_event = 0;
    remaining = LEAD_IN + wait_before(sonata[0]);
    bios_timer = _dos_getvect(TIMER);
    _dos_setvect(TIMER, play);
    set_timer(PIT_DIVISOR);
}

/* Stop playing, and give the timer back to the BIOS. */
static void stop_music(void)
{
    set_timer(0);
    _dos_setvect(TIMER, bios_timer);
    outp(SPEAKER, inp(SPEAKER) & ~SPEAKER_BITS);
}

/* Return how long the sonata has played, in milliseconds times CLOCK. */
static unsigned long played(void)
{
    unsigned long ms;
    unsigned short due;

    _disable();
    ms = now;
    due = millisecond_due;
    _enable();
    return ms * CLOCK + due * CLOCK / PIT_MILLISECOND;
}

/* Return a * b / c rounded down, for c > 0 */
long muldiv(short a, unsigned short b, unsigned short c);
#pragma aux muldiv = \
    "movsx eax, ax" \
    "movzx ebx, bx" \
    "movzx ecx, cx" \
    "imul eax, ebx" \
    "cdq" \
    "idiv ecx" \
    "sar edx, 31" /* -1 if the remainder is negative */ \
    "add eax, edx" \
    "shld edx, eax, 16" \
    parm [ax] [bx] [cx] \
    value [dx ax] \
    modify exact [ax bx cx dx];

/* Return a whole number between -half and half, more often near 0 for
   higher CLUSTER. */
static short clustered(int half)
{
    int distance = RAND_MAX, u;
    unsigned i;
    short n;

    for (i = 0; i < CLUSTER; i++) {
        u = rand();
        if (u < distance) distance = u;
    }
    n = (short)((2L * half * distance + RAND_MAX + 1) / (2 * (RAND_MAX + 1L)));
    return rand() <= RAND_MAX / 2 ? -n : n;
}

/* Return a color that isn't black or TEXT_COLOR. */
static unsigned char random_color(void)
{
    return 1 + rand() % (COLORS - 2);
}

/* Return a new star at depth z = 1 */
static Star star(void)
{
    Star s;

    s.x = clustered(WIDTH / 2 * SUBPIXELS);
    s.y = clustered(HEIGHT / 2 * SUBPIXELS);
    s.z = DEPTH;
    s.color = random_color();
    s.timed = 0;
    return s;
}

/* Fill a rectangle with a color on the page that's drawn on. */
static void fill(int left, int top, int width, int height, unsigned char color)
{
    int right = left + width, bottom = top + height;
    unsigned y;

    if (left < 0) left = 0;
    if (top < 0) top = 0;
    if (right > WIDTH) right = WIDTH;
    if (bottom > HEIGHT) bottom = HEIGHT;
    if (left >= right || top >= bottom) return;

    for (y = top; y < bottom; y++) {
        select_bank(page * PAGE_BANKS + y / BANK_LINES);
        memset(window + y % BANK_LINES * WIDTH + left, color, right - left);
    }
}

/* Erase the squares that were drawn on the page before. */
static void erase(void)
{
    Square *square = squares[page];
    unsigned i;

    for (i = 0; i < drawn[page]; i++, square++) {
        fill(square->left, square->top, square->size, square->size, 0);
    }
    drawn[page] = 0;
}

/* Draw a star, and remember where to erase it later. */
static void draw(int left, int top, int width, int height, unsigned char color)
{
    Square *square = &squares[page][drawn[page]++];

    square->left = left;
    square->top = top;
    square->size = width > height ? width : height;
    fill(left, top, width, height, color);
}

/* Return a position in SUBPIXELS rounded to whole pixels. */
static int pixel(long position)
{
    return (int)(position + SUBPIXELS / 2) >> SUBPIXEL_BITS;
}

/* Return how many stars to add after travelling a distance, so that the
   field fills up at the correct rate. */
static unsigned arrivals(unsigned distance)
{
    unsigned n = 0, step;

    while (distance > 0) {
        step = distance < MAX_WARP * 100 ? distance : MAX_WARP * 100;
        due += (unsigned long)density * step * TRAVELLED_DEN;
        n += (unsigned)(due / (TRAVELLED_NUM * DEPTH));
        due %= TRAVELLED_NUM * DEPTH;
        distance -= step;
    }
    return n;
}

/* Fly through space by a distance, drawing the stars on the page.
   Return whether we collided with a star. */
static int update(unsigned distance)
{
    unsigned i, first = count, kept, gone = 0, n;
    long left, top, size;
    int x, y;
    Star s;

    erase();

    /* Each star is a point in space, at a fixed x and y that put it
       anywhere on the screen at depth z = 1, mostly near the center,
       and moves toward the viewer at z = 0 at the same speed, however
       long a frame takes. Dividing x and y by z projects it onto the
       screen, and its size grows with 1 / z, faster for a higher ZOOM,
       both in SUBPIXELS, so that its edges round to whole pixels the same
       way. Newer stars are further away, so they're drawn first. */
    for (i = count; i-- > 0;) {
        s = stars[i];
        if (s.z - NEAREST <= distance) {
            if (s.timed) {
                /* Collision! The star fills the screen. */
                fill(0, 0, WIDTH, HEIGHT, s.color);
                return 1;
            }
            gone++;
            continue;
        }
        s.z -= distance;
        size = SUBPIXELS
               + ZOOM * SUBPIXELS * (unsigned long)(DEPTH - s.z) / s.z;
        left = WIDTH / 2 * SUBPIXELS - size / 2 + muldiv(s.x, DEPTH, s.z);
        top = HEIGHT / 2 * SUBPIXELS - size / 2 + muldiv(s.y, DEPTH, s.z);
        if (!(-size < left && left < WIDTH * SUBPIXELS
              && -size < top && top < HEIGHT * SUBPIXELS)) {
            gone++;
            continue;
        }
        stars[--first] = s;
        x = pixel(left);
        y = pixel(top);
        draw(x, y, pixel(left + size) - x, pixel(top + size) - y, s.color);
    }
    kept = count - first;
    memmove(stars, stars + first, kept * sizeof *stars);

    /* Replace stars that left and add more until field is full. */
    n = arrivals(distance);
    if (gone < n) gone = n;
    if (gone > density - kept) gone = density - kept;
    for (i = 0; i < gone; i++) {
        stars[kept++] = star();
    }
    count = kept;
    return 0;
}

/* Add a star in the exact center, the only one you can collide with. */
static void center_star(void)
{
    Star s = {0, 0, DEPTH};

    s.color = random_color();
    s.timed = 1;
    if (count < density) {
        stars[count++] = s;
    } else if (count > 0) {
        stars[count - 1] = s;
    }
}

/* Return how far the stars travel from the last frame to the moment the
   sonata has played until, so that they keep time with the music. */
static unsigned travel(unsigned long moment)
{
    unsigned long units = (moment - last_frame) * warp;

    last_frame = moment;
    if (units >= 1000ul * CLOCK * DEPTH / FPS) {
        leftover = 0;
        return DEPTH;
    }
    units = units * FPS + leftover;
    leftover = (unsigned)(units % (1000ul * CLOCK));
    return (unsigned)(units / (1000ul * CLOCK));
}

/* Return whether it's time for the center star to set out, so that it
   arrives around when the sonata ends. */
static int time_to_launch(unsigned long moment)
{
    unsigned long journey = (DEPTH - NEAREST) * 1000ul * CLOCK
                            / ((unsigned long)warp * FPS);

    return moment + journey >= SONATA_END * CLOCK;
}

/* Handle Esc. */
static int escape(void)
{
    int pressed = 0;

    while (kbhit()) {
        switch (getch()) {
        case 0: /* extended key, skip its scan code */
            getch();
            break;
        case ESCAPE:
            pressed = 1;
            break;
        }
    }
    return pressed;
}

/* Wait for the start of a vertical retrace. */
static void wait_retrace(void)
{
    while (inp(INPUT_STATUS) & RETRACE);
    while (!(inp(INPUT_STATUS) & RETRACE));
}

/* Show the page that was drawn, and draw on the other one. The card takes
   the new start address at the start of a vertical retrace. */
static void flip(void)
{
    union REGS regs;

    regs.w.ax = 0x4F07;
    regs.w.bx = 0;
    regs.w.cx = 0;
    regs.w.dx = page * HEIGHT;
    int86(0x10, &regs, &regs);
    wait_retrace();
    page = 1 - page;
}

/* Count a frame that was just shown, and how many were shown each second. */
static void count_frame(void)
{
    unsigned long moment = played();

    frames++;
    if (moment - second >= 1000ul * CLOCK) {
        rate = (unsigned)((frames * 1000ul * CLOCK + (moment - second) / 2)
                          / (moment - second));
        frames = 0;
        second = moment;
    }
}

/* Write a number right-aligned in a field of characters. */
static void number(char *field, unsigned width, unsigned n)
{
    char *p = field + width;

    do {
        *--p = '0' + n % 10;
        n /= 10;
    } while (n && p > field);
    while (p > field) *--p = ' ';
}

/* Write text in TEXT_COLOR on black on the page that's drawn on. */
static void write_text(int left, int top, const char *text)
{
    unsigned char __far *dot;
    unsigned char bits, bit;
    const char *c;
    int row;

    for (row = top; row < top + FONT_HEIGHT; row++) {
        select_bank(page * PAGE_BANKS + row / BANK_LINES);
        dot = window + row % BANK_LINES * WIDTH + left;
        for (c = text; *c; c++) {
            bits = font[(unsigned char)*c * FONT_HEIGHT + row - top];
            for (bit = 0x80; bit; bit >>= 1) {
                *dot++ = bits & bit ? TEXT_COLOR : 0;
            }
        }
    }
}

/* Show the frame rate at the top left. */
static void show_rate(void)
{
    static char text[] = "000 FPS";

    number(text, 3, rate);
    write_text(FONT_HEIGHT, FONT_HEIGHT, text);
}

/* Write a character to standard output, ending lines with CR LF. */
static void put(char c)
{
    union REGS regs;

    if (c == '\n') put('\r');
    regs.h.ah = 0x02;
    regs.h.dl = c;
    int86(0x21, &regs, &regs);
}

/* Write a number to standard output. */
static void put_unsigned(unsigned n)
{
    if (n >= 10) put_unsigned(n / 10);
    put('0' + n % 10);
}

/* Like printf(), but only has %s and %u */
static void print(const char *format, ...)
{
    va_list args;
    const char *s;

    va_start(args, format);
    for (; *format; format++) {
        if (*format != '%') {
            put(*format);
        } else if (*++format == 's') {
            for (s = va_arg(args, const char *); *s; s++) put(*s);
        } else {
            put_unsigned(va_arg(args, unsigned));
        }
    }
    va_end(args);
}

/* Show help message. */
static void help(void)
{
    print("Starfield Simulation for MS-DOS, by Jaap Joris Vens.\n"
          "\n"
          "STARS [/D density] [/W warp] [/F]\n"
          "\n"
          "  /D  Number of stars (default %u)\n"
          "  /W  Warp speed, 1 to %u (default %u.%u)\n"
          "  /F  Show the frame rate\n"
          "  /H  Show this help\n",
          DENSITY, MAX_WARP, WARP / 100, WARP / 10 % 10);
}

/* Show error message. */
static void fail(const char *message, const char *arg)
{
    print("%s: %s\nType STARS /H for help.\n", message, arg);
    exit(1);
}

/* Read a number like strtod() does, ignoring digits after the hundredths. */
static long decimal(const char *value, char **end, long *divisor)
{
    const char *p = value;
    long number = 0;
    int digits = 0, negative = 0;

    *divisor = 1;
    if (*p == '-' || *p == '+') negative = *p++ == '-';
    for (; isdigit(*p); p++, digits++) {
        number = number * 10 + (*p - '0');
    }
    if (*p == '.') {
        for (p++; isdigit(*p); p++, digits++) {
            if (*divisor == 100) continue;
            number = number * 10 + (*p - '0');
            *divisor *= 10;
        }
    }
    *end = (char *)(digits ? p : value);
    return negative ? -number : number;
}

/* Split the command line into args[1] onward, and return how many args there
   are. Not using the argv of main(), because it brings in malloc(). */
static int split(void)
{
    const unsigned char __far *tail = COMMAND_TAIL;
    char *p = line;
    int argc = 1, i;

    for (i = 0; i < tail[0] && i < sizeof line - 1; i++) {
        line[i] = tail[1 + i];
    }
    line[i] = '\0';
    while (argc < MAX_ARGS) {
        while (*p == ' ' || *p == '\t') *p++ = '\0';
        if (*p == '\0') break;
        args[argc++] = p;
        while (*p != '\0' && *p != ' ' && *p != '\t') p++;
    }
    return argc;
}

/* Parse command-line arguments. */
static void parse(int argc, char *argv[])
{
    int i;
    long number, divisor;
    char option, *value, *end;

    for (i = 1; i < argc; i++) {
        if (argv[i][0] != '/' && argv[i][0] != '-') {
            fail("Invalid argument", argv[i]);
        }
        option = tolower(argv[i][1]);
        if (option == 'h' || option == '?') {
            help();
            exit(0);
        }
        if (option == 'f') {
            font = rom_font();
            continue;
        }
        if (option != 'd' && option != 'w') {
            fail("Invalid switch", argv[i]);
        }
        value = argv[i] + 2;
        if (*value == ':') value++;
        if (*value == '\0') {
            if (i + 1 == argc) fail("Missing value for", argv[i]);
            value = argv[++i];
        }
        if (option == 'd') {
            number = strtol(value, &end, 10);
        } else {
            number = decimal(value, &end, &divisor);
            if (number < divisor) number = divisor;
            if (number > MAX_WARP * divisor) number = MAX_WARP * divisor;
            warp = (unsigned)(number * 100 / divisor);
        }
        if (end == value || *end != '\0') {
            fail("Invalid number", value);
        }
        if (option == 'd') {
            if (number > MAX_DENSITY) {
                print("Too many stars, the maximum is %u.\n", MAX_DENSITY);
                exit(1);
            }
            density = number < 0 ? 0 : (unsigned)number;
        }
    }
}

/* Main entry point. */
int main(void)
{
    int collided = 0, launched = 0;
    unsigned long moment;
    unsigned distance;

    parse(split(), args);
    /* One spare, so there's no asking DOS for nothing. */
    stars = allocate((density + 1) * sizeof *stars);
    for (page = 0; page < PAGES; page++) {
        squares[page] = allocate((density + 1) * sizeof *squares[page]);
        if (squares[page] == NULL) stars = NULL;
    }
    if (stars == NULL) {
        print("Not enough memory for %u stars.\n", density);
        return 1;
    }
    srand(*(unsigned __far *)BIOS_TICKS); /* Seed from BIOS. */
    boost();
    if (!set_vesa_mode()) {
        print("This needs a VESA video card with 1024x768 in 256 colors.\n");
        return 1;
    }
    set_palette();
    page = 1;
    start_music();
    while (!collided && !escape()) {
        moment = played();
        distance = travel(moment);
        if (!launched && time_to_launch(moment)) {
            center_star();
            launched = 1;
        }
        collided = update(distance);
        if (font && !collided) show_rate();
        flip();
        if (font) count_frame();
    }
    stop_music();
    if (collided) delay(100);
    set_mode(0x03);
    return 0;
}
