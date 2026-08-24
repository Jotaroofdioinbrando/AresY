import time

limite = 20000000
inicio = time.time()

soma = 0.0
x = 0.5
passo = 1.0 / 10000000.0

for i in range(limite):
    soma += (x * x * x * x) - (3.5 * x * x) + (2.1 * x) - 0.7
    x += passo

fim = time.time()

print("Soma FPU:", soma)
print("Tempo Python:", fim - inicio)
