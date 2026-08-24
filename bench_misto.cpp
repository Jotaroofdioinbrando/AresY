#include <iostream>
#include <chrono>

long long calcular(long long n) {
    long long total = 0;

    for (long long i = 1; i <= n; i++) {
        long long x = i * 37;
        x %= 1000000007;

        if (x % 2 == 0)
            total += x * 3;
        else
            total += x * 7;

        total %= 1000000007;
    }

    return total;
}

int main() {
    auto inicio = std::chrono::steady_clock::now();

    long long resultado = 0;

    for (long long i = 0; i < 1000; i++)
        resultado = calcular(100000);

    auto fim = std::chrono::steady_clock::now();

    double tempo =
        std::chrono::duration<double>(fim - inicio).count();

    std::cout << "Resultado:\n";
    std::cout << resultado << '\n';
    std::cout << "Tempo:\n";
    std::cout << tempo << '\n';

    return 0;
}
