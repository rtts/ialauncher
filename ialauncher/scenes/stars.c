/* Starfield Simulation for MS-DOS.

A simplified DOS version of starfield.py, running in VGA mode 12h.
*/

#include <conio.h>
#include <ctype.h>
#include <i86.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define WIDTH 640
#define HEIGHT 480
#define PITCH (WIDTH / 8u)
#define SCREEN_SIZE (PITCH * HEIGHT)
#define FPS 60
#define SPEED 10 /* seconds from z = 1 to z = 0 */
#define WARP 1.0f
#define DENSITY 500u
#define MAX_DENSITY 5000u /* 10 bytes each, malloc can't exceed 64 KB */
#define CLUSTER 4
#define ESCAPE 27
#define SPACE ' '
#define INPUT_STATUS 0x3DA
#define RETRACE 0x08
#define SEQUENCER 0x3C4
#define MAP_MASK 0x02
#define PLANES 4
#define BIOS_TICKS MK_FP(0x40, 0x6C) /* 18.2 per second since midnight */
#define RETRACES_PER_FRAME (60 / FPS)
#define FLOOR(f) ((long)(f) - ((f) < (long)(f)))
#define TRAVELLED \
    (1 - 2.0f / (CLUSTER + 1) + 1.0f / (2 * CLUSTER + 1))

/* A star with a fixed x and y and a moving z. */
typedef struct {
    short x, y;
    float z;
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
static float warp = WARP;
static float due;
static unsigned char *planes[PLANES]; /* allocated, or they'd be in the .exe */
static unsigned char __far *const vga = MK_FP(0xA000, 0);

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

/* Return a random number from 0 up to, but not including, 1. */
static float uniform(void)
{
    return rand() / (RAND_MAX + 1.0f);
}

/* Return a number between -1 and 1, near 0 more often for higher CLUSTER. */
static float clustered(void)
{
    float distance = 1, u;
    unsigned i;

    for (i = 0; i < CLUSTER; i++) {
        u = uniform();
        if (u < distance) distance = u;
    }
    return uniform() < 0.5f ? -distance : distance;
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
    float x = clustered() * WIDTH / 2 + 0.5f;
    float y = clustered() * HEIGHT / 2 + 0.5f;

    /* Round x and y to whole pixels, so there's a chance you
       collide with the star when both happen to be zero. */
    s.x = (short)FLOOR(x);
    s.y = (short)FLOOR(y);
    s.z = 1;
    s.color = random_color();
    return s;
}

/* Draw a square in the given color. */
static void fill(int left, int top, int size, unsigned char color)
{
    int right = left + size, bottom = top + size;
    int x, y, plane;
    unsigned char *row, bit;

    if (left < 0) left = 0;
    if (top < 0) top = 0;
    if (right > WIDTH) right = WIDTH;
    if (bottom > HEIGHT) bottom = HEIGHT;
    for (plane = 0; plane < PLANES; plane++) {
        for (y = top; y < bottom; y++) {
            row = planes[plane] + y * PITCH;
            for (x = left; x < right; x++) {
                bit = 0x80 >> (x & 7);
                if (color >> plane & 1) {
                    row[x >> 3] |= bit;
                } else {
                    row[x >> 3] &= ~bit;
                }
            }
        }
    }
}

/* Fly through space. Return whether we collided with a star. */
static int update(void)
{
    const float step = warp / (SPEED * FPS);
    /* Filling at this rate prevents "waves" of stars. */
    const float rate = density * step / TRAVELLED;
    unsigned i, first = count, kept, gone = 0, n, plane;
    int size;
    float scale, left, top;
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
        s.z -= step;
        if (s.z <= 1.0f / HEIGHT) {
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
        scale = 1 / s.z;
        size = (int)scale;
        left = WIDTH / 2 - size / 2 + s.x * scale;
        top = HEIGHT / 2 - size / 2 + s.y * scale;
        if (!(-size < left && left < WIDTH && -size < top && top < HEIGHT)) {
            gone++;
            continue;
        }
        stars[--first] = s;
        fill((int)FLOOR(left), (int)FLOOR(top), size, s.color);
    }
    kept = count - first;
    memmove(stars, stars + first, kept * sizeof *stars);

    /* Replace stars that left and add more until field is full. */
    due += rate;
    n = (unsigned)due;
    due -= n;
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
    Star s = {0, 0, 1};

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

/* Show help message. */
static void help(void)
{
    printf("Starfield Simulation for MS-DOS, by Jaap Joris Vens.\n"
           "\n"
           "STARS [/D density] [/W warp]\n"
           "\n"
           "  /D  Number of stars (default %u)\n"
           "  /W  Warp speed, 1 or more (default %u.%u)\n"
           "  /H  Show this help\n",
           DENSITY, (unsigned)WARP, (unsigned)(WARP * 10) % 10);
}

/* Show error message. */
static void fail(const char *message, const char *arg)
{
    printf("%s: %s\nType STARS /H for help.\n", message, arg);
    exit(1);
}

/* Read a number like strtod() does. */
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
            number = number * 10 + (*p - '0');
            *divisor *= 10;
        }
    }
    *end = (char *)(digits ? p : value);
    return negative ? -number : number;
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
            warp = (float)number / divisor;
        }
        if (end == value || *end != '\0') {
            fail("Invalid number", value);
        }
        if (option == 'd') {
            if (number > MAX_DENSITY) {
                printf("Too many stars, the maximum is %u.\n", MAX_DENSITY);
                exit(1);
            }
            density = number < 0 ? 0 : (unsigned)number;
        }
    }
    if (!(warp >= 1)) warp = 1;
}

/* Main entry point. */
int main(int argc, char *argv[])
{
    unsigned i;
    int collided = 0, plane;

    parse(argc, argv);
    /* One spare, because malloc(0) may return NULL. */
    stars = malloc((density + 1) * sizeof *stars);
    for (plane = 0; plane < PLANES; plane++) {
        planes[plane] = malloc(SCREEN_SIZE);
        if (planes[plane] == NULL) stars = NULL;
    }
    if (stars == NULL) {
        printf("Not enough memory for %u stars.\n", density);
        return 1;
    }
    srand(*(unsigned __far *)BIOS_TICKS); /* Seed from BIOS. */
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
