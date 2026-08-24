#include <cstdio>
#include <cmath>
#include <chrono>

int main() {
    auto inicio = std::chrono::high_resolution_clock::now();

    double soma = 0.0;
    long limite = 20000000;

    for (long i = 1; i <= limite; i++) {
        soma += std::sqrt(i);
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma: %f\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
