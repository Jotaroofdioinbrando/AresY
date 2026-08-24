#include <cstdio>
#include <chrono>

long long adicionar(long long a, long long b) {
    return a + b;
}

int main() {
    long long limite = 100000000;

    auto inicio = std::chrono::high_resolution_clock::now();

    long long soma = 0;

    for (long long i = 0; i < limite; i++) {
        soma += adicionar(i, 3);
    }

    auto fim = std::chrono::high_resolution_clock::now();

    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma: %lld\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
