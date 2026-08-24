import time

limite = 100000000
inicio = time.time()

acc = 123456789
i = 0

while i < limite:
    acc = (acc ^ (i * 3)) & 2147483647
    i += 1

fim = time.time()

print("Resultado Bitwise:", acc)
print("Tempo Python:", fim - inicio)
