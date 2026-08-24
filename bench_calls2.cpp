#include <cstdio>
#include <cstdint>
#include <chrono>

int64_t transforma(int64_t x) {
    if (x % 2 == 0) {
        return (x / 2) + 3;
    }
    return (x * 3) + 1;
}

int main() {
    int64_t limite = 50000000;
    auto inicio = std::chrono::high_resolution_clock::now();

    int64_t estado = 123456;
    int64_t i = 0;

    while (i < limite) {
        estado = transforma(estado + i);
        i++;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Estado Final: %ld\n", estado);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
