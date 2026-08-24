import time

MOD = 1000000007

def mistura_fibonacci(a, b, i):
    x = (a + b) % MOD
    x = (x * 31 + i * 17) % MOD

    if x % 2 == 0:
        return x * 3
    else:
        return x * 7

def processamento(i, a, b):
    arr = [0] * 8

    arr[0] = a
    arr[1] = b
    arr[2] = i
    arr[3] = a + b
    arr[4] = a * 3
    arr[5] = b * 5
    arr[6] = i % 1000
    arr[7] = (a + b + i) % MOD

    texto = "AresY-" + str(i % 1000)
    tamanho = len(texto)

    x = arr[i % 8]
    x = (x + tamanho) % MOD

    return mistura_fibonacci(x, arr[(i + 1) % 8], i)

inicio = time.perf_counter()

a = 1
b = 1
total = 0

for i in range(100000000):
    resultado = processamento(i, a, b)

    proximo = (a + b) % MOD
    a = b
    b = proximo

    total = (total + resultado) % MOD

    if total % 3 == 0:
        total = (total + a) % MOD
    else:
        total = (total + b) % MOD

fim = time.perf_counter()

print("=== Python EXTREMO ===")
print("Iteracoes:")
print(100000000)
print("Resultado:")
print(total)
print("Tempo:")
print(fim - inicio)
