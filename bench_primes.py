import time

limite = 500000
inicio = time.time()

total_primos = 0
n = 2

while n <= limite:
    eh_primo = 1
    i = 2
    while i * i <= n:
        if n % i == 0:
            eh_primo = 0
            break
        i += 1
    if eh_primo == 1:
        total_primos += 1
    n += 1

fim = time.time()

print("Total de primos:", total_primos)
print("Tempo Python:", fim - inicio)
