#include <stdio.h>
#include "geom.h"

static int failures = 0;

#define CHECK(cond) do { \
    if (!(cond)) { \
        printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        failures++; \
    } \
} while (0)

int main(void) {
    CHECK(rect_area(3, 4) == 12);
    CHECK(rect_area(-1, 4) == -1);
    /* 漏测点：w/h 为 0 的边界 */
    CHECK(clampi(5, 1, 10) == 5);
    /* 漏测点：clampi 边界值 */
    CHECK(max3(1, 5, 3) == 5);
    CHECK(max3(9, 2, 3) == 9);
    /* 漏测点：c 为最大值分支 */
    CHECK(point_in_rect(2, 3, 1, 1, 5, 5) == 1);
    CHECK(point_in_rect(6, 3, 1, 1, 5, 5) == 0);
    if (failures == 0) {
        printf("ALL PASS\n");
        return 0;
    }
    printf("%d failures\n", failures);
    return 1;
}
