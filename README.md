# aresY

Linguagem aresY: sintaxe própria, compila pra LLVM IR e usa o `clang` como
backend (binário nativo de verdade, não interpretado).

## Instalar o comando `aresy` no Termux

```
pkg install clang python
bash install_termux.sh
```

Depois disso:

```
aresy
```

já abre o REPL. (Se preferir não instalar, dá pra usar tudo com
`python aresy_compiler.py ...` no lugar de `aresy ...` nos exemplos abaixo.)

## Uso

```
aresy                          # abre o REPL (modo interativo, nativo)
aresy programa.ay              # compila e roda direto
aresy run programa.ay          # igual acima, forma explícita
aresy build programa.ay saida.ll [--triple TRIPLE] [--no-gc]
                                # só gera o LLVM IR
aresy --version                # mostra a versão do compilador
aresy --help                   # lista de comandos e flags
aresy --how                    # resumo de TODA a sintaxe da linguagem
                                # (comece por aqui se for programar em aresY)
```

Pra virar binário nativo depois do `build`:
```
clang -O3 -ffast-math saida.ll -lm -lgc -o programa
./programa
```
(o `-lgc` só é necessário se você não usou `--no-gc`; veja a seção sobre GC
mais abaixo.)

Se der erro de target no seu aparelho, gere o IR passando o triple certo:
```
aresy build exemplo.ay saida.ll --triple aarch64-unknown-linux-android24
```

## Modo interativo (REPL)

```
$ aresy
aresY — modo interativo (compila e roda nativo via clang)
GC (Boehm) ligado — pra desligar, sai e roda: aresy --no-gc
Ctrl+D ou Ctrl+C pra sair.

>>> var x = 10
>>> x + 5
15
>>> fn dobro(n) {
...     return n * 2
... }
>>> dobro(21)
42
```

Funções declaradas ficam disponíveis pro resto da sessão. Blocos com `{ }`
(fn/if/while/try) podem ser escritos em várias linhas — o prompt muda pra
`...` até fechar a chave. Toda expressão "solta" (sem `print`) tem o
resultado ecoado automaticamente.

**Limitação do REPL:** variáveis do tipo `str` e `array(n)` não persistem
entre rounds (o processo anterior já terminou, e o ponteiro/`malloc` dele
não existe mais no próximo). Pra usar isso de verdade, escreva um `.ay` e
rode com `aresy arquivo.ay`.

## Sintaxe — resumo rápido

Rode `aresy --how` a qualquer momento pra ver isso direto no terminal.
Aqui vai o essencial:

```
fn soma(a, b) { return a + b }                    // tipos inferidos (i64)
fn media(a: double, b: double) -> double {         // tipos explícitos
    return (a + b) / 2.0
}

fn main() {
    var x = 10
    var nome = "aresY"
    var arr = array(5)
    arr[0] = x

    if x > 5 { print("grande") } else { print("pequeno") }

    var i = 0
    while i < 3 { print(i); i = i + 1 }

    try {
        if x == 0 { throw "x não pode ser zero" }
    } catch e {
        print("erro: " + e)
    }

    return 0
}
```

- `var x = expr` — declaração; `x = expr` — reatribuição
- `if cond { } else { }`, `while cond { }`, `return expr`
- Aritmética `+ - * / %`, comparação `== != < > <= >=`, bitwise `& | ^`
  (só com inteiros), unário `-`
- `true` / `false`
- Strings: concatenação com `+`, `==`/`!=` por conteúdo, `len(s)`,
  `upper(s)`, `lower(s)`, `substr(s, i, tam)`, `char_at(s, i)`, `str(n)`
- Arrays: `array(n)` (só `i64`, sem bounds checking, sem `free` — o GC
  cuida da memória se estiver ligado)
- `try { } catch e { }` / `throw expr` — exceções propagam pela pilha de
  chamadas até o catch mais próximo; `e` dentro do catch é sempre `str`
- `extern fn nome(tipos) -> tipo` + `import "libc_ou_nome_da_lib"` —
  chama função de biblioteca C (tipos aceitos: `i64`, `f64`, `void`)
- Builtins: `sqrt` `sin` `cos` `tan` `atan` `atan2` `log` `log10` `exp`
  `pow` `floor` `ceil` `abs` `min` `max` `pi()` `time()` `sleep(s)`
  `random(n)` `input()` `read_line()` `read_file(caminho)`
  `write_file(caminho, txt)` `append_file(caminho, txt)`

## Bibliotecas nativas em .ay (import de módulo)

Além de `import "nome_da_lib_c"` (que vira `-lNOME` na hora de linkar),
dá pra importar um arquivo `.ay` inteiro — as `fn` dele ficam disponíveis
no programa que importou, tipo um `#include` simples:

```
import "stdlib/mathx.ay"     // caminho relativo ao arquivo que importa
import geometria              // sem aspas: procura "geometria.ay" no
                               // mesmo diretório

fn main() {
    print(quadrado(7))                        // de stdlib/mathx.ay
    print(geometria.calcular_area_circulo(5.0)) // prefixo é opcional,
                                                  // só documentação
    return 0
}
```

Regras: bibliotecas importadas não podem ter `main()`; um mesmo arquivo só
é trazido uma vez mesmo se importado por caminhos diferentes do grafo de
imports (evita duplicação e import circular). O projeto já vem com duas
bibliotecas em `stdlib/`:

- `stdlib/mathx.ay` — `quadrado`, `cubo`, `potencia`, `fatorial`,
  `eh_primo`, `eh_par`/`eh_impar`, `mdc`, `mmc`, `clamp`, `media`
- `stdlib/strings.ay` — `eh_vazia`, `repetir`, `inverter`,
  `eh_palindromo`, `contem`

Veja `exemplo_stdlib.ay` pra um exemplo completo usando as duas.

## Coletor de lixo (GC)

Por padrão, `array(n)`, strings novas (concatenação, `substr` etc.) e
strings lidas de arquivo/teclado são alocadas com o Boehm GC (`GC_malloc`),
que varre e libera memória automaticamente — sem isso, um programa de vida
longa que aloca em loop vazaria memória sem parar (o protótipo original
usava só `malloc` puro e nunca liberava nada).

- Precisa da `libgc` instalada (`pkg install libgc`) e do `-lgc` na hora
  de linkar — o `aresy` já faz isso sozinho.
- Se não quiser depender da libgc, use `--no-gc` em qualquer comando
  (`aresy --no-gc programa.ay`, `aresy build --no-gc ...`) — aí volta a
  usar `malloc` puro, sem coleta (cuidado com loops muito longos).

## Bugs corrigidos nesta versão

- **Notação científica em float** (`0.0000001`, `1e-7`) — literais double
  agora são emitidos como hex IEEE-754 (`0x...`) pro LLVM, formato que não
  depende de como o Python formata o número por baixo dos panos.
- **`==`/`!=` entre strings fora de `if`** — o resultado da comparação
  (`icmp`, tipo `i1` no LLVM) estava rotulado internamente como `i64`, o
  que gerava IR inválido sempre que o resultado era usado em outro lugar
  além da condição de um `if`/`while` (ex.: `print(a == b)` ou
  `return a == b` quebravam a compilação). Mesmo problema existia pra
  comparação de números (`print(3 > 2)`) e pra aritmética/bitwise
  misturando número com comparação (`1 + (3 > 2)`). Corrigido normalizando
  esses valores pra `i64` nos pontos onde são consumidos.
- **`import geometria` / `modulo.funcao(...)`** — a sintaxe já existia nos
  exemplos do projeto (`main.ay`/`geometria.ay`) mas não compilava: faltava
  o `.` no lexer e o parser não entendia chamada qualificada por módulo.

## Limitações atuais

- Parâmetros de função aceitam `i64`/`double`/`str`, mas ponteiro de
  função como argumento (callback) assume sempre `i64` — sem checagem de
  tipo real entre o que foi passado e como é chamado.
- Arrays não têm bounds checking; só guardam `i64`.
- Sem structs/tipos compostos ainda.
- Sem interpolação/f-strings — concatenação com `+` cobre o caso básico.
- `import "arquivo.ay"` não tem namespace de verdade: tudo que a
  biblioteca declara no topo do arquivo entra no escopo global de quem
  importou (sem exportação seletiva, sem `as apelido`).
