#include <cstdio>
#include <cstdint>
#include <chrono>

int main() {
    int64_t limite = 100000000;
    auto inicio = std::chrono::high_resolution_clock::now();

    int64_t acc = 0;
    int64_t i = 0;

    while (i < limite) {
        if (i % 2 == 0) {
            acc += i * 2;
        } else {
            acc -= i;
        }
        i++;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Resultado: %ld\n", acc);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
