#include <stdio.h>
#include "calc.h"

static int failures = 0;

#define CHECK(cond) do { \
    if (!(cond)) { \
        printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        failures++; \
    } \
} while (0)

int main(void) {
    CHECK(add(2, 3) == 5);
    CHECK(add(-1, 1) == 0);
    CHECK(is_leap(2024) == 1);
    CHECK(is_leap(2000) == 1);
    CHECK(is_leap(1900) == 0);
    CHECK(is_leap(2023) == 0);
    if (failures == 0) {
        printf("ALL PASS\n");
        return 0;
    }
    printf("%d failures\n", failures);
    return 1;
}
