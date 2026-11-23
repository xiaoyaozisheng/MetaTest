#include "guard.h"

/* 词法误伤高危区：本行宏体内含 "+"，词法级变异器不得触碰 */
#define OFFSET 3

/* 词法误伤高危区：字符串字面量内含运算符与 && */
static const char *LABEL = "a + b && c";

int add(int a, int b) {
    return a + b + OFFSET;
}

int maxv(int a, int b) {
    return (a > b) ? a : b;
}
