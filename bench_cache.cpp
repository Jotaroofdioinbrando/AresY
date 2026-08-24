#include <cstdio>
#include <cstdint>
#include <vector>
#include <chrono>

int main() {
    int64_t tam = 10000000;
    std::vector<int64_t> arr(tam);
    for (int64_t i = 0; i < tam; i++) {
        arr[i] = (i * 7 + 13) % tam;
    }

    auto inicio = std::chrono::high_resolution_clock::now();

    int64_t idx = 0;
    int64_t soma = 0;
    int64_t passadas = 0;
    int64_t limite_passadas = 20000000;

    while (passadas < limite_passadas) {
        idx = arr[idx];
        soma += idx;
        passadas++;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma: %ld\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
