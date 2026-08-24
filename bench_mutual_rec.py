import time
import sys

sys.setrecursionlimit(30000)

def e_impar(n):
    if n == 0:
        return 0
    return e_par(n - 1)

def e_par(n):
    if n == 0:
        return 1
    return e_impar(n - 1)

limite = 20000
inicio = time.time()
resultado = 0

for i in range(1000):
    resultado = e_par(limite)

fim = time.time()

print("Resultado Par (1 = Sim):", resultado)
print("Tempo Python:", fim - inicio)
