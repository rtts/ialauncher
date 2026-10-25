/* Starfield Simulation for MS-DOS.

A simplified DOS version of starfield.py, running in VGA mode 12h.
*/

#include <conio.h>
#include <ctype.h>
#include <i86.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>

#define WIDTH 640
#define HEIGHT 480
#define PITCH (WIDTH / 8u)
#define SCREEN_SIZE (PITCH * HEIGHT)
#define FPS 60
#define SPEED 10 /* seconds from z = 1 to z = 0 */
#define DEPTH (SPEED * FPS * 100u)
#define WARP 100u /* hundredths */
#define MAX_WARP 100u /* whole warps */
#define DENSITY 500u
#define MAX_DENSITY 5000u
#define CLUSTER 4
#define ESCAPE 27
#define SPACE ' '
#define INPUT_STATUS 0x3DA
#define RETRACE 0x08
#define SEQUENCER 0x3C4
#define MAP_MASK 0x02
#define PLANES 4
#define BIOS_TICKS MK_FP(0x40, 0x6C) /* 18.2 per second since midnight */
#define COMMAND_TAIL MK_FP(_psp, 0x80)
#define MAX_ARGS 64
#define RETRACES_PER_FRAME (60 / FPS)

/* Prevent "waves" of stars by filling up a the correct rate. */
#define TRAVELLED_NUM (2ul * CLUSTER * CLUSTER)
#define TRAVELLED_DEN ((CLUSTER + 1ul) * (2 * CLUSTER + 1))

/* A star with a fixed x and y and a moving z. */
typedef struct {
    short x, y;
    unsigned short z;
    unsigned char color;
} Star;

/* Colors resembling the title screens. */
static const struct {
    unsigned char red, green, blue;
} PALETTE[1 << PLANES] = {
    {0, 0, 0},    {8, 7, 18},   {8, 9, 36},   {18, 15, 24},
    {31, 12, 9},  {24, 22, 19}, {24, 22, 39}, {49, 0, 0},
    {45, 17, 24}, {43, 17, 45}, {17, 31, 45}, {21, 35, 18},
    {33, 37, 38}, {17, 44, 45}, {45, 44, 17}, {47, 48, 47},
};

static Star *stars;
static unsigned count;
static unsigned density = DENSITY;
static unsigned warp = WARP;
static unsigned long due;
static unsigned char *planes[PLANES];
static char line[128];
static char *args[MAX_ARGS];
static unsigned char __far *const vga = MK_FP(0xA000, 0);

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

/* Switch to the given BIOS video mode. */
static void set_mode(unsigned short mode)
{
    union REGS regs;

    memset(&regs, 0, sizeof regs);
    regs.w.ax = mode;
    int86(0x10, &regs, &regs);
}

/* Load PALETTE into the VGA. */
static void set_palette(void)
{
    union REGS regs;
    unsigned char i;

    for (i = 0; i < 1 << PLANES; i++) {
        /* Use DAC register i for color i, instead of the EGA mapping. */
        regs.w.ax = 0x1000;
        regs.h.bl = i;
        regs.h.bh = i;
        int86(0x10, &regs, &regs);
        regs.w.ax = 0x1010;
        regs.w.bx = i;
        regs.h.dh = PALETTE[i].red;
        regs.h.ch = PALETTE[i].green;
        regs.h.cl = PALETTE[i].blue;
        int86(0x10, &regs, &regs);
    }
}

/* Divide by a positive number, rounding down instead of toward zero. */
static long floor_div(long a, long b)
{
    return (a < 0 ? a - b + 1 : a) / b;
}

/* Return a * b / c rounded down, for c > 0, like floor_div() */
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
    long offset;

    for (i = 0; i < CLUSTER; i++) {
        u = rand();
        if (u < distance) distance = u;
    }
    offset = 2L * half * distance;
    if (rand() <= RAND_MAX / 2) offset = -offset;
    return (short)floor_div(offset + RAND_MAX + 1, 2 * (RAND_MAX + 1L));
}

/* Return a non-black color. */
static unsigned char random_color(void)
{
    return 1 + rand() % ((1 << PLANES) - 1);
}

/* Return a new star at depth z = 1 */
static Star star(void)
{
    Star s;

    /* Whole pixels, so there's a chance you collide
       with the star when both happen to be zero. */
    s.x = clustered(WIDTH / 2);
    s.y = clustered(HEIGHT / 2);
    s.z = DEPTH;
    s.color = random_color();
    return s;
}

/* Draw a square in the given color. */
static void fill(int left, int top, int size, unsigned char color)
{
    int right = left + size, bottom = top + size;
    unsigned x, y, first, last, offset, plane;
    unsigned char head, tail, mask;

    if (left < 0) left = 0;
    if (top < 0) top = 0;
    if (right > WIDTH) right = WIDTH;
    if (bottom > HEIGHT) bottom = HEIGHT;
    if (left >= right || top >= bottom) return;

    /* Work a byte (8 pixels) at a time, masking the partial ends. */
    first = left >> 3;
    last = (right - 1) >> 3;
    head = 0xFF >> (left & 7);
    tail = 0xFF << (7 - ((right - 1) & 7));
    for (y = top; y < bottom; y++) {
        for (x = first; x <= last; x++) {
            mask = 0xFF;
            if (x == first) mask &= head;
            if (x == last) mask &= tail;
            offset = y * PITCH + x;
            for (plane = 0; plane < PLANES; plane++) {
                if (color >> plane & 1) {
                    planes[plane][offset] |= mask;
                } else {
                    planes[plane][offset] &= ~mask;
                }
            }
        }
    }
}

/* Fly through space. Return whether we collided with a star. */
static int update(void)
{
    unsigned i, first = count, kept, gone = 0, n, plane;
    int size;
    long left, top;
    Star s;

    for (plane = 0; plane < PLANES; plane++) {
        memset(planes[plane], 0, SCREEN_SIZE);
    }

    /* Each star is a point in space, at a fixed x and y that put it
       anywhere on the screen at depth z = 1, mostly near the center,
       and moves toward the viewer at z = 0 by the same distance every
       frame. Dividing x and y by z projects it onto the screen.
       Newer stars are further away, so they're drawn first. */
    for (i = count; i-- > 0;) {
        s = stars[i];
        if (s.z - DEPTH / HEIGHT <= warp) {
            if (s.x == 0 && s.y == 0) {
                /* Collision! The star fills the screen. */
                for (plane = 0; plane < PLANES; plane++) {
                    memset(planes[plane], s.color >> plane & 1 ? 0xFF : 0,
                           SCREEN_SIZE);
                }
                return 1;
            }
            gone++;
            continue;
        }
        s.z -= warp;
        size = DEPTH / s.z;
        left = WIDTH / 2 - size / 2 + muldiv(s.x, DEPTH, s.z);
        top = HEIGHT / 2 - size / 2 + muldiv(s.y, DEPTH, s.z);
        if (!(-size < left && left < WIDTH && -size < top && top < HEIGHT)) {
            gone++;
            continue;
        }
        stars[--first] = s;
        fill((int)left, (int)top, size, s.color);
    }
    kept = count - first;
    memmove(stars, stars + first, kept * sizeof *stars);

    /* Replace stars that left and add more until field is full. */
    due += (unsigned long)density * warp * TRAVELLED_DEN;
    n = (unsigned)(due / (TRAVELLED_NUM * DEPTH));
    due %= TRAVELLED_NUM * DEPTH;
    if (gone < n) gone = n;
    if (gone > density - kept) gone = density - kept;
    for (i = 0; i < gone; i++) {
        stars[kept++] = star();
    }
    count = kept;
    return 0;
}

/* Add a star in the exact center. */
static void center_star(void)
{
    Star s = {0, 0, DEPTH};

    s.color = random_color();
    if (count < density) {
        stars[count++] = s;
    } else if (count > 0) {
        stars[count - 1] = s;
    }
}

/* Handle Space and Esc. */
static int escape(void)
{
    int pressed = 0;

    while (kbhit()) {
        switch (getch()) {
        case 0: /* extended key, skip its scan code */
            getch();
            break;
        case SPACE:
            center_star();
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
          "STARS [/D density] [/W warp]\n"
          "\n"
          "  /D  Number of stars (default %u)\n"
          "  /W  Warp speed, 1 to %u (default %u.%u)\n"
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
    unsigned i;
    int collided = 0, plane;

    parse(split(), args);
    /* One spare, so there's no asking DOS for nothing. */
    stars = allocate((density + 1) * sizeof *stars);
    for (plane = 0; plane < PLANES; plane++) {
        planes[plane] = allocate(SCREEN_SIZE);
        if (planes[plane] == NULL) stars = NULL;
    }
    if (stars == NULL) {
        print("Not enough memory for %u stars.\n", density);
        return 1;
    }
    srand(*(unsigned __far *)BIOS_TICKS); /* Seed from BIOS. */
    boost();
    set_mode(0x12);
    set_palette();
    while (!collided && !escape()) {
        collided = update();
        for (i = 0; i < RETRACES_PER_FRAME; i++) {
            wait_retrace();
        }
        for (plane = 0; plane < PLANES; plane++) {
            outpw(SEQUENCER, (1 << plane) << 8 | MAP_MASK);
            memcpy(vga, planes[plane], SCREEN_SIZE);
        }
    }
    if (collided) delay(100);
    set_mode(0x03);
    return 0;
}
