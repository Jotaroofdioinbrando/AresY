#include <cstdio>
#include <cstdint>
#include <chrono>

int main() {
    int64_t limite = 50000000;
    auto inicio = std::chrono::high_resolution_clock::now();

    int64_t soma_mdc = 0;
    for (int64_t i = 1; i < limite; i++) {
        int64_t a = i * 7;
        int64_t b = i * 3;

        while (b != 0) {
            int64_t temp = b;
            b = a % b;
            a = temp;
        }

        soma_mdc += a;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma dos MDCs: %ld\n", soma_mdc);
    printf("Tempo C++: %f\n", duracao.count());
    return 0;
}
