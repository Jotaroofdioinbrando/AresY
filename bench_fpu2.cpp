#include <cstdio>
#include <chrono>

int main() {
    long limite = 20000000;
    auto inicio = std::chrono::high_resolution_clock::now();

    double soma = 0.0;
    double x = 0.5;
    double passo = 1.0 / 10000000.0;

    for (long i = 0; i < limite; i++) {
        soma += (x * x * x * x) - (3.5 * x * x) + (2.1 * x) - 0.7;
        x += passo;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma FPU: %f\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
