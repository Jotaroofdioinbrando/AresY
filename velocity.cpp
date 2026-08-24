#include <iostream>
#include <chrono>

long long calcular(long long n) {
    long long total = 0;
    long long i = 1;

    while (i <= n) {
        long long x = i * 31;
        x = x % 1000000007;

        if (x % 3 == 0) {
            total = total + x * 7;
        } else {
            if (x % 2 == 0) {
                total = total + x * 3;
            } else {
                total = total + x * 5;
            }
        }

        total = total % 1000000007;
        i = i + 1;
    }

    return total;
}

int main() {
    auto inicio = std::chrono::steady_clock::now();

    long long resultado = 0;
    long long i = 0;

    while (i < 1000) {
        resultado = calcular(100000);
        i = i + 1;
    }

    auto fim = std::chrono::steady_clock::now();

    double tempo =
        std::chrono::duration<double>(fim - inicio).count();

    std::cout << "=== C++ VELOCITY ===\n";
    std::cout << "Resultado:\n";
    std::cout << resultado << '\n';
    std::cout << "Tempo:\n";
    std::cout << tempo << '\n';

    return 0;
}
