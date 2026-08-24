import time

def fibo(n):
    if n <= 1:
        return n
    return fibo(n - 1) + fibo(n - 2)

inicio = time.time()
res = fibo(38)
fim = time.time()

print("Resultado:", res)
print("Tempo Python:", fim - inicio)
