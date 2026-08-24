import time

def somar(a, b):
    return a + b

def multiplicar(a, b):
    return a * b

def executar_operacao(func, x, y):
    return func(x, y)

limite = 30000000
inicio = time.time()

acc = 0
for i in range(limite):
    acc = executar_operacao(somar, acc, 1)
    acc = executar_operacao(multiplicar, acc, 1)

fim = time.time()

print("Resultado Callback:", acc)
print("Tempo Python:", fim - inicio)
