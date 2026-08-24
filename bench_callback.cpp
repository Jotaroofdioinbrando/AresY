#include <cstdio>
#include <cstdint>
#include <chrono>

int64_t somar(int64_t a, int64_t b) {
    return a + b;
}

int64_t multiplicar(int64_t a, int64_t b) {
    return a * b;
}

int64_t executar_operacao(int64_t (*func)(int64_t, int64_t), int64_t x, int64_t y) {
    return func(x, y);
}

int main() {
    int64_t limite = 30000000;
    auto inicio = std::chrono::high_resolution_clock::now();

    int64_t acc = 0;
    for (int64_t i = 0; i < limite; i++) {
        acc = executar_operacao(somar, acc, 1);
        acc = executar_operacao(multiplicar, acc, 1);
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Resultado Callback: %ld\n", acc);
    printf("Tempo C++: %f\n", duracao.count());
    return 0;
}
