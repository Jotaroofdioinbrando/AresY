import time

limite = 10000
inicio = time.time()

texto = ""
for i in range(limite):
    texto = texto + "A"

fim = time.time()

print("Tempo Python:", fim - inicio)
