#include <cstdio>
#include <cstdint>
#include <vector>
#include <chrono>

struct Objeto {
    int64_t a;
    int64_t b;
};

int main() {
    int64_t limite = 1000000;
    auto inicio = std::chrono::high_resolution_clock::now();

    // Aloca 1 milhão de ponteiros/objetos dinâmicos na Heap
    std::vector<Objeto*> objetos(limite);
    for (int64_t i = 0; i < limite; i++) {
        Objeto* obj = new Objeto();
        obj->a = i;
        obj->b = i * 2;
        objetos[i] = obj;
    }

    int64_t soma = 0;
    for (int64_t i = 0; i < limite; i++) {
        Objeto* o = objetos[i];
        soma += o->a + o->b;
    }

    auto fim = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duracao = fim - inicio;

    printf("Soma: %ld\n", soma);
    printf("Tempo C++: %f\n", duracao.count());

    return 0;
}
