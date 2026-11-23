cmake_minimum_required(VERSION 3.21)
project(c_demo C)

enable_testing()

add_executable(calc_test
    src/calc.c
    tests/calc_test.c
)
target_include_directories(calc_test PRIVATE src)

add_test(NAME calc COMMAND calc_test)
