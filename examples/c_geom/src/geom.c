#include "geom.h"

int rect_area(int w, int h) {
    if (w <= 0 || h <= 0) {
        return -1;
    }
    return w * h;
}

int clampi(int v, int lo, int hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

int max3(int a, int b, int c) {
    int m = a;
    if (b > m) m = b;
    if (c > m) m = c;
    return m;
}

int point_in_rect(int x, int y, int x1, int y1, int x2, int y2) {
    return x >= x1 && x <= x2 && y >= y1 && y <= y2;
}
