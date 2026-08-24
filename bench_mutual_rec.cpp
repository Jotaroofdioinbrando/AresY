#include <cstdio>
#include <chrono>

int e_par(int n);

int e_impar(int n) {
    if (n == 0) return 0;
    return e_par(n - 1);
}

int e_par(int n) {
    if (n == 0) return 1;
    return e_impar(n - 1);
}

int main() {
    int limite = 20000;
    auto inicio = std::chrono::high_resolution_clock::now();
    int resultado = 0;

    for (int i = 0; i < 1000; i++) {
        resultado = e_par(limite);
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Resultado Par (1 = Sim): %d\n", resultado);
    printf("Tempo C++: %f\n", duracao.count());
    return 0;
}
