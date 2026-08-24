import time

limite = 100000000
inicio = time.time()

acc = 0
i = 0

while i < limite:
    if i % 2 == 0:
        acc += i * 2
    else:
        acc -= i
    i += 1

fim = time.time()

print("Resultado:", acc)
print("Tempo Python:", fim - inicio)
