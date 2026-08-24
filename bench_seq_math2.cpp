#include <cstdio>
#include <cstdint>
#include <vector>
#include <chrono>

int main() {
    int64_t tamanho = 10000000;

    auto inicio = std::chrono::high_resolution_clock::now();

    std::vector<int64_t> arr(tamanho);

    for (int64_t i = 0; i < tamanho; i++) {
        arr[i] = i;
    }

    double soma = 0.0;

    for (int64_t i = 0; i < tamanho; i++) {
        double x = arr[i];
        double a = x * 1.371;
        double b = a * a;
        double c = b + (x * 0.731);
        soma += (c * 0.917) - (a * 0.213) + 7.31;
    }

    auto fim = std::chrono::high_resolution_clock::now();

    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma: %.6f\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
