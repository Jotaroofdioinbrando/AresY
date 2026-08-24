#include <cstdio>
#include <cstdint>
#include <chrono>

__attribute__((noinline))
double calcular(double x) {
    double a = x * 1.371;
    double b = a * a;
    double c = b + (x * 0.731);
    return (c * 0.917) - (a * 0.213) + 7.31;
}

int main() {
    int64_t tamanho = 10000000;

    auto inicio = std::chrono::high_resolution_clock::now();

    double soma = 0.0;

    for (int64_t i = 0; i < tamanho; i++) {
        double x = i;
        soma += calcular(x);
    }

    auto fim = std::chrono::high_resolution_clock::now();

    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma: %.6f\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
