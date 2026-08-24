#include <cstdio>
#include <cstdint>
#include <vector>
#include <chrono>

int main() {
    int64_t tamanho = 10000000;
    auto inicio = std::chrono::high_resolution_clock::now();

    std::vector<int64_t> arr(tamanho);
    for (int64_t i = 0; i < tamanho; i++) {
        arr[i] = i * 2;
    }

    int64_t soma = 0;
    for (int64_t i = 0; i < tamanho; i++) {
        soma += arr[i];
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma: %ld\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
