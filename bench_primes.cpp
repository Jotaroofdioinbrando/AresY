#include <cstdio>
#include <cstdint>
#include <chrono>

int main() {
    int limite = 500000;
    auto inicio = std::chrono::high_resolution_clock::now();

    int total_primos = 0;
    int n = 2;
    int i = 2;
    int eh_primo = 1;

    while (n <= limite) {
        eh_primo = 1;
        i = 2;
        while (i * i <= n) {
            if (n % i == 0) {
                eh_primo = 0;
                break;
            }
            i++;
        }
        if (eh_primo == 1) {
            total_primos++;
        }
        n++;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Total de primos: %d\n", total_primos);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
