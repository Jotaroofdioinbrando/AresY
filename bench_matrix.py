import time

tam = 2000
total = tam * tam
inicio = time.time()

mat = [0] * total
for i in range(tam):
    for j in range(tam):
        mat[i * tam + j] = i + j

soma = 0
for i in range(tam):
    for j in range(tam):
        soma += mat[i * tam + j]

fim = time.time()

print("Soma:", soma)
print("Tempo Python:", fim - inicio)
