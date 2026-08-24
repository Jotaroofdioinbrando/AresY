import time

limite = 10000000
inicio = time.time()

e_composto = [0] * limite
primos = 0

for i in range(2, limite):
    if e_composto[i] == 0:
        primos += 1
        for j in range(i * 2, limite, i):
            e_composto[j] = 1

fim = time.time()

print("Total de Primos:", primos)
print("Tempo Python:", fim - inicio)
