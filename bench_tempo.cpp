#include <iostream>
#include <chrono>

long long fib(long long n) {
    if (n < 2)
        return n;
    return fib(n - 1) + fib(n - 2);
}

int main() {
    auto inicio = std::chrono::steady_clock::now();

    long long resultado = 0;

    for (int i = 0; i < 10; i++)
        resultado = fib(30);

    auto fim = std::chrono::steady_clock::now();

    auto tempo = std::chrono::duration_cast<
        std::chrono::microseconds
    >(fim - inicio).count();

    std::cout << "Resultado:\n";
    std::cout << resultado << '\n';
    std::cout << "Tempo:\n";
    std::cout << tempo << " us\n";
}
