#include <cstdio>
#include <vector>
#include <chrono>

int main() {
    int limite = 10000000;
    auto inicio = std::chrono::high_resolution_clock::now();

    std::vector<int> e_composto(limite, 0);
    int primos = 0;

    for (int i = 2; i < limite; i++) {
        if (e_composto[i] == 0) {
            primos++;
            for (int j = i * 2; j < limite; j += i) {
                e_composto[j] = 1;
            }
        }
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Total de Primos: %d\n", primos);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
