#include <cstdio>
#include <chrono>

int main() {
    long limite = 10000000;
    auto inicio = std::chrono::high_resolution_clock::now();

    double soma = 0.0;

    for (long i = 0; i < limite; i++) {
        double x = i;
        double a = x * 1.371;
        double b = a * a;
        double c = b + x * 0.72;
        soma += c * 0.92 - a * 0.213 + 7.31;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma: %f\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
