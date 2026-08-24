#include <iostream>
#include <chrono>
#include <string>

long long trabalho(long long n) {
    long long a = 1;
    long long b = 1;
    long long total = 0;

    for (long long i = 0; i < n; i++) {
        long long c = (a + b) % 1000000007;
        a = b;
        b = c;

        long long x =
            (a * 31 + b * 17 + i * 13) % 1000000007;

        if (x % 2 == 0)
            total += x * 3;
        else
            total += x * 7;

        total %= 1000000007;

        std::string s = "AresY-" + std::to_string(i % 1000);
        total += s.length();
    }

    return total;
}

int main() {
    auto inicio = std::chrono::steady_clock::now();

    long long resultado = trabalho(20000000);

    auto fim = std::chrono::steady_clock::now();

    double tempo =
        std::chrono::duration<double>(fim - inicio).count();

    std::cout << "=== C++ ===\n";
    std::cout << "Resultado:\n";
    std::cout << resultado << '\n';
    std::cout << "Tempo:\n";
    std::cout << tempo << '\n';

    return 0;
}
