import time

def trabalho(n):
    a = 1
    b = 1
    total = 0

    for i in range(n):
        c = (a + b) % 1000000007
        a = b
        b = c

        x = (a * 31 + b * 17 + i * 13) % 1000000007

        if x % 2 == 0:
            total += x * 3
        else:
            total += x * 7

        total %= 1000000007

        s = "AresY-" + str(i % 1000)
        total += len(s)

    return total

inicio = time.perf_counter()

resultado = trabalho(20000000)

fim = time.perf_counter()

print("=== Python ===")
print("Resultado:")
print(resultado)
print("Tempo:")
print(fim - inicio)
