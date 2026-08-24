#include <iostream>
#include <chrono>
#include <string>

long long trabalho(long long n) {
    long long total = 0;

    for (long long i = 0; i < n; i++) {
        long long arr[16];

        arr[0] = i;
        arr[1] = i * 3;
        arr[2] = i * 7;
        arr[3] = i * 11;
        arr[4] = i * 13;
        arr[5] = i * 17;
        arr[6] = i * 19;
        arr[7] = i * 23;

        long long x = arr[i % 8];

        if (x % 2 == 0)
            total += x * 3;
        else
            total += x * 5;

        total %= 1000000007;

        std::string texto = "AresY-" + std::to_string(i % 1000);
        total += texto.length();
    }

    return total;
}

int main() {
    auto inicio = std::chrono::steady_clock::now();

    long long resultado = 0;

    for (long long rodada = 0; rodada < 100; rodada++)
        resultado = trabalho(100000);

    auto fim = std::chrono::steady_clock::now();

    double tempo =
        std::chrono::duration<double>(fim - inicio).count();

    std::cout << "=== C++ MAX ===\n";
    std::cout << "Resultado:\n";
    std::cout << resultado << '\n';
    std::cout << "Tempo:\n";
    std::cout << tempo << '\n';

    return 0;
}
