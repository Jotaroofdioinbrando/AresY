#include <iostream>
#include <chrono>

long long trabalho(long long n) {
    long long a = 0;
    long long b = 1;
    long long soma = 0;

    for (long long i = 0; i < n; i++) {
        long long proximo = a + b;
        a = b;
        b = proximo;

        if (b > 1000000000) {
            a %= 1000000007;
            b %= 1000000007;
        }

        soma = (soma + a * 31 + b * 17) % 1000000007;
    }

    return soma;
}

int main() {
    auto inicio = std::chrono::steady_clock::now();

    long long resultado = 0;

    for (long long i = 0; i < 1000000; i++) {
        resultado = trabalho(100);
    }

    auto fim = std::chrono::steady_clock::now();

    double tempo =
        std::chrono::duration<double>(fim - inicio).count();

    std::cout << "Resultado:\n";
    std::cout << resultado << '\n';
    std::cout << "Tempo:\n";
    std::cout << tempo << '\n';

    return 0;
}
