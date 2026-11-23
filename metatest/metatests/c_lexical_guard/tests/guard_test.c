#include <stdio.h>
#include "guard.h"

static int failures = 0;

#define CHECK(cond) do { \
    if (!(cond)) { \
        printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        failures++; \
    } \
} while (0)

int main(void) {
    CHECK(add(2, 3) == 8);      /* 2+3+OFFSET(3) */
    CHECK(add(-1, 1) == 3);
    CHECK(maxv(5, 2) == 5);
    CHECK(maxv(2, 5) == 5);
    if (failures == 0) {
        printf("ALL PASS\n");
        return 0;
    }
    printf("%d failures\n", failures);
    return 1;
}
