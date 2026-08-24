#include <cstdio>
#include <vector>
#include <chrono>

int main() {
    int tamanho = 1000;
    std::vector<std::vector<int>> matriz(tamanho, std::vector<int>(tamanho));

    for (int i = 0; i < tamanho; i++) {
        for (int j = 0; j < tamanho; j++) {
            matriz[i][j] = i + j;
        }
    }

    auto inicio = std::chrono::high_resolution_clock::now();
    long long soma = 0;

    for (int k = 0; k < 10; k++) {
        for (int r = 0; r < tamanho; r++) {
            for (int c = 0; c < tamanho; c++) {
                soma += matriz[r][c];
            }
        }
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma da Matriz: %lld\n", soma);
    printf("Tempo C++: %f\n", duracao.count());
    return 0;
}
