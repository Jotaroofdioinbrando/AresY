import time

def calcula(a, b):
    return (a * 3) + (b // 2)

limite = 50000000
inicio = time.time()

soma = 0
i = 0

while i < limite:
    soma += calcula(i, 4)
    i += 1

fim = time.time()

print("Soma:", soma)
print("Tempo Python:", fim - inicio)
