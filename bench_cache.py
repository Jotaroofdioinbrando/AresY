import time

tam = 10000000
arr = [(i * 7 + 13) % tam for i in range(tam)]

inicio = time.time()

idx = 0
soma = 0
passadas = 0
limite_passadas = 20000000

while passadas < limite_passadas:
    idx = arr[idx]
    soma += idx
    passadas += 1

fim = time.time()

print("Soma:", soma)
print("Tempo Python:", fim - inicio)
