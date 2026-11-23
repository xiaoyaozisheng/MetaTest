#include <stdio.h>
#include "strutil.h"

static int failures = 0;

#define CHECK(cond) do { \
    if (!(cond)) { \
        printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        failures++; \
    } \
} while (0)

int main(void) {
    CHECK(my_strlen("hello") == 5);
    CHECK(my_strlen("") == 0);
    CHECK(is_palindrome("level") == 1);
    CHECK(is_palindrome("hello") == 0);
    /* 漏测点：单字符/空串回文边界 */
    CHECK(count_vowels("metatest") == 3);
    if (failures == 0) {
        printf("ALL PASS\n");
        return 0;
    }
    printf("%d failures\n", failures);
    return 1;
}
