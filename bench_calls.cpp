#include <cstdio>
#include <cstdint>
#include <chrono>

int64_t calcula(int64_t a, int64_t b) {
    return (a * 3) + (b / 2);
}

int main() {
    int64_t limite = 50000000;
    auto inicio = std::chrono::high_resolution_clock::now();

    int64_t soma = 0;
    int64_t i = 0;

    while (i < limite) {
        soma += calcula(i, 4);
        i++;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma: %ld\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
