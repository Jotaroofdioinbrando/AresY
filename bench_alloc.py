import time

class Objeto:
    def __init__(self, a, b):
        self.a = a
        self.b = b

limite = 1000000
inicio = time.time()

objetos = [None] * limite
for i in range(limite):
    objetos[i] = Objeto(i, i * 2)

soma = 0
for i in range(limite):
    o = objetos[i]
    soma += o.a + o.b

fim = time.time()

print("Soma:", soma)
print("Tempo Python:", fim - inicio)
