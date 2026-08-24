#include <cstdio>
#include <cstdint>
#include <vector>
#include <chrono>

int main() {
    int tam = 15000;
    std::vector<int64_t> arr(tam);
    for (int i = 0; i < tam; i++) {
        arr[i] = tam - i;
    }

    auto inicio = std::chrono::high_resolution_clock::now();

    // Bubble Sort
    int i = 0;
    int j = 0;
    int64_t temp = 0;
    int limite_j = 0;

    for (i = 0; i < tam; i++) {
        limite_j = tam - i - 1;
        for (j = 0; j < limite_j; j++) {
            if (arr[j] > arr[j + 1]) {
                temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Primeiro elemento: %ld\n", arr[0]);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
