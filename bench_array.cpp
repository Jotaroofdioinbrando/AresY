#include <iostream>
#include <chrono>

long long calcular(long long n) {
    long long dados[100];
    long long i = 0;
    long long total = 0;

    while (i < 100) {
        dados[i] = (i + 1) * 37;
        i++;
    }

    i = 0;

    while (i < n) {
        long long pos = i % 100;
        total += dados[pos] * (i + 1);

        if (total > 1000000007)
            total %= 1000000007;

        i++;
    }

    return total;
}

int main() {
    auto inicio = std::chrono::steady_clock::now();

    long long resultado = 0;
    long long i = 0;

    while (i < 1000) {
        resultado = calcular(100000);
        i++;
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
