import time

tam = 15000
arr = [tam - i for i in range(tam)]

inicio = time.time()

# Bubble Sort
for i in range(tam):
    limite_j = tam - i - 1
    for j in range(limite_j):
        if arr[j] > arr[j + 1]:
            arr[j], arr[j + 1] = arr[j + 1], arr[j]

fim = time.time()

print("Primeiro elemento:", arr[0])
print("Tempo Python:", fim - inicio)
