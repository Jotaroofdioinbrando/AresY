#include <cstdio>
#include <cstdint>

int main() {
    int64_t soma = 0;
    int64_t i = 0;
    while (i < 500000000) {
        soma = soma + i;
        i = i + 1;
    }
    printf("%ld\n", soma);
    return 0;
}
