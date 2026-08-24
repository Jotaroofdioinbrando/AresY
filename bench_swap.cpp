#include <cstdio>
#include <vector>
#include <chrono>

int main() {
    int limite = 10000000;
    std::vector<int> arr(limite);
    for (int i = 0; i < limite; i++) arr[i] = i;

    auto inicio = std::chrono::high_resolution_clock::now();

    int esquerda = 0;
    int direita = limite - 1;
    while (esquerda < direita) {
        int temp = arr[esquerda];
        arr[esquerda] = arr[direita];
        arr[direita] = temp;
        esquerda++;
        direita--;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Array Invertido! Elemento 0: %d\n", arr[0]);
    printf("Tempo C++: %f\n", duracao.count());
    return 0;
}
