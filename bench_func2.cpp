#include <cstdio>
#include <chrono>
#include <cstdint>

__attribute__((noinline))
int64_t calcular(int64_t x) {
    int64_t a = (x * 7) ^ (x / 8);
    return (a * 13) + (x % 256);
}

int main() {
    int64_t limite = 100000000;

    auto inicio = std::chrono::high_resolution_clock::now();

    int64_t soma = 0;

    for (int64_t i = 0; i < limite; i++) {
        soma += calcular(i);
    }

    auto fim = std::chrono::high_resolution_clock::now();

    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma: %ld\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
