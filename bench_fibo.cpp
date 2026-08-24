#include <cstdio>
#include <cstdint>
#include <chrono>

int64_t fibo(int64_t n) {
    if (n <= 1) {
        return n;
    }
    return fibo(n - 1) + fibo(n - 2);
}

int main() {
    auto inicio = std::chrono::high_resolution_clock::now();

    int64_t res = fibo(42);

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Resultado: %ld\n", res);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
