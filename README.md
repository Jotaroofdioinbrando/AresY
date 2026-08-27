# aresY

Linguagem aresY: sintaxe própria, compila pra LLVM IR e usa o `clang` como
backend (binário nativo de verdade, não interpretado).

Tipos (`i64`/`double`/`str`/`bool`), `struct` com campos nomeados,
arrays nativos de `double`, funções com anotação de tipo opcional,
`try`/`catch`/`throw`, ponteiro de função, `extern fn` (chama biblioteca
C), sistema de `import` de arquivos `.ay`, coletor de lixo (Boehm GC) e
um gerenciador de pacotes (`aresy install`) pra puxar bibliotecas de
terceiros.

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
    for i = 0; i < 3; i = i + 1 { print(i) }

    try {
        if x == 0 { throw "x não pode ser zero" }
    } catch e {
        print("erro: " + e)
    }

    return 0
}
```

- `var x = expr` — declaração; `x = expr` — reatribuição
- `if cond { } else { }`, `while cond { }`, `for init; cond; post { }`,
  `break`, `continue`, `return expr`
- Aritmética `+ - * / %`, comparação `== != < > <= >=`, bitwise `& | ^`
  (só com inteiros), unário `-`
- `true` / `false` (`bool`/`i1`; `i64` também vira booleano em condições)
- Strings: concatenação com `+`, `==`/`!=` por conteúdo, `len(s)`,
  `upper(s)`, `lower(s)`, `substr(s, i, tam)`, `char_at(s, i)`, `str(n)`
- Arrays: `array(n)` continua sendo `i64` fixo, sem bounds checking e
  sem `free` explícito; `darray(n)` cria `double[]` nativo e `dmat(r,c)`
  cria `double[][]` nativo para uso com `matmul(a,b)`
- Structs: `struct Nome { campo: tipo, ... }` com acesso por ponto e
  literal `Nome { campo: valor, ... }`
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
- Builtins nativos: `darray(n)`, `dmat(r,c)`, `matmul(a,b)`

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
- `stdlib/vector.ay` — vetor dinâmico: um array de `i64` que **cresce**
  sozinho. O `array(n)` nativo do aresY tem tamanho fixo (não dá pra
  realocar); este módulo resolve isso do jeito clássico do `realloc`
  em C — quando falta espaço, aloca um array novo maior (dobrando a
  capacidade), copia os dados antigos pra ele e passa a usar o novo.
  Por causa disso, toda operação que **pode** precisar crescer o
  vetor (`vec_push`, `vec_insert`, `vec_reserve`, `vec_extend`,
  `vec_concat`) devolve o vetor atualizado — **sempre reatribua o
  retorno**: `v = vec_push(v, x)`. Operações que só mexem no conteúdo
  sem nunca realocar (`vec_set`, `vec_pop`, `vec_remove`, `vec_clear`,
  `vec_fill`) não precisam de reatribuição. Principais funções:
  criação (`vec_new`), metadados (`vec_len`, `vec_cap`, `vec_is_empty`),
  acesso (`vec_get`, `vec_set`, `vec_front`, `vec_back`, com checagem de
  limites), inserção/remoção (`vec_push`, `vec_pop`, `vec_insert`,
  `vec_remove`, `vec_clear`), combinação (`vec_extend`, `vec_concat`),
  utilidades (`vec_copy`, `vec_fill`, `vec_sum`, `vec_contains`,
  `vec_index_of`), interoperabilidade com arrays estilo `numares.ay`
  (`vec_to_array`, `vec_from_array`) e impressão (`print_vec`). Exemplo:
  ```
  import "stdlib/vector.ay"

  fn main() {
      var v = vec_new(2)          // capacidade inicial 2
      var i = 0
      while i < 10 {
          v = vec_push(v, i * i)  // cresce sozinho (2 -> 4 -> 8 -> 16)
          i = i + 1
      }
      print_vec(v)                 // [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
      print(vec_len(v))            // 10
      print(vec_cap(v))            // 16

      var x = vec_pop(v)           // 81 (não precisa reatribuir)
      v = vec_insert(v, 2, 999)    // [0, 1, 999, 4, 9, ...]
      return 0
  }
  ```
- `stdlib/tensor_d.ay` — tensores dinâmicos N-dimensionais de **ponto
  flutuante** (`double`) — a versão "de verdade" do `tensor.ay` (que só
  guarda `i64`), pensada pra redes tipo Transformer (matmul, attention,
  softmax, layer_norm) e simulação numérica tipo Brian2. Mesmo layout do
  `tensor.ay` (cabeçalho com ndim/shape/strides), só que cada slot de
  dado guarda `to_raw(double)` em vez do `i64` puro; reaproveita
  `shape1..shape5`/`idx1..idx5` do `tensor.ay` (que já vem importado
  junto). **Não tem autograd** — é um motor de forward pass, não de
  treino. Principais funções: criação (`t_zeros`, `t_ones`, `t_full`,
  `t_copy`), acesso (`t_get`/`t_set` com descritor, e os atalhos mais
  rápidos `t_get1`/`t_set1`, `t_get2`/`t_set2`, `t_get3`/`t_set3` pra
  1D/2D/3D sem montar descritor a cada chamada), elemento a elemento
  (`t_add`, `t_sub`, `t_mul`, `t_div`, `t_scale`, `t_add_scalar`, `t_neg`),
  reduções (`t_sum`, `t_prod`, `t_min`, `t_max`, `t_mean`, `t_variance`,
  `t_std`), operações de matriz 2D (`t_matmul`, `t_transpose2`, `t_row`,
  `t_add_row_bias` — o único broadcasting que a lib faz, de propósito —,
  `t_sum_axis1`, `t_max_axis1`), ativações (`t_relu`, `t_sigmoid`,
  `t_tanh`, `t_gelu`, `t_exp`), os blocos prontos de um Transformer
  (`t_softmax_row`, `t_layer_norm`, `t_linear` = `x @ w + b`,
  `t_attention` = scaled dot-product attention completa), impressão
  (`t_print`, `t_print_shape`) e uma lista dinâmica de `double` que
  cresce sozinha — o `dlist` (`dlist_new`, `dlist_push`, `dlist_get`,
  `dlist_to_tensor`...) — útil pra ir acumulando algo de tamanho
  desconhecido de antemão (embeddings sendo montados, trem de spikes
  de uma simulação). Exemplo:
  ```
  import "stdlib/tensor_d.ay"

  fn main() {
      var x = t_full(shape2(2, 3), 1.5)
      var w = t_ones(shape2(3, 4))
      var b = t_zeros(shape1(4))
      var y = t_linear(x, w, b)      // y = x @ w + b
      t_print(y)

      var q = t_full(shape2(2, 4), 0.5)
      var k = t_full(shape2(2, 4), 0.3)
      var v = t_full(shape2(2, 4), 2.0)
      t_print(t_attention(q, k, v))   // scaled dot-product attention

      var l = dlist_new(2)            // lista de double que cresce
      var i = 0
      while i < 5 {
          dlist_push(l, i * 1.5)       // não precisa reatribuir "l"
          i = i + 1
      }
      t_print(dlist_to_tensor(l))      // [0, 1.5, 3, 4.5, 6]
      return 0
  }
  ```
- `stdlib/autograd.ay` — diferenciação automática (**reverse-mode
  autograd**), construída em cima do `tensor_d.ay`. É o motor por trás
  de treinar qualquer coisa (regressão, MLP, atenção) sem derivar nada
  à mão: cada `Var` guarda seu valor (um tensor), o gradiente acumulado,
  os pais que o geraram e um **ponteiro de função** pra sua derivada
  local; `ag_backward(saida)` percorre esse grafo de trás pra frente
  (ordenação topológica) chamando cada derivada e acumulando gradiente
  nos pais — igual PyTorch faz, só que sem operator overloading (aresY
  não tem), então cada operação é uma função `ag_*` explícita em vez de
  `+`/`*` comuns. Validei as fórmulas mais complexas (`layer_norm`,
  `softmax`, `matmul`) contra gradiente numérico por diferenças finitas
  — bateram na casa de `1e-9` de erro, dentro do esperado. Principais
  funções: criação/acesso de nó (`ag_leaf`, `ag_value`, `ag_grad`,
  `ag_zero_grad`), aritmética (`ag_add`, `ag_sub`, `ag_mul`, `ag_div`,
  `ag_neg`, `ag_scale`, `ag_add_scalar`), matriz 2D (`ag_matmul`,
  `ag_transpose2`, `ag_add_row_bias`), reduções (`ag_sum`, `ag_mean`),
  ativações (`ag_relu`, `ag_sigmoid`, `ag_tanh`, `ag_exp`), os blocos de
  Transformer (`ag_softmax_row`, `ag_layer_norm`, `ag_linear` = `x@w+b`,
  `ag_attention` = scaled dot-product attention), treino (`ag_sgd_step`)
  e depuração (`ag_print`). **Gradientes acumulam** entre chamadas de
  `ag_backward` (mesmo comportamento do PyTorch) — chame `ag_zero_grad`
  nos parâmetros antes de cada passo novo, ou o gradiente do passo
  anterior soma junto. `ag_scale`/`ag_layer_norm` recebem um fator/eps
  **constante** (não um `Var`) — não há gradiente calculado em relação
  a esse parâmetro, só no tensor de entrada. `gelu` ainda não tem
  backward (a derivada exata da aproximação tanh é longa); use
  `ag_relu`/`ag_tanh`/`ag_sigmoid` enquanto isso. Exemplo — uma camada
  linear + ReLU + mean, com um passo de SGD:
  ```
  import "stdlib/autograd.ay"

  fn main() {
      var x = ag_leaf(t_full(shape2(2, 3), 1.0))
      var w = ag_leaf(t_full(shape2(3, 4), 0.5))
      var b = ag_leaf(t_zeros(shape1(4)))

      var h = ag_relu(ag_linear(x, w, b))
      var loss = ag_mean(h)

      ag_backward(loss)
      t_print(ag_grad(w))     // dL/dw

      ag_sgd_step(w, 0.01)    // w.value -= 0.01 * w.grad
      ag_zero_grad(w)
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
- **`matmul(a, b)` nativo para `double[][]`** — o compilador agora
  reconhece o layout nativo de matriz 2D em `double` e gera o laço de
  multiplicação direto em LLVM IR, sem depender da stdlib.

## Limitações atuais

- Parâmetros de função aceitam `i64`/`double`/`str`, mas ponteiro de
  função como argumento (callback) assume sempre `i64` — sem checagem de
  tipo real entre o que foi passado e como é chamado.
- Arrays não têm bounds checking; só guardam `i64`.
- `array(n)` continua sendo `i64` puro; `darray`/`dmat` cobrem os casos
  nativos de `double`.
- Sem interpolação/f-strings — concatenação com `+` cobre o caso básico.
- `import "arquivo.ay"` não tem namespace de verdade: tudo que a
  biblioteca declara no topo do arquivo entra no escopo global de quem
  importou (sem exportação seletiva, sem `as apelido`).
