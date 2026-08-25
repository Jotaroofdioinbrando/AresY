# aresY

Linguagem aresY: sintaxe própria, compila pra LLVM IR e usa o `clang` como
backend (binário nativo de verdade, não interpretado).

Tipos (`i64`/`double`/`str`), funções com anotação de tipo opcional,
arrays, `try`/`catch`/`throw`, ponteiro de função, `extern fn` (chama
biblioteca C), sistema de `import` de arquivos `.ay`, coletor de lixo
(Boehm GC) e um gerenciador de pacotes (`aresy install`) pra puxar
bibliotecas de terceiros.

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
  `to_raw(double) -> i64` / `from_raw(i64) -> double` — reinterpreta os
  bits (não converte o valor); serve pra guardar `double` dentro de um
  `array`, que só guarda `i64` por posição (é assim que `numares.ay`
  implementa os arrays "_d" de ponto flutuante)

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
imports (evita duplicação e import circular). O projeto já vem com três
bibliotecas em `stdlib/`:

- `stdlib/mathx.ay` — `quadrado`, `cubo`, `potencia`, `fatorial`,
  `eh_primo`, `eh_par`/`eh_impar`, `mdc`, `mmc`, `clamp`, `media`
- `stdlib/strings.ay` — `eh_vazia`, `repetir`, `inverter`,
  `eh_palindromo`, `contem`
- `stdlib/numares.ay` — arrays numéricos estilo NumPy, ~70 funções.
  Convenção: `arr[0]` guarda o tamanho, os elementos ficam em
  `arr[1..n]` (assim as funções sabem o tamanho sem precisar receber
  como parâmetro separado). Cobre desde o básico (`zeros`, `ones`,
  `arange`, `sum`, `mean`, `std`, `sort`, `unique`) até operações de
  matriz 2D (`matmul_2d`, `transpose_2d`, `det_2x2`/`det_3x3`,
  `inv_2x2`, `solve_2x2`, `matvec_mul`). Exemplo:
  ```
  import "stdlib/numares.ay"

  fn main() {
      var a = zeros(5)
      var b = ones(5)
      var c = add(a, b)
      print(sum(c))      // 5
      print(mean(c))      // 1.0
      return 0
  }
  ```
- `stdlib/tensor.ay` — tensores dinâmicos **N-dimensionais** (2D, 3D, 4D...,
  qualquer número de dimensões decidido em tempo de execução). Como aresY só
  tem `array(n)` de 1 dimensão (e nenhuma função variádica), a biblioteca
  representa o tensor como um array plano com um pequeno cabeçalho:
  `t[0]` = número de dimensões, seguido pelo shape e pelas strides
  (pré-calculadas, indexação O(1)), com os dados guardados em ordem
  row-major logo depois. Shape e índice multi-dimensional são passados como
  "descritores" — arrays no mesmo estilo do `numares.ay` (`desc[0]` =
  quantidade, `desc[1..n]` = valores) — montados com os atalhos `shapeN`/
  `idxN` (`N` de 1 a 5) pra não precisar declarar e preencher um array na
  mão. Principais funções: criação (`zeros_nd`, `ones_nd`, `full_nd`,
  `copy_nd`), metadados (`ndim_nd`, `size_nd`, `dim_nd`, `shape_nd`,
  `strides_nd`), acesso (`get_nd`, `set_nd`, com checagem de limites),
  elementwise (`add_nd`, `sub_nd`, `mul_nd`, `div_nd`, `scale_nd`), reduções
  (`sum_nd`, `prod_nd`, `amin_nd`, `amax_nd`, `mean_nd`, `variance_nd`,
  `std_nd`), reformatação (`reshape_nd`, `flatten_nd`, `from_flat_nd`,
  `transpose_nd` com permutação arbitrária de eixos) e impressão
  (`print_nd`, com colchetes aninhados de acordo com o shape). Exemplo:
  ```
  import "stdlib/tensor.ay"

  fn main() {
      var t = zeros_nd(shape3(2, 3, 4))   // tensor 2x3x4, tudo zero
      set_nd(t, idx3(0, 1, 2), 99)
      print(get_nd(t, idx3(0, 1, 2)))      // 99
      print(size_nd(t))                    // 24 (2*3*4)

      var a = full_nd(shape2(2, 3), 5)
      var b = ones_nd(shape2(2, 3))
      print_nd(add_nd(a, b))                // [[6, 6, 6], [6, 6, 6]]
      print(mean_nd(a))                     // 5.0

      var at = transpose_nd(a, idx2(1, 0))  // transposta (3x2)
      print_shape_nd(at)                    // (3, 2)
      return 0
  }
  ```


## Gerenciador de pacotes (aresy install)

Além das bibliotecas locais (`import "arquivo.ay"`), dá pra instalar
pacotes de terceiros publicados pela comunidade:

```
aresy install numares            # procura "numares" no índice central
                                  # (aresy-index) e instala
aresy install https://github.com/fulano/lib-x   # instala direto de um
                                  # repositório git
aresy install https://raw.githubusercontent.com/fulano/lib-x/main/lib-x.ay
                                  # ou de um link direto pra um .ay cru
aresy uninstall numares           # remove
aresy list                        # lista dependências e se cada uma
                                   # está instalada
aresy install                     # sem argumento: instala tudo que
                                   # está no aresy.json do projeto
```

Um pacote instalado vai pra `ares_packages/<nome>/` e fica disponível
automaticamente pra `import <nome>` — não precisa de nenhuma sintaxe
nova, é o mesmo `import` de sempre. As dependências do projeto ficam
registradas num `aresy.json` na raiz (nome -> URL), parecido com um
`package.json`/`requirements.txt` bem simples; ele é criado/atualizado
sozinho a cada `aresy install <algo>`.

Pacotes sem URL explícita (`aresy install <nome>`) são resolvidos
consultando o **aresy-index**, um índice central mantido no GitHub.
Isso significa que instalar um pacote faz uma requisição de rede e,
mais cedo ou mais tarde, compila e roda código de terceiros — trate
`aresy install` com o mesmo cuidado que teria com `pip install` ou
`npm install`: só instale de nomes/URLs em que você confia.

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
- **"Instruction does not dominate all uses"** — `var` (ou a variável de
  `catch`) declarada dentro de um `if`/`try` e reaproveitada em outro ramo
  irmão (ex.: dois `catch e` diferentes na mesma função) gerava um
  `alloca` que o LLVM rejeitava, porque o registrador só existia dentro de
  um branch específico e não "dominava" o outro. Corrigido hoistando
  (movendo) todo `alloca` de variável local pro início da função, antes de
  qualquer `if`/`while`/`try` — é o mesmo jeito que o clang gera código
  pra variáveis locais em C.
- **`-lm` duplicado na hora de linkar** quando o programa faz
  `import "m"` explicitamente (libm já é linkada por padrão em todo
  programa, com ou sem esse import).
- **Escape de string corrompia UTF-8** — `"coração"` virava lixo tipo
  `"coraÃ§Ã£o"` porque o decode antigo (`unicode_escape`) tratava cada byte
  como um caractere Latin-1 antes de reaplicar os escapes. Trocado por
  `codecs.escape_decode`, que preserva UTF-8 multi-byte corretamente.
- **Divisão por zero crashava o binário** (`SIGFPE` em `i64`, `inf`/`nan`
  silencioso em `double`) — agora as duas viram uma exceção catchável
  (`throw "divisao por zero"`), consistente com o resto do mecanismo de
  `try`/`catch`.

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
