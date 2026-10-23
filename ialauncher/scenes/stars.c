/* Starfield Simulation for MS-DOS.

A simplified DOS version of starfield.py, running in VGA mode 11h.
*/

#include <conio.h>
#include <ctype.h>
#include <i86.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define WIDTH 640
#define HEIGHT 480
#define PITCH (WIDTH / 8u)
#define SCREEN_SIZE (PITCH * HEIGHT)
#define FPS 60
#define SPEED 10 /* seconds from z = 1 to z = 0 */
#define WARP 1.0f
#define DENSITY 500u
#define MAX_DENSITY 5000u /* 12 bytes each, malloc can't exceed 64 KB */
#define CLUSTER 4
#define ESCAPE 27
#define INPUT_STATUS 0x3DA
#define RETRACE 0x08
#define RETRACES_PER_FRAME (60 / FPS)
#define TRAVELLED \
    (1 - 2.0f / (CLUSTER + 1) + 1.0f / (2 * CLUSTER + 1))

/* A star with a fixed x and y and a moving z. */
typedef struct {
    float x, y, z;
} Star;

static Star *stars;
static unsigned count;
static unsigned density = DENSITY;
static float warp = WARP;
static float due;
static unsigned char *buffer; /* allocated, or it would be in the .exe */
static unsigned char __far *const vga = MK_FP(0xA000, 0);

static void set_mode(unsigned short mode)
{
    union REGS regs;

    memset(&regs, 0, sizeof regs);
    regs.w.ax = mode;
    int86(0x10, &regs, &regs);
}

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

/* Return a new star at depth z = 1. */
static Star star(void)
{
    Star s;

    /* Round x and y to whole pixels, so there's a chance you
       collide with the star when both happen to be zero. */
    s.x = floor(clustered() * WIDTH + 0.5f) / 2;
    s.y = floor(clustered() * HEIGHT + 0.5f) / 2;
    s.z = 1;
    return s;
}

/* Draw a white square, clipped to the screen. */
static void fill(int left, int top, int size)
{
    int right = left + size, bottom = top + size;
    int x, y;
    unsigned char *row;

    if (left < 0) left = 0;
    if (top < 0) top = 0;
    if (right > WIDTH) right = WIDTH;
    if (bottom > HEIGHT) bottom = HEIGHT;
    for (y = top; y < bottom; y++) {
        row = buffer + y * PITCH;
        for (x = left; x < right; x++) {
            row[x >> 3] |= 0x80 >> (x & 7);
        }
    }
}

/* Fly through space. Return whether we collided with a star. */
static int update(void)
{
    const float step = warp / (SPEED * FPS);
    /* Filling at this rate prevents "waves" of stars. */
    const float rate = density * step / TRAVELLED;
    unsigned i, kept = 0, gone = 0, n;
    int size;
    float scale, left, top;
    Star s;

    memset(buffer, 0, SCREEN_SIZE);

    /* Each star is a point in space, at a fixed x and y that put it
       anywhere on the screen at depth z = 1, mostly near the center,
       and moves toward the viewer at z = 0 by the same distance every
       frame. Dividing x and y by z projects it onto the screen. */
    for (i = 0; i < count; i++) {
        s = stars[i];
        s.z -= step;
        if (s.z <= 1.0f / HEIGHT) {
            if (s.x == 0 && s.y == 0) {
                return 1; /* Collision! */
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
        stars[kept++] = s;
        fill((int)floor(left), (int)floor(top), size);
    }

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

/* Return whether Esc was pressed, emptying the keyboard buffer. */
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

static void help(void)
{
    printf("Starfield Simulation for MS-DOS, by Jaap Joris Vens.\n"
           "\n"
           "STARS [/D density] [/W warp]\n"
           "\n"
           "  /D  Number of stars (default %u)\n"
           "  /W  Warp speed, 1 or more (default %.1f)\n"
           "  /H  Show this help\n",
           DENSITY, WARP);
}

static void fail(const char *message, const char *arg)
{
    printf("%s: %s\nType STARS /H for help.\n", message, arg);
    exit(1);
}

/* Read options given as /D 500, /D500 or /D:500, in any case. */
static void parse(int argc, char *argv[])
{
    int i;
    long number;
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
            warp = (float)strtod(value, &end);
        }
        if (end == value || *end != '\0') {
            fail("Invalid number", value);
        }
        if (option == 'd') {
            /* Check before converting, a 16-bit unsigned would wrap. */
            if (number > MAX_DENSITY) {
                printf("Too many stars, the maximum is %u.\n", MAX_DENSITY);
                exit(1);
            }
            density = number < 0 ? 0 : (unsigned)number;
        }
    }
    if (!(warp >= 1)) warp = 1;
}

int main(int argc, char *argv[])
{
    unsigned i;

    parse(argc, argv);
    /* One spare, because malloc(0) may return NULL. */
    stars = malloc((density + 1) * sizeof *stars);
    buffer = malloc(SCREEN_SIZE);
    if (stars == NULL || buffer == NULL) {
        printf("Not enough memory for %u stars.\n", density);
        return 1;
    }
    srand((unsigned)time(NULL));
    set_mode(0x11);
    while (!escape() && !update()) {
        for (i = 0; i < RETRACES_PER_FRAME; i++) {
            wait_retrace();
        }
        memcpy(vga, buffer, SCREEN_SIZE);
    }
    set_mode(0x03);
    return 0;
}
