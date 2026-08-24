#include <iostream>
#include <string>
#include <chrono>

int main() {
    int limite = 10000;
    auto inicio = std::chrono::high_resolution_clock::now();

    std::string texto = "";
    for (int i = 0; i < limite; i++) {
        texto = texto + "A";
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    std::cout << "Tempo C++:\n" << duracao.count() << "\n";
    return 0;
}
