#include <cstdio>
#include <cstdint>
#include <vector>
#include <chrono>

int main() {
    int64_t tamanho = 10000000;

    std::vector<int64_t> arr(tamanho);

    for (int64_t i = 0; i < tamanho; i++) {
        arr[i] = (i * 7919 + 12345) % tamanho;
    }

    auto inicio = std::chrono::high_resolution_clock::now();

    int64_t idx = 0;
    int64_t soma = 0;
    int64_t passadas = 0;
    int64_t limite = 20000000;

    while (passadas < limite) {
        idx = arr[idx];
        soma = soma + idx;
        passadas = passadas + 1;
    }

    auto fim = std::chrono::high_resolution_clock::now();

    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma: %ld\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
