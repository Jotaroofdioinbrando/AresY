#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <chrono>

int main() {
    auto inicio = std::chrono::high_resolution_clock::now();

    int64_t soma = 0;
    int64_t i = 0;

    while (i < 50000000) {
        soma = soma + (rand() % 1000000);
        i = i + 1;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("%ld\n", soma);
    printf("%f\n", duracao.count());

    return 0;
}
