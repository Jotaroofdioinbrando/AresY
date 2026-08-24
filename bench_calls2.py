import time

def transforma(x):
    if x % 2 == 0:
        return (x // 2) + 3
    return (x * 3) + 1

limite = 50000000
inicio = time.time()

estado = 123456
i = 0

while i < limite:
    estado = transforma(estado + i)
    i += 1

fim = time.time()

print("Estado Final:", estado)
print("Tempo Python:", fim - inicio)
