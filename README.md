# aresY

Linguagem aresY: sintaxe própria (baseada no protótipo antigo). Tem dois
jeitos de rodar um programa:

- **Modo dinâmico (interpretado)** — roda na hora, sem clang, tipo
  `python arquivo.py`. É o que dá suporte ao REPL interativo também.
- **Modo compilado** — sintaxe própria → LLVM IR → binário nativo via clang.
  Mais rápido, mas precisa do clang instalado.

## Instalar o comando `aresy` no Termux

Assim dá pra digitar só `aresy` no terminal e cair direto no modo
interativo, igual quando você digita `python` sozinho.

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
aresy                          # abre o REPL (modo interativo, dinâmico)
aresy programa.ay              # interpreta e roda direto, sem compilar
aresy run programa.ay          # igual acima, forma explícita
aresy build programa.ay saida.ll   # gera LLVM IR (fluxo antigo)
```

Pra virar binário nativo depois do `build`:
```
clang -O3 -ffast-math saida.ll -lm -o programa
./programa
```

Se der erro de target no seu aparelho, gere o IR passando o triple certo:
```
aresy build exemplo.ay saida.ll --triple aarch64-unknown-linux-android24
```

## Modo interativo (REPL)

```
$ aresy
aresY — modo interativo (dinâmico, sem compilar pra binário)
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

Variáveis e funções declaradas ficam disponíveis pro resto da sessão
(igual ao REPL do Python). Blocos com `{ }` (fn/if/while) podem ser escritos
em várias linhas — o prompt muda pra `...` até fechar a chave. Toda
expressão "solta" (sem `print`) tem o resultado ecoado automaticamente.

### Diferenças do modo dinâmico em relação ao compilado

- Não tem tipos fixos: `var x = 10` depois aceitar `x = 1.5` sem erro
  (no modo compilado, o tipo da variável é travado na primeira atribuição).
- Não gera binário nem precisa de clang — roda direto em Python por baixo
  dos panos, então é mais lento pra código pesado (loops gigantes, etc.).
  Pra isso, use `aresy build` + clang.

## Sintaxe suportada

- `fn nome(a, b) { ... }` — funções (parâmetros são sempre i64)
- `var x = expr` — declaração (obrigatória antes de usar a variável)
- `x = expr` — reatribuição
- `if cond { } else { }`
- `while cond { }`
- `return expr` (ou `return` sem valor)
- `print(expr)` ou `print("texto")`
- Aritmética: `+ - * / %`, comparações `== != < > <= >=`, unário `-`
- `true` / `false` — literais booleanos (agora funcionam; antes eram
  reconhecidos pelo lexer mas o parser ignorava)
- `array(n)` — aloca array de n inteiros (malloc, sem free — cuidado com uso longo)
- `arr[i]` / `arr[i] = expr` — leitura/escrita no array (leitura solta, sem
  atribuição, também funciona agora — antes só parseava se viesse um `=` depois)
- Builtins: `sqrt(x)`, `time()`, `random(n)`, `input()`

## O que mudou em relação ao protótipo antigo (bugs corrigidos)

- Tipo de cada valor agora é rastreado por tabela de símbolos de verdade,
  não adivinhado por substring do nome do registrador.
- `%` agora é operador de módulo nativo do parser (antes quebrava o parsing).
- Funções podem retornar valor (`i64` ou `double`), não só `void`.
- `return` dentro do `main` agora gera `ret i32` corretamente (o protótipo
  antigo geraria um erro de tipo no LLVM aqui).
- `arr[i]` como expressão solta (sem `=` depois) agora parseia — antes o
  parser sempre exigia uma atribuição e quebrava com `SyntaxError`.
- `true` / `false` agora são utilizáveis como literais — antes o token
  existia no lexer mas o parser não sabia o que fazer com ele.

## Limitações atuais (v1)

- Parâmetros de função são sempre `i64` — passar float pra função ainda não
  tem suporte (fica pro type-checker mais robusto, com genéricos).
- Sem strings como valor (só literais em `print`).
- Arrays não têm bounds checking nem `free`.
- Sem structs/tipos compostos ainda.
