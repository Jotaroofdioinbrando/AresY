#include <cstdio>
#include <cstdint>
#include <chrono>

int main() {
    int64_t limite = 100000000;
    auto inicio = std::chrono::high_resolution_clock::now();

    int64_t acc = 123456789;
    int64_t i = 0;

    while (i < limite) {
        acc = (acc ^ (i * 3)) & 2147483647;
        i++;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Resultado Bitwise: %ld\n", acc);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
