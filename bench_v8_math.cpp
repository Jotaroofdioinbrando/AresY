#include <cstdio>
#include <cmath>
#include <chrono>

int main() {
    double limite = 10000000.0;
    auto inicio = std::chrono::high_resolution_clock::now();

    double soma = 0.0;
    double i = 1.0;

    while (i < limite) {
        soma += std::sin(i) + std::cos(i) + std::pow(1.01, 2.0);
        i += 1.0;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma Math Builtin C++: %f\n", soma);
    printf("Tempo C++ (-O3 -ffast-math): %f\n", duracao.count());

    return 0;
}
