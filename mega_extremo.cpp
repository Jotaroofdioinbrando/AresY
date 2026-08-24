#include <iostream>
#include <chrono>
#include <string>

long long mistura_fibonacci(long long a, long long b, long long i) {
    long long x = (a + b) % 1000000007;
    x = (x * 31 + i * 17) % 1000000007;

    if (x % 2 == 0)
        return x * 3;
    else
        return x * 7;
}

long long processamento(long long i, long long a, long long b) {
    long long arr[8];

    arr[0] = a;
    arr[1] = b;
    arr[2] = i;
    arr[3] = a + b;
    arr[4] = a * 3;
    arr[5] = b * 5;
    arr[6] = i % 1000;
    arr[7] = (a + b + i) % 1000000007;

    std::string texto = "AresY-" + std::to_string(i % 1000);
    long long tamanho = texto.length();

    long long x = arr[i % 8];
    x = (x + tamanho) % 1000000007;

    return mistura_fibonacci(x, arr[(i + 1) % 8], i);
}

int main() {
    auto inicio = std::chrono::steady_clock::now();

    long long a = 1;
    long long b = 1;
    long long total = 0;

    for (long long i = 0; i < 100000000; i++) {
        long long resultado = processamento(i, a, b);

        long long proximo = (a + b) % 1000000007;
        a = b;
        b = proximo;

        total = (total + resultado) % 1000000007;

        if (total % 3 == 0)
            total = (total + a) % 1000000007;
        else
            total = (total + b) % 1000000007;
    }

    auto fim = std::chrono::steady_clock::now();

    double tempo =
        std::chrono::duration<double>(fim - inicio).count();

    std::cout << "=== C++ EXTREMO ===\n";
    std::cout << "Iteracoes:\n";
    std::cout << 100000000 << '\n';
    std::cout << "Resultado:\n";
    std::cout << total << '\n';
    std::cout << "Tempo:\n";
    std::cout << tempo << '\n';
}
