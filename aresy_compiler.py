"""
aresY compiler — sintaxe própria, compila para LLVM IR e usa clang como backend.

Sintaxe:
    fn soma(a, b) {
        return a + b
    }

    fn main() {
        var x = 10
        var y = soma(x, 5)
        var arr = array(5)
        arr[0] = y
        if arr[0] > 10 {
            print(arr[0])
        } else {
            print(0)
        }
        var i = 0
        while i < 3 {
            print(i)
            i = i + 1
        }
        var raiz = sqrt(2.0)
        print(raiz)
        return 0
    }

Diferenças em relação ao protótipo antigo (corrigidas):
  - tipo de cada valor é rastreado de verdade via tabela de símbolos, não
    adivinhado por substring do nome do registrador.
  - "%" é o operador de módulo nativo (não colide mais com o parser).
  - funções podem retornar valor (i64 ou double), não só void.
"""

import sys
import re
import struct
import math as _pymath

VERSION = "1.5.2"

HOW_TEXT = """\
aresY — resumo rápido da sintaxe (aresy --how)
================================================

Todo programa executável precisa de uma fn main() { ... }.
Comentário: // até o fim da linha.

--- Variáveis ---
    var x = 10            // tipo inferido pelo valor (i64/double/str)
    x = x + 1              // reatribuição (a variável já precisa existir)

--- Tipos ---
    i64             inteiro 64 bits (padrão pra números sem ponto)
    double (ou f64) ponto flutuante 64 bits
    str (ou string) texto
    bool / i1       booleano
    void            só usado em retorno de função / extern

--- Funções ---
    fn soma(a, b) {                     // sem anotação: parâmetros e
        return a + b                    // retorno assumem i64
    }
    fn media(a: double, b: double) -> double {   // com tipos explícitos
        return (a + b) / 2.0
    }
    fn saudacao(nome: str) -> str {
        return "Olá, " + nome
    }

--- Controle de fluxo ---
    if cond { ... } else { ... }        // "else" é opcional
    while cond { ... }
    for init; cond; post { ... }
    break                                // sai imediatamente do loop mais interno
    continue                             // pula pra próxima iteração
    return expr                          // ou "return" sozinho (void)

--- Operadores ---
    Aritméticos:  +  -  *  /  %
    Comparação:   ==  !=  <  >  <=  >=
    Bitwise:      &  |  ^   (só com inteiros)
    Unário:       -x

--- Literais ---
    10              inteiro
    3.14            float
    1e-7, 2.5E10    float em notação científica
    "texto"         string (aceita \\n \\t \\" \\\\ etc.)
    true / false    booleano (vira i1; i64 também vira bool em condições)

--- Strings ---
    a + b                    concatenação
    a == b, a != b            igualdade de conteúdo (não de ponteiro)
    len(s)                    tamanho
    upper(s) / lower(s)       maiúsculas / minúsculas
    substr(s, inicio, tam)    fatia
    char_at(s, i)             caractere na posição i (como string de 1)
    str(numero)               converte i64/double pra string

--- Arrays, matrizes e structs ---
    var arr = array(5)        // aloca 5 posições
    arr[0] = 42
    print(arr[0])
    // array(n) é i64 fixo, sem bounds checking.
    var xs: double[] = darray(4)
    var ms: double[][] = dmat(2, 3)
    var prod: double[][] = matmul(ms, dmat(3, 2))

    struct Ponto { x: double, y: double }
    var p = Ponto { x: 1.0, y: 2.0 }
    print(p.x)

--- Structs ---
    struct Nome { campo: tipo, outro: tipo }
    var n = Nome { campo: 10, outro: 3.14 }
    print(n.campo)

--- Exceções ---
    fn divide(a, b) {
        if b == 0 { throw "divisao por zero" }
        return a / b
    }
    try {
        var r = divide(10, 0)
    } catch e {
        print("Erro: " + e)     // "e" é sempre string
    }
    // uma exceção não capturada propaga pra cima da pilha de chamadas
    // até achar um catch; se nenhum try pegar, o programa imprime o
    // erro e sai com código 1.

--- Funções nativas (builtins) ---
    Matemática:  sqrt(x) sin(x) cos(x) tan(x) atan(x) atan2(y,x)
                 log(x) log10(x) exp(x) pow(b,e) floor(x) ceil(x)
                 abs(x) min(a,b) max(a,b) pi()
                 to_raw(double) -> i64    reinterpreta os bits (não
                 from_raw(i64) -> double  converte) — pra guardar double
                                           dentro de um array (que só
                                           guarda i64 por posição)
    Arrays nativos: darray(n) -> double[]  (comprimento + dados)
                    dmat(r,c) -> double[][]
                    matmul(a,b) -> double[][] (otimizado no compilador)
    Tempo:       time() -> segundos desde epoch (double)
                 sleep(segundos) -> pausa a execução (aceita float)
    Aleatório:   random(n) -> inteiro entre 0 e n-1
    E/S:         input() -> lê um i64 do teclado
                 read_line() -> lê uma linha (str, sem o \\n do fim)
                 read_file(caminho) -> conteúdo do arquivo (str)
                 write_file(caminho, conteudo) -> sobrescreve (retorna 1/0)
                 append_file(caminho, conteudo) -> acrescenta (retorna 1/0)
    print(expr)  imprime qualquer i64/double/str com \\n no final

--- Ponteiro de função (callback) ---
    fn somar(a, b) { return a + b }
    fn aplicar(func, x, y) { return func(x, y) }
    aplicar(somar, 2, 3)      // passa a função como valor (assume i64)

--- extern: chamar função de biblioteca C ---
    import "m"                          // linka -lm na hora de compilar
    extern fn cbrt(f64) -> f64           // tipos aceitos aqui: i64, f64, void
    cbrt(27.0)

--- import: bibliotecas nativas escritas em aresY (.ay) ---
    import "stdlib/mathx.ay"            // caminho relativo ao arquivo atual
    import geometria                     // sem aspas: procura geometria.ay
                                          // no mesmo diretório
    geometria.calcular_area_circulo(5.0) // chamada com prefixo (opcional,
                                          // é só documentação — a função
                                          // já está disponível sem prefixo
                                          // também)

    Bibliotecas que já vêm com o projeto (stdlib/):
      mathx.ay    quadrado, cubo, potencia, fatorial, eh_primo,
                  eh_par/eh_impar, mdc, mmc, clamp, media
      strings.ay  eh_vazia, repetir, inverter, eh_palindromo, contem
      numares.ay  arrays numéricos estilo NumPy (~70 funções) — arr[0]
                  guarda o tamanho, elementos ficam em arr[1..n]:
                    criação:    zeros(n) ones(n) full(n,v) arange(a,b,p)
                                zeros_2d(r,c) ones_2d(r,c) eye(n)
                    stats:      sum() mean() variance() std() median()
                                amin() amax() argmin() argmax() ptp()
                    elemento a elemento: add sub mul div mod_array
                                scale square power abs_array clamp_array
                    conjuntos:  unique isin intersect1d union1d setdiff1d
                    forma:      sort argsort flip roll concat repeat tile
                    matriz 2D:  transpose_2d matmul_2d det_2x2/3x3
                                inv_2x2 solve_2x2 matvec_mul
                  import "stdlib/numares.ay" pra usar.
      tensor.ay   tensores dinâmicos N-dimensionais (2D, 3D, 4D... — o
                  número de dimensões é decidido em tempo de execução).
                  Layout: t[0] = ndim, shape e strides no cabeçalho,
                  dados em row-major logo depois. Shape/índice são
                  passados como descritores (mesmo estilo do numares.ay:
                  desc[0] = quantidade, desc[1..n] = valores), montados
                  com os atalhos shapeN/idxN (N de 1 a 5):
                    criação:    zeros_nd(shape) ones_nd(shape)
                                full_nd(shape,v) copy_nd(t)
                    metadados:  ndim_nd(t) size_nd(t) dim_nd(t,eixo)
                                shape_nd(t) strides_nd(t)
                    acesso:     get_nd(t,idx) set_nd(t,idx,v)
                                (com checagem de limites)
                    elemento a elemento: add_nd sub_nd mul_nd div_nd
                                scale_nd
                    stats:      sum_nd() prod_nd() amin_nd() amax_nd()
                                mean_nd() variance_nd() std_nd()
                    forma:      reshape_nd() flatten_nd() from_flat_nd()
                                transpose_nd(t,perm) (permutação de eixos)
                    impressão:  print_nd(t) print_shape_nd(t)
                  import "stdlib/tensor.ay" pra usar.
      vector.ay   vetor dinâmico — array de i64 que CRESCE sozinho (o
                  array() nativo tem tamanho fixo). Cresce dobrando a
                  capacidade quando precisa; operações que podem
                  realocar (vec_push, vec_insert, vec_reserve, vec_extend,
                  vec_concat) devolvem o vetor atualizado — sempre
                  reatribua: `v = vec_push(v, x)`.
                    criação:    vec_new(cap)
                    metadados:  vec_len(v) vec_cap(v) vec_is_empty(v)
                    acesso:     vec_get(v,i) vec_set(v,i,val)
                                vec_front(v) vec_back(v)
                    inserção:   vec_push(v,val) vec_insert(v,i,val)
                    remoção:    vec_pop(v) vec_remove(v,i) vec_clear(v)
                    combinação: vec_extend(v,outro) vec_concat(a,b)
                    utilidades: vec_copy(v) vec_fill(v,val) vec_sum(v)
                                vec_contains(v,val) vec_index_of(v,val)
                    interop:    vec_to_array(v) vec_from_array(arr)
                                (arr no estilo numares.ay: arr[0]=n)
                    impressão:  print_vec(v)
                  import "stdlib/vector.ay" pra usar.
      tensor_d.ay tensores dinâmicos N-dimensionais de PONTO FLUTUANTE
                  (double) — a versão "de verdade" do tensor.ay pra redes
                  tipo Transformer (matmul, attention, softmax, layer_norm)
                  e simulação numérica tipo Brian2. Mesmo layout do
                  tensor.ay, mas cada slot de dado guarda to_raw(double).
                  Reusa shapeN/idxN do tensor.ay (import "tensor.ay" já
                  vem junto). Sem autograd — é motor de forward pass.
                    criação:    t_zeros(shape) t_ones(shape)
                                t_full(shape,v) t_copy(t)
                    metadados:  t_ndim(t) t_size(t) t_dim(t,eixo)
                                t_shape(t) t_strides(t)
                    acesso:     t_get(t,idx) t_set(t,idx,v) — e atalhos
                                mais rápidos t_get1/t_set1, t_get2/t_set2,
                                t_get3/t_set3 (evitam montar descritor)
                    elemento a elemento: t_add t_sub t_mul t_div t_scale
                                t_add_scalar t_neg
                    reduções:   t_sum() t_prod() t_min() t_max() t_mean()
                                t_variance() t_std()
                    matriz 2D:  t_matmul(a,b) t_transpose2(t) t_row(t,i)
                                t_add_row_bias(t,bias) t_sum_axis1(t)
                                t_max_axis1(t)
                    ativações:  t_relu(t) t_sigmoid(t) t_tanh(t) t_gelu(t)
                                t_exp(t)
                    transformer: t_softmax_row(t) t_layer_norm(t,eps)
                                t_linear(x,w,b) t_attention(q,k,v)
                    impressão:  t_print(t) t_print_shape(t)
                    lista dinâmica de double (dlist, cresce sozinha):
                                dlist_new(cap) dlist_len(l) dlist_push(l,v)
                                dlist_get(l,i) dlist_set(l,i,v)
                                dlist_clear(l) dlist_to_tensor(l)
                  import "stdlib/tensor_d.ay" pra usar.
      autograd.ay diferenciação automática (reverse-mode), em cima do
                  tensor_d.ay — o motor por trás de treinar qualquer coisa
                  (regressão, MLP, atenção) sem derivar nada à mão. Cada
                  "Var" guarda valor + gradiente + como foi calculado;
                  ag_backward percorre o grafo de trás pra frente.
                    nó (Var):   ag_leaf(tensor) ag_value(v) ag_grad(v)
                                ag_zero_grad(v) ag_backward(saida)
                    aritmética: ag_add ag_sub ag_mul ag_div ag_neg
                                ag_scale(a,fator) ag_add_scalar(a,c)
                    matriz 2D:  ag_matmul ag_transpose2 ag_add_row_bias
                    reduções:   ag_sum(a) ag_mean(a)
                    ativações:  ag_relu ag_sigmoid ag_tanh ag_exp
                    transformer: ag_softmax_row ag_layer_norm(a,eps)
                                ag_linear(x,w,b) ag_attention(q,k,v)
                    treino:     ag_sgd_step(v,lr) — w.value -= lr*w.grad
                    depuração:  ag_print(v)
                  Gradientes ACUMULAM entre chamadas de ag_backward (igual
                  PyTorch) — use ag_zero_grad nos parâmetros antes de cada
                  passo novo. Funções que multiplicam por uma constante
                  (ag_scale, ag_layer_norm) não são diferenciáveis nesse
                  parâmetro — só no tensor de entrada.
                  import "stdlib/autograd.ay" pra usar.

--- Pacotes de terceiros (aresy install) ---
    aresy install                instala tudo que já foi registrado
                                  como dependência neste diretório
    aresy install <nome>         procura <nome> no índice central
                                  (aresy-index) e instala
    aresy install <url> [nome]   instala direto de uma URL — repo git
                                  ou link cru pra um arquivo .ay
    aresy uninstall <nome>       remove uma dependência
    aresy list                   lista as dependências e se cada uma
                                  está instalada

    Pacotes instalados vão pra ares_packages/<nome>/ e ficam visíveis
    pra "import <nome>" automaticamente — não precisa de sintaxe nova.
    Atenção: instalar um pacote baixa e (na próxima vez que for usado)
    compila/roda código de terceiros — só instale de fontes em que
    você confia, do mesmo jeito que faria com qualquer gerenciador de
    pacotes.

--- Rodando programas ---
    aresy                       modo interativo (REPL, nativo via clang)
    aresy programa.ay           compila e roda direto
    aresy run programa.ay       mesma coisa, explícito
    aresy build programa.ay saida.ll   gera só o LLVM IR
    aresy install / uninstall / list   gerenciador de pacotes (ver acima)
    aresy --version             mostra a versão
    aresy --help                lista de comandos e flags
    aresy --how                 este resumo de sintaxe

    Flags extras (valem em qualquer comando acima):
    --triple TRIPLE   define o target LLVM (ex.: pra compilar cruzado)
    --no-gc           compila sem o coletor de lixo (Boehm GC), usa
                      malloc puro — útil se não tiver a libgc instalada
"""


# ---------------------------------------------------------------------------
# 1. LEXER
# ---------------------------------------------------------------------------

TOKEN_SPEC = [
    ("FLOAT",    r"\d+\.\d+(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+"),
    ("INT",      r"\d+"),
    ("STRING",   r'"(?:\\.|[^"\\])*"'),
    ("ID",       r"[A-Za-z_][A-Za-z0-9_]*"),
    ("COMMENT",  r"//.*"),
    ("OP",       r"->|==|!=|<=|>=|[+\-*/%=<>(){}\[\],^&|~:.;]"),
    ("NEWLINE",  r"\n"),
    ("SKIP",     r"[ \t]+"),
]
MASTER_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC))
KEYWORDS = {"fn", "if", "else", "while", "return", "print", "var", "true", "false",
            "extern", "import", "try", "catch", "throw", "break", "for", "continue",
            "struct"}

# Nomes de tipo aceitos em anotações (fn e extern). Mapeiam pro vocabulário
# interno do compilador: "i64", "double", "str", "void".
TYPE_ALIASES = {
    "i64": "i64",
    "i1": "i1",
    "bool": "i1",
    "boolean": "i1",
    "f64": "double",
    "double": "double",
    "str": "str",
    "string": "str",
    "void": "void",
}


def parse_type_spec_from_name(raw):
    """Converte um nome de tipo opcionalmente com sufixos de array em uma
    representação estruturada.

    Exemplos:
      i64        -> "i64"
      double[]   -> ("array", "double", 1)
      Foo[][]    -> ("array", ("struct", "Foo"), 2)
    """
    if not raw:
        raise SyntaxError("Nome de tipo vazio")
    rank = raw.count("[]")
    base = raw.replace("[]", "")
    if base in TYPE_ALIASES:
        t = TYPE_ALIASES[base]
    else:
        t = ("struct", base)
    if rank:
        return ("array", t, rank)
    return t


def type_spec_to_text(t):
    if isinstance(t, tuple):
        if not t:
            return "<vazio>"
        if t[0] == "struct":
            return t[1]
        if t[0] == "array":
            return type_spec_to_text(t[1]) + "[]" * t[2]
    return str(t)


def is_array_type(t):
    return isinstance(t, tuple) and len(t) >= 3 and t[0] == "array"


def array_base_type(t):
    return t[1] if is_array_type(t) else None


def array_rank(t):
    return t[2] if is_array_type(t) else 0


def is_struct_type(t):
    return isinstance(t, tuple) and len(t) == 2 and t[0] == "struct"


def is_opaque_type(t):
    return is_array_type(t) or is_struct_type(t)


def types_compatible(lhs, rhs):
    return lhs == rhs


def resolve_type_name(raw):
    if raw not in TYPE_ALIASES:
        raise SyntaxError(
            f"Tipo '{raw}' desconhecido — use i64, double (ou f64), str (ou string) ou void"
        )
    return TYPE_ALIASES[raw]


class Token:
    def __init__(self, kind, value):
        self.kind, self.value = kind, value
    def __repr__(self):
        return f"{self.kind}:{self.value}"


def tokenize(code):
    tokens = []
    pos = 0
    for m in MASTER_RE.finditer(code):
        if m.start() != pos:
            bad = code[pos:m.start()]
            line = code.count("\n", 0, pos) + 1
            raise SyntaxError(f"Caractere não reconhecido {bad!r} na linha {line}")
        pos = m.end()
        kind, value = m.lastgroup, m.group()
        if kind in ("SKIP", "COMMENT", "NEWLINE"):
            continue
        if kind == "ID" and value in KEYWORDS:
            kind = value.upper()
        tokens.append(Token(kind, value))
    if pos != len(code):
        bad = code[pos:]
        line = code.count("\n", 0, pos) + 1
        raise SyntaxError(f"Caractere não reconhecido {bad!r} na linha {line}")
    tokens.append(Token("EOF", None))
    return tokens


# ---------------------------------------------------------------------------
# 2. AST
# ---------------------------------------------------------------------------

class Num:
    def __init__(self, value, is_float): self.value, self.is_float = value, is_float
class Str:
    def __init__(self, value):
        raw = value[1:-1]
        import codecs
        self.value = codecs.escape_decode(bytes(raw, "utf-8"))[0].decode("utf-8")
class Bool:
    def __init__(self, value): self.value = value
class Var:
    def __init__(self, name): self.name = name
class VarDecl:
    def __init__(self, name, expr, decl_type=None):
        self.name, self.expr, self.decl_type = name, expr, decl_type
class Assign:
    def __init__(self, name, expr): self.name, self.expr = name, expr
class IndexGet:
    def __init__(self, arr, idx): self.arr, self.idx = arr, idx
class IndexSet:
    def __init__(self, arr, idx, expr): self.arr, self.idx, self.expr = arr, idx, expr
class BinOp:
    def __init__(self, op, left, right): self.op, self.left, self.right = op, left, right
class UnaryOp:
    def __init__(self, op, operand): self.op, self.operand = op, operand
class Call:
    def __init__(self, name, args): self.name, self.args = name, args
class Print:
    def __init__(self, expr): self.expr = expr
class If:
    def __init__(self, cond, then_b, else_b): self.cond, self.then_b, self.else_b = cond, then_b, else_b
class While:
    def __init__(self, cond, body): self.cond, self.body = cond, body
class FuncDef:
    def __init__(self, name, params, body, param_types=None, ret_type=None):
        self.name, self.params, self.body = name, params, body
        # tipagem unificada: cada parâmetro tem um tipo real (i64/double/str).
        # None = sem anotação — resolvido em compile_program via inferência
        # leve de uso (ver _infer_param_type); se não achar evidência, cai
        # em i64 (compatível com código antigo).
        self.param_types = param_types if param_types is not None else [None] * len(params)
        self.ret_type = ret_type
class Return:
    def __init__(self, expr): self.expr = expr
class ExprStmt:
    def __init__(self, expr): self.expr = expr
class ExternDecl:
    def __init__(self, name, param_types, ret_type):
        self.name, self.param_types, self.ret_type = name, param_types, ret_type
class ImportDecl:
    def __init__(self, name): self.name = name
class StructDef:
    def __init__(self, name, fields):
        self.name, self.fields = name, fields
class StructLiteral:
    def __init__(self, name, fields):
        self.name, self.fields = name, fields
class FieldGet:
    def __init__(self, base, field):
        self.base, self.field = base, field
class FieldSet:
    def __init__(self, base, field, expr):
        self.base, self.field, self.expr = base, field, expr
class For:
    def __init__(self, init, cond, post, body):
        self.init, self.cond, self.post, self.body = init, cond, post, body
class TryCatch:
    def __init__(self, try_body, catch_var, catch_body):
        self.try_body, self.catch_var, self.catch_body = try_body, catch_var, catch_body
class Throw:
    def __init__(self, expr): self.expr = expr
class Break:
    pass
class Continue:
    pass


# ---------------------------------------------------------------------------
# 3. PARSER
# ---------------------------------------------------------------------------

class Parser:
    def __init__(self, tokens):
        self.tokens, self.pos = tokens, 0
        self.known_structs = set()

    def peek(self, offset=0): return self.tokens[self.pos + offset]
    def advance(self):
        t = self.tokens[self.pos]; self.pos += 1; return t
    def expect(self, kind):
        t = self.advance()
        if t.kind != kind:
            raise SyntaxError(f"Esperado {kind}, veio {t.kind} ({t.value})")
        return t

    def parse_program(self):
        for i, tok in enumerate(self.tokens[:-1]):
            if tok.kind == "STRUCT" and i + 1 < len(self.tokens) and self.tokens[i + 1].kind == "ID":
                self.known_structs.add(self.tokens[i + 1].value)
        stmts = []
        while self.peek().kind != "EOF":
            stmts.append(self.parse_statement())
        return stmts

    def parse_block(self):
        self.expect("OP")  # {
        stmts = []
        while self.peek().value != "}":
            stmts.append(self.parse_statement())
        self.expect("OP")  # }
        return stmts

    def parse_type(self):
        raw = self.expect("ID").value
        while self.peek().value == "[" and self.peek(1).value == "]":
            self.advance()
            self.advance()
            raw += "[]"
        return parse_type_spec_from_name(raw)

    def parse_simple_statement(self):
        tok = self.peek()
        if tok.kind == "VAR":
            self.advance()
            name = self.expect("ID").value
            decl_type = None
            if self.peek().value == ":":
                self.advance()
                decl_type = self.parse_type()
            self.expect("OP")  # =
            expr = self.parse_expr()
            return VarDecl(name, expr, decl_type=decl_type)
        if tok.kind == "ID" and self.peek(1).value == "=":
            name = self.advance().value
            self.advance()
            return Assign(name, self.parse_expr())
        if tok.kind == "ID" and self.peek(1).value == "[":
            name = self.advance().value
            indices = []
            while self.peek().value == "[":
                self.advance()
                indices.append(self.parse_expr())
                self.expect("OP")
            base = Var(name)
            if self.peek().value == "=":
                self.advance()
                expr = self.parse_expr()
                target = base
                for idx in indices[:-1]:
                    target = IndexGet(target, idx)
                return IndexSet(target, indices[-1], expr)
            node = base
            for idx in indices:
                node = IndexGet(node, idx)
            return ExprStmt(node)
        expr = self.parse_expr()
        return ExprStmt(expr)

    def parse_until(self, stop_value):
        stmt = self.parse_simple_statement()
        return stmt

    EXTERN_TYPES = {"i64", "f64", "void"}

    def parse_statement(self):
        tok = self.peek()
        if tok.kind == "IMPORT":
            self.advance()
            if self.peek().kind == "STRING":
                lib = self.advance().value[1:-1]
                return ImportDecl(lib)
            # import sem aspas: nome de módulo — procura "<nome>.ay" no
            # mesmo diretório do arquivo que faz o import (ex.: 'import
            # geometria' carrega 'geometria.ay'). Depois disso, chamadas
            # qualificadas como 'geometria.calcular_area(x)' funcionam
            # (ver parse_atom) — o prefixo é só documentação, a função
            # já foi trazida pro escopo global pelo import em si.
            mod = self.expect("ID").value
            return ImportDecl(mod + ".ay")
        if tok.kind == "EXTERN":
            self.advance()
            self.expect("FN")
            name = self.expect("ID").value
            self.expect("OP")  # (
            param_types = []
            while self.peek().value != ")":
                t = self.expect("ID").value
                if t not in self.EXTERN_TYPES:
                    raise SyntaxError(f"Tipo '{t}' inválido em extern — use i64, f64 ou void")
                param_types.append(t)
                if self.peek().value == ",": self.advance()
            self.expect("OP")  # )
            ret_type = "i64"
            if self.peek().value == "->":
                self.advance()
                ret_type = self.expect("ID").value
                if ret_type not in self.EXTERN_TYPES:
                    raise SyntaxError(f"Tipo '{ret_type}' inválido em extern — use i64, f64 ou void")
            return ExternDecl(name, param_types, ret_type)
        if tok.kind == "FN": return self.parse_funcdef()
        if tok.kind == "IF": return self.parse_if()
        if tok.kind == "WHILE": return self.parse_while()
        if tok.kind == "FOR": return self.parse_for()
        if tok.kind == "TRY": return self.parse_try()
        if tok.kind == "THROW":
            self.advance()
            return Throw(self.parse_expr())
        if tok.kind == "BREAK":
            self.advance()
            return Break()
        if tok.kind == "CONTINUE":
            self.advance()
            return Continue()
        if tok.kind == "STRUCT":
            self.advance()
            name = self.expect("ID").value
            self.known_structs.add(name)
            self.expect("OP")  # {
            fields = []
            while self.peek().value != "}":
                fname = self.expect("ID").value
                self.expect("OP")  # :
                ftype = self.parse_type()
                fields.append((fname, ftype))
                if self.peek().value == ",":
                    self.advance()
            self.expect("OP")  # }
            return StructDef(name, fields)
        if tok.kind == "VAR":
            self.advance()
            name = self.expect("ID").value
            decl_type = None
            if self.peek().value == ":":
                self.advance()
                decl_type = self.parse_type()
            self.expect("OP")  # =
            expr = self.parse_expr()
            return VarDecl(name, expr, decl_type=decl_type)
        if tok.kind == "RETURN":
            self.advance()
            if self.peek().value in ("}",):
                return Return(None)
            return Return(self.parse_expr())
        if tok.kind == "PRINT":
            self.advance(); self.expect("OP")
            expr = self.parse_expr()
            self.expect("OP")
            return Print(expr)
        if tok.kind == "ID" and self.peek(1).value in ("=", "["):
            return self.parse_simple_statement()
        return ExprStmt(self.parse_expr())

    def parse_funcdef(self):
        self.advance()
        name = self.expect("ID").value
        self.expect("OP")  # (
        params = []
        param_types = []
        while self.peek().value != ")":
            pname = self.expect("ID").value
            ptype = None  # None = sem anotação (decidido depois: inferência leve ou i64)
            if self.peek().value == ":":
                self.advance()
                ptype = self.parse_type()
            params.append(pname)
            param_types.append(ptype)
            if self.peek().value == ",": self.advance()
        self.expect("OP")  # )
        ret_type = None
        if self.peek().value == "->":
            self.advance()
            ret_type = self.parse_type()
        body = self.parse_block()
        return FuncDef(name, params, body, param_types=param_types, ret_type=ret_type)

    def parse_if(self):
        self.advance()
        cond = self.parse_expr()
        then_b = self.parse_block()
        else_b = []
        if self.peek().kind == "ELSE":
            self.advance()
            else_b = self.parse_block()
        return If(cond, then_b, else_b)

    def parse_while(self):
        self.advance()
        cond = self.parse_expr()
        body = self.parse_block()
        return While(cond, body)

    def parse_for(self):
        self.advance()
        init = None
        cond = None
        post = None
        if self.peek().value != ";":
            init = self.parse_simple_statement()
        self.expect("OP")  # ;
        if self.peek().value != ";":
            cond = self.parse_expr()
        self.expect("OP")  # ;
        if self.peek().value != "{":
            post = self.parse_simple_statement()
        body = self.parse_block()
        return For(init, cond, post, body)

    def parse_try(self):
        self.advance()  # try
        try_body = self.parse_block()
        self.expect("CATCH")
        catch_var = self.expect("ID").value
        catch_body = self.parse_block()
        return TryCatch(try_body, catch_var, catch_body)

    def parse_expr(self): return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_bitwise()
        while self.peek().value in ("==", "!=", "<", ">", "<=", ">="):
            op = self.advance().value
            left = BinOp(op, left, self.parse_bitwise())
        return left

    def parse_bitwise(self):
        left = self.parse_add_sub()
        while self.peek().value in ("&", "|", "^"):
            op = self.advance().value
            left = BinOp(op, left, self.parse_add_sub())
        return left

    def parse_add_sub(self):
        left = self.parse_mul_div()
        while self.peek().value in ("+", "-"):
            op = self.advance().value
            left = BinOp(op, left, self.parse_mul_div())
        return left

    def parse_mul_div(self):
        left = self.parse_unary()
        while self.peek().value in ("*", "/", "%"):
            op = self.advance().value
            left = BinOp(op, left, self.parse_unary())
        return left

    def parse_unary(self):
        if self.peek().value == "-":
            self.advance()
            return UnaryOp("-", self.parse_unary())
        return self.parse_atom()

    def parse_atom(self):
        tok = self.peek()
        if tok.kind == "FLOAT":
            self.advance(); return Num(float(tok.value), True)
        if tok.kind == "INT":
            self.advance(); return Num(int(tok.value), False)
        if tok.kind == "STRING":
            self.advance(); return Str(tok.value)
        if tok.kind == "TRUE":
            self.advance(); return Bool(True)
        if tok.kind == "FALSE":
            self.advance(); return Bool(False)
        if tok.kind == "ID":
            name = self.advance().value
            if self.peek().value == "." and self.peek(1).kind == "ID":
                # chamada qualificada por módulo: 'modulo.funcao(args)'. O
                # prefixo é só pra documentar de onde a função veio — o
                # import já trouxe ela pro escopo global (mesma ideia de um
                # "#include"), então aqui a gente só usa o nome real.
                self.advance()  # .
                real_name = self.advance().value
                if self.peek().value == "(":
                    name = real_name
                else:
                    node = FieldGet(Var(name), real_name)
                    while self.peek().value == "." and self.peek(1).kind == "ID":
                        self.advance()
                        field = self.advance().value
                        node = FieldGet(node, field)
                    while self.peek().value == "[":
                        self.advance()
                        idx = self.parse_expr()
                        self.expect("OP")
                        node = IndexGet(node, idx)
                    return node
            if self.peek().value == "{" and name in self.known_structs:
                self.advance()
                fields = []
                while self.peek().value != "}":
                    fname = self.expect("ID").value
                    self.expect("OP")
                    fexpr = self.parse_expr()
                    fields.append((fname, fexpr))
                    if self.peek().value == ",":
                        self.advance()
                self.expect("OP")
                return StructLiteral(name, fields)
            if self.peek().value == "(":
                self.advance()
                args = []
                while self.peek().value != ")":
                    args.append(self.parse_expr())
                    if self.peek().value == ",": self.advance()
                self.expect("OP")
                return Call(name, args)
            node = Var(name)
            while self.peek().value == "." and self.peek(1).kind == "ID":
                self.advance()
                field = self.advance().value
                node = FieldGet(node, field)
            while self.peek().value == "[":
                self.advance()
                idx = self.parse_expr()
                self.expect("OP")
                node = IndexGet(node, idx)
            return node
        if tok.kind == "STRUCT":
            self.advance()
            name = self.expect("ID").value
            self.expect("OP")  # {
            fields = []
            while self.peek().value != "}":
                fname = self.expect("ID").value
                self.expect("OP")  # :
                fexpr = self.parse_expr()
                fields.append((fname, fexpr))
                if self.peek().value == ",":
                    self.advance()
            self.expect("OP")  # }
            return StructLiteral(name, fields)
        if tok.value == "(":
            self.advance()
            e = self.parse_expr()
            self.expect("OP")
            return e
        raise SyntaxError(f"Token inesperado: {tok}")


# ---------------------------------------------------------------------------
# 4. CODEGEN (LLVM IR) — tipo é rastreado de verdade, sem heurística de nome
# ---------------------------------------------------------------------------

BUILTIN_DECLARES = (
    'declare i32 @printf(i8*, ...)\n'
    'declare i32 @scanf(i8*, ...)\n'
    'declare i32 @gettimeofday(i8*, i8*)\n'
    'declare double @sqrt(double)\n'
    'declare i8* @malloc(i64)\n'
    'declare i32 @rand()\n'
    'declare void @srand(i32)\n'
    'declare i32 @usleep(i32)\n'
    'declare i64 @strlen(i8*)\n'
    'declare i8* @strcpy(i8*, i8*)\n'
    'declare i8* @strcat(i8*, i8*)\n'
    # --- GC (Boehm-Demers-Weiser, libgc, linkada via -lgc no clang) ---
    # Conservador (varre stack/registradores procurando ponteiros), mas
    # bem mais rápido que qualquer coletor "correto" de rastreamento
    # preciso escrito à mão — é o mesmo motor que Guile/Chicken usam.
    'declare void @GC_init()\n'
    'declare i8* @GC_malloc(i64)\n'
    # --- Math (libm, já linkada via -lm no clang) ---
    'declare double @sin(double)\n'
    'declare double @cos(double)\n'
    'declare double @tan(double)\n'
    'declare double @atan(double)\n'
    'declare double @atan2(double, double)\n'
    'declare double @log(double)\n'
    'declare double @log10(double)\n'
    'declare double @exp(double)\n'
    'declare double @pow(double, double)\n'
    'declare double @floor(double)\n'
    'declare double @ceil(double)\n'
    'declare double @fabs(double)\n'
    # --- Erros/exceções (try/catch/throw) ---
    'declare i32 @sprintf(i8*, i8*, ...)\n'
    'declare void @exit(i32)\n'
    # --- Strings avançadas & I/O ---
    'declare i32 @strcmp(i8*, i8*)\n'
    'declare i8* @strncpy(i8*, i8*, i64)\n'
    'declare i32 @toupper(i32)\n'
    'declare i32 @tolower(i32)\n'
    'declare i64 @read(i32, i8*, i64)\n'
    'declare i8* @fopen(i8*, i8*)\n'
    'declare i32 @fclose(i8*)\n'
    'declare i32 @fseek(i8*, i64, i32)\n'
    'declare i64 @ftell(i8*)\n'
    'declare i64 @fread(i8*, i64, i64, i8*)\n'
    'declare i64 @fwrite(i8*, i64, i64, i8*)\n'
    'declare i64 @getrandom(i8*, i64, i32)\n'
)
FMT_CONSTANTS = (
    '@fmt_int = private unnamed_addr constant [5 x i8] c"%ld\\0A\\00"\n'
    '@fmt_float = private unnamed_addr constant [4 x i8] c"%f\\0A\\00"\n'
    '@fmt_str = private unnamed_addr constant [4 x i8] c"%s\\0A\\00"\n'
    '@fmt_scan = private unnamed_addr constant [4 x i8] c"%ld\\00"\n'
    # formatos "crus" (sem \n), usados só pra converter número -> string
    # dentro de throw (ex.: "throw 42" vira a string "42")
    '@fmt_int_raw = private unnamed_addr constant [4 x i8] c"%ld\\00"\n'
    '@fmt_float_raw = private unnamed_addr constant [3 x i8] c"%f\\00"\n'
    '@fmt_uncaught = private unnamed_addr constant [25 x i8] '
    'c"Excecao nao tratada: %s\\0A\\00"\n'
    # modos de abertura de arquivo (fopen)
    '@fmt_mode_r = private unnamed_addr constant [2 x i8] c"r\\00"\n'
    '@fmt_mode_w = private unnamed_addr constant [2 x i8] c"w\\00"\n'
    '@fmt_mode_a = private unnamed_addr constant [2 x i8] c"a\\00"\n'
)
# Estado global de exceção: uma flag (0/1) + a mensagem (sempre uma string).
# É um mecanismo simples de propagação por "código de erro" — sem
# invoke/landingpad de verdade — mas cobre o caso comum de throw dentro
# de um try, e também throw dentro de uma função chamada de dentro do try
# (cada call site verifica a flag logo depois de chamar).
EXC_GLOBALS = (
    "@__ares_exc_flag = global i32 0\n"
    "@__ares_exc_msg = global i8* null\n"
)

class CompileError(Exception):
    pass


def fmt_double_literal(v):
    # LLVM IR exige que literais double tenham ponto decimal na mantissa
    # (ex.: "1e-07" é sintaxe inválida, mas "1.0e-07" seria válida). Pra
    # não depender da formatação "esperta" do Python (que varia conforme
    # a magnitude do número), sempre emitimos o literal como hex IEEE-754,
    # que o LLVM aceita sem ambiguidade em qualquer caso.
    bits = struct.unpack("<Q", struct.pack("<d", float(v)))[0]
    return f"0x{bits:016X}"


def llvm_escape_string(text):
    """Escapa bytes de uma string para literal de string do LLVM IR."""
    out = []
    for b in text.encode("utf-8"):
        if b == 0x5C:       # backslash
            out.append(r"\5C")
        elif b == 0x22:     # aspas
            out.append(r"\22")
        elif b == 0x0A:     # newline
            out.append(r"\0A")
        elif b == 0x0D:     # carriage return
            out.append(r"\0D")
        elif b == 0x09:     # tab
            out.append(r"\09")
        elif 0x20 <= b <= 0x7E:
            out.append(chr(b))
        else:
            out.append(f"\\{b:02X}")
    return "".join(out)


class CodeGen:
    def __init__(self, target_triple=None, use_gc=True):
        self.target_triple = target_triple
        self.use_gc = use_gc
        self.counter = 0
        self.strings = []
        self.functions = {}   # name -> {'params': [...], 'ret': tipo, 'extern': bool}
        self.structs = {}      # nome -> [(campo, tipo), ...]
        self.imports = []     # nomes de libs de "import" (viram -lNOME na hora de linkar)
        self.catch_stack = []      # labels dos catch ativos (mais interno primeiro), por função
        self.func_exc_exit = None  # label pra onde pular se uma exceção escapar de todo try da função atual
        self.loop_stack = []       # pilha de (continue_label, break_label)

    def new_id(self):
        self.counter += 1
        return self.counter

    def llvm_type(self, t):
        # "str" é rastreado internamente como tipo próprio, mas em LLVM
        # é sempre um ponteiro i8* (C string terminada em \0).
        if t == "str":
            return "i8*"
        if is_array_type(t) or is_struct_type(t):
            return "i8*"
        return t

    def type_name(self, t):
        return type_spec_to_text(t)

    def _struct_field_index(self, struct_name, field):
        if struct_name not in self.structs:
            raise CompileError(f"Struct '{struct_name}' não foi declarada")
        for idx, (fname, _) in enumerate(self.structs[struct_name]):
            if fname == field:
                return idx
        raise CompileError(f"Struct '{struct_name}' não possui o campo '{field}'")

    def _struct_field_type(self, struct_name, field):
        idx = self._struct_field_index(struct_name, field)
        return self.structs[struct_name][idx][1]

    def _default_zero(self, t):
        if t == "double":
            return "0.0"
        if t == "i1":
            return "0"
        if t == "void":
            return None
        if t == "str" or is_opaque_type(t):
            return "null"
        return "0"

    def _is_truthy_type(self, t):
        return t in ("i64", "i32", "i1", "double") or t == "str" or is_opaque_type(t)

    def _to_bool(self, lines, t, v):
        if t == "i1":
            return v
        uid = self.new_id()
        if t == "double":
            lines.append(f"  %bool_{uid} = fcmp une double {v}, 0.0")
        elif t == "str" or is_opaque_type(t):
            lines.append(f"  %bool_{uid} = icmp ne i8* {v}, null")
        else:
            v = self.cast(lines, t, v, "i64")
            lines.append(f"  %bool_{uid} = icmp ne i64 {v}, 0")
        return f"%bool_{uid}"

    def _type_compatible(self, expected, got):
        if expected == got:
            return True
        if expected == "i1" and got == "i64":
            return True
        if expected == "i64" and got == "i1":
            return True
        if expected == "double" and got == "i1":
            return True
        if expected == "double" and got == "i64":
            return True
        if expected == "i64" and got == "double":
            return True
        return False

    def _validate_type_spec(self, t, _seen=None):
        if _seen is None:
            _seen = set()
        if t is None:
            return
        if t in ("i64", "i32", "i1", "double", "str", "void"):
            return
        if is_struct_type(t):
            if t[1] in _seen:
                return
            if t[1] not in self.structs:
                raise CompileError(f"Tipo struct '{t[1]}' não foi declarado")
            _seen.add(t[1])
            for _, field_t in self.structs[t[1]]:
                self._validate_type_spec(field_t, _seen)
            _seen.remove(t[1])
            return
        if is_array_type(t):
            self._validate_type_spec(t[1], _seen)
            return
        raise CompileError(f"Tipo inválido: {self.type_name(t)}")

    # --- pré-varredura: adivinha o tipo de retorno de cada função pro header ---
    def _scan_return_type(self, body):
        found = {"type": "void"}
        def walk(stmts):
            for s in stmts:
                if isinstance(s, Return) and s.expr is not None:
                    found["type"] = self._guess_type(s.expr)
                elif isinstance(s, If):
                    walk(s.then_b); walk(s.else_b)
                elif isinstance(s, While):
                    walk(s.body)
                elif isinstance(s, TryCatch):
                    walk(s.try_body); walk(s.catch_body)
        walk(body)
        return found["type"]

    def _guess_type(self, node, known=None):
        # heurística leve só pra declarar o cabeçalho da função no LLVM
        # quando NÃO há anotação explícita de retorno ('-> tipo'); o valor
        # real de retorno é convertido (cast) se necessário no codegen.
        # 'known' é o mapa (nome -> tipo) das variáveis já hoistadas antes
        # desta, na ordem em que aparecem no corpo — sem isso, uma expressão
        # como "h1 * 0.4" não tinha como saber que 'h1' é double (o caso
        # base de Var não existia, então caía sempre no default i64).
        known = known or {}
        if isinstance(node, Num): return "double" if node.is_float else "i64"
        if isinstance(node, Str): return "str"
        if isinstance(node, StructLiteral):
            return ("struct", node.name)
        if isinstance(node, FieldGet):
            base_t = self._guess_type(node.base, known)
            if is_struct_type(base_t):
                return self._struct_field_type(base_t[1], node.field)
            return "i64"
        if isinstance(node, Var): return known.get(node.name, "i64")
        if isinstance(node, Call) and node.name in (
            "sqrt", "time", "sin", "cos", "tan", "atan", "atan2",
            "log", "log10", "exp", "floor", "ceil", "pow", "pi", "from_raw",
        ):
            return "double"
        if isinstance(node, Call) and node.name in ("darray", "dmat", "arrayd", "arrayd2"):
            if node.name in ("dmat", "arrayd2"):
                return ("array", "double", 2)
            return ("array", "double", 1)
        if isinstance(node, Call) and node.name == "matmul":
            return ("array", "double", 2)
        if isinstance(node, Call) and node.name in ("abs", "min", "max"):
            # polimórficas (i64 ou double, dependendo do argumento) — usa o
            # tipo adivinhado do primeiro argumento, mesma lógica do codegen
            # de verdade (ver gen_call).
            return self._guess_type(node.args[0], known) if node.args else "i64"
        if isinstance(node, Call) and node.name in ("upper", "lower", "substr", "char_at", "str",
                                                      "read_line", "read_file"):
            return "str"
        if isinstance(node, Call) and node.name in self.functions:
            # função do usuário (ou extern) já registrada — usa o tipo de
            # retorno real dela, em vez de cair no default 'i64'. Sem isso,
            # "var x = minha_str_func(...)" era hoistado como i64 (chute
            # errado) e depois batia de frente com o tipo real no codegen.
            return self.functions[node.name].get("ret", "i64")
        if isinstance(node, BinOp): return self._guess_type(node.left, known)
        if isinstance(node, UnaryOp): return self._guess_type(node.operand, known)
        return "i64"

    _STR_BUILTIN_FIRST_ARG = {"upper", "lower", "len", "substr", "char_at"}

    def _collect_calls_into(self, stmts, calls_by_name):
        """Varre uma lista de statements (recursivamente) catando toda
        chamada de função, agrupada por nome. Usado pela inferência de
        tipo de parâmetro por call-site (ver _infer_param_type_from_calls)
        — bem parecido com o walker de _infer_param_type, mas coletando
        TODAS as chamadas em vez de procurar uma evidência específica."""
        def walk_expr(e):
            if e is None:
                return
            if isinstance(e, Call):
                calls_by_name.setdefault(e.name, []).append(e)
                for a in e.args:
                    walk_expr(a)
            elif isinstance(e, BinOp):
                walk_expr(e.left); walk_expr(e.right)
            elif isinstance(e, UnaryOp):
                walk_expr(e.operand)
            elif isinstance(e, IndexGet):
                walk_expr(e.arr); walk_expr(e.idx)

        def walk_stmt(s):
            if isinstance(s, (VarDecl, Assign)):
                walk_expr(s.expr)
            elif isinstance(s, IndexSet):
                walk_expr(s.arr); walk_expr(s.idx); walk_expr(s.expr)
            elif isinstance(s, Print):
                walk_expr(s.expr)
            elif isinstance(s, If):
                walk_expr(s.cond)
                for x in s.then_b: walk_stmt(x)
                for x in s.else_b: walk_stmt(x)
            elif isinstance(s, While):
                walk_expr(s.cond)
                for x in s.body: walk_stmt(x)
            elif isinstance(s, TryCatch):
                for x in s.try_body: walk_stmt(x)
                for x in s.catch_body: walk_stmt(x)
            elif isinstance(s, Throw):
                walk_expr(s.expr)
            elif isinstance(s, Return):
                if s.expr is not None: walk_expr(s.expr)
            elif isinstance(s, ExprStmt):
                walk_expr(s.expr)

        for s in stmts:
            walk_stmt(s)

    def _infer_param_type_from_calls(self, fname, idx, calls_by_name):
        """Segunda tentativa quando o CORPO da função não dá nenhuma pista
        de tipo (caso comum: 'fn assert_close(name, got, expected, eps)'
        só usa os parâmetros em operações neutras tipo subtração/comparação
        entre si — não tem nenhum literal ali que entregue o tipo). Em vez
        disso, olha pra quem CHAMA essa função: se algum call site passa
        nesse parâmetro um literal double, uma string, ou o retorno de uma
        função já conhecida como double/str, usa isso como evidência."""
        for c in calls_by_name.get(fname, []):
            if idx >= len(c.args):
                continue
            t = self._guess_type(c.args[idx])
            if t != "i64":
                return t
        return None

    def _infer_param_type(self, param_name, body):
        """Parâmetro sem anotação ('fn f(s) {...}'): tenta adivinhar 'str'
        olhando como ele é usado no corpo (passado pra uma função de string,
        ou comparado/concatenado com uma string literal). Sem nenhuma
        evidência, cai no padrão de sempre: i64."""
        found = {"str": False, "double": False}

        def walk_expr(e):
            if e is None or found["str"]:
                return
            if isinstance(e, Call):
                if (e.name in self._STR_BUILTIN_FIRST_ARG and e.args
                        and isinstance(e.args[0], Var) and e.args[0].name == param_name):
                    found["str"] = True
                for a in e.args:
                    walk_expr(a)
            elif isinstance(e, BinOp):
                l_is_p = isinstance(e.left, Var) and e.left.name == param_name
                r_is_p = isinstance(e.right, Var) and e.right.name == param_name
                if l_is_p and isinstance(e.right, Str): found["str"] = True
                if r_is_p and isinstance(e.left, Str): found["str"] = True
                if l_is_p and isinstance(e.right, Num) and e.right.is_float: found["double"] = True
                if r_is_p and isinstance(e.left, Num) and e.left.is_float: found["double"] = True
                walk_expr(e.left); walk_expr(e.right)
            elif isinstance(e, UnaryOp):
                walk_expr(e.operand)
            elif isinstance(e, IndexGet):
                walk_expr(e.arr); walk_expr(e.idx)
            elif isinstance(e, FieldGet):
                walk_expr(e.base)

        def walk_stmt(s):
            if found["str"]:
                return
            if isinstance(s, (VarDecl, Assign)):
                walk_expr(s.expr)
            elif isinstance(s, IndexSet):
                walk_expr(s.arr); walk_expr(s.idx); walk_expr(s.expr)
            elif isinstance(s, FieldSet):
                walk_expr(s.base); walk_expr(s.expr)
            elif isinstance(s, Print):
                walk_expr(s.expr)
            elif isinstance(s, If):
                walk_expr(s.cond)
                for x in s.then_b: walk_stmt(x)
                for x in s.else_b: walk_stmt(x)
            elif isinstance(s, While):
                walk_expr(s.cond)
                for x in s.body: walk_stmt(x)
            elif isinstance(s, TryCatch):
                for x in s.try_body: walk_stmt(x)
                for x in s.catch_body: walk_stmt(x)
            elif isinstance(s, Throw):
                walk_expr(s.expr)
            elif isinstance(s, Return):
                if s.expr is not None: walk_expr(s.expr)
            elif isinstance(s, ExprStmt):
                walk_expr(s.expr)
            elif isinstance(s, For):
                if s.init is not None: walk_stmt(s.init)
                if s.cond is not None: walk_expr(s.cond)
                if s.post is not None: walk_stmt(s.post)
                for x in s.body: walk_stmt(x)
            elif isinstance(s, StructDef):
                pass

        for s in body:
            walk_stmt(s)
            if found["str"]:
                break
        if found["str"]:
            return "str"
        if found["double"]:
            return "double"
        return "i64"

    EXTERN_TYPE_MAP = {"i64": "i64", "f64": "double", "void": "void"}

    def compile_program(self, stmts):
        structdefs = [s for s in stmts if isinstance(s, StructDef)]
        funcdefs = [s for s in stmts if isinstance(s, FuncDef)]
        externs = [s for s in stmts if isinstance(s, ExternDecl)]
        imports = [s for s in stmts if isinstance(s, ImportDecl)]
        if not any(f.name == "main" for f in funcdefs):
            raise CompileError("Programa precisa de uma função main()")

        for sd in structdefs:
            if sd.name in self.structs:
                raise CompileError(f"Struct '{sd.name}' já foi declarada")
            self.structs[sd.name] = sd.fields
        for sd in structdefs:
            for _, field_t in sd.fields:
                self._validate_type_spec(field_t)

        self.imports = [i.name for i in imports]

        extern_ir = []
        for e in externs:
            if e.name in self.functions:
                raise CompileError(f"'{e.name}' já foi declarada (extern duplicado ou conflito com fn)")
            param_ts = [self.EXTERN_TYPE_MAP[t] for t in e.param_types]
            ret_t = self.EXTERN_TYPE_MAP[e.ret_type]
            for t in param_ts + [ret_t]:
                self._validate_type_spec(t)
            self.functions[e.name] = {"params": param_ts, "ret": ret_t, "extern": True}
            llvm_ret = "void" if ret_t == "void" else ret_t
            extern_ir.append(f"declare {llvm_ret} @{e.name}({', '.join(param_ts)})")

        # coleta todas as chamadas de função do programa inteiro ANTES de
        # resolver os parâmetros sem anotação — precisamos disso pra
        # inferência por call-site (ver _infer_param_type_from_calls):
        # às vezes o CORPO da função não dá nenhuma pista de tipo (ex.:
        # "fn assert_close(name, got, expected, eps) { ... got - expected ... }"),
        # mas quem CHAMA ela passa um literal double/string óbvio.
        calls_by_name = {}
        for f in funcdefs:
            self._collect_calls_into(f.body, calls_by_name)

        for f in funcdefs:
            if f.name in self.functions:
                raise CompileError(f"'{f.name}' já foi declarada (conflito com extern)")
            # resolve parâmetros sem anotação (None) por inferência leve de
            # uso — sem isso, toda função que recebe string sem anotar
            # explicitamente ("fn f(s) { return upper(s) }") quebrava com
            # erro de tipo, mesmo sendo óbvio pelo uso que 's' é string.
            # Se o corpo não der pista nenhuma (fica no default i64), tenta
            # de novo olhando como a função é CHAMADA em outros lugares.
            new_types = []
            for idx, (p, t) in enumerate(zip(f.params, f.param_types)):
                if t is not None:
                    new_types.append(t)
                    continue
                guessed = self._infer_param_type(p, f.body)
                if guessed == "i64":
                    alt = self._infer_param_type_from_calls(f.name, idx, calls_by_name)
                    if alt is not None:
                        guessed = alt
                new_types.append(guessed)
            f.param_types = new_types
            # "params" agora guarda os TIPOS reais de cada parâmetro (unificado
            # com extern, que já funcionava assim). "ret" usa a anotação
            # explícita ('-> tipo') se houver; senão cai na heurística antiga
            # (varre os returns do corpo tentando adivinhar).
            ret_kind = f.ret_type if f.ret_type is not None else self._scan_return_type(f.body)
            self._validate_type_spec(ret_kind)
            for t in f.param_types:
                self._validate_type_spec(t)
            self.functions[f.name] = {
                "params": f.param_types, "ret": ret_kind, "extern": False,
            }

        body_ir = []
        for f in funcdefs:
            body_ir.append(self.gen_function(f))

        header = ""
        if self.target_triple:
            header += f'target triple = "{self.target_triple}"\n'
        header += BUILTIN_DECLARES + FMT_CONSTANTS + EXC_GLOBALS + "\n" + "\n".join(extern_ir) + "\n"
        return header + "\n".join(self.strings) + "\n" + "\n".join(body_ir)

    def _collect_locals(self, body, out):
        """Anda pelo corpo da função (entrando em if/while/try) coletando o
        tipo de cada 'var' e cada variável de 'catch'. Usado pra hoistar
        (mover pro início da função) todos os alloca — o LLVM exige que um
        alloca sempre domine qualquer lugar onde é usado; um alloca dentro
        de um bloco condicional (ex.: dentro de um 'catch') NÃO domina o
        uso em outro ramo irmão (outro 'catch' ou outro 'if'), e o clang
        rejeita isso como "Instruction does not dominate all uses"."""
        for s in body:
            if isinstance(s, VarDecl):
                t = s.decl_type if s.decl_type is not None else self._guess_type(s.expr, out)
                if s.name in out:
                    if not self._type_compatible(out[s.name], t):
                        raise CompileError(
                            f"'{s.name}' já foi declarada com outro tipo nesta função — "
                            f"não dá pra redeclarar com um tipo incompatível ({self.type_name(out[s.name])} vs {self.type_name(t)})"
                        )
                else:
                    out[s.name] = t
            elif isinstance(s, If):
                self._collect_locals(s.then_b, out)
                self._collect_locals(s.else_b, out)
            elif isinstance(s, While):
                self._collect_locals(s.body, out)
            elif isinstance(s, For):
                if s.init is not None:
                    self._collect_locals([s.init], out)
                self._collect_locals(s.body, out)
                if s.post is not None:
                    self._collect_locals([s.post], out)
            elif isinstance(s, TryCatch):
                self._collect_locals(s.try_body, out)
                if s.catch_var in out and out[s.catch_var] != "str":
                    raise CompileError(
                        f"'{s.catch_var}' já existe nesta função com outro tipo — "
                        "a variável de 'catch' é sempre str, escolhe outro nome"
                    )
                out.setdefault(s.catch_var, "str")
                self._collect_locals(s.catch_body, out)
            elif isinstance(s, StructDef):
                continue

    def gen_function(self, node):
        env = {}
        lines = []
        is_main = node.name == "main"
        ret_kind = self.functions[node.name]["ret"]
        llvm_ret = "i32" if is_main else self.llvm_type(ret_kind)

        param_types = self.functions[node.name]["params"]
        params_sig = ", ".join(
            f"{self.llvm_type(t)} %arg_{i}" for i, t in enumerate(param_types)
        )
        lines.append(f"define {llvm_ret} @{node.name}({params_sig}) {{")
        lines.append("entry:")

        # label pra onde uma exceção "escapada" (sem catch ativo nesta função)
        # deve pular; em main isso é o handler de exceção não tratada, nas
        # outras funções é um retorno antecipado que devolve o controle pro
        # chamador (que por sua vez verifica a flag global logo após a call).
        func_uid = self.new_id()
        self.func_exc_exit = f"func_exc_exit_{func_uid}"
        self.catch_stack = []
        self.loop_stack = []

        if is_main:
            if self.use_gc:
                lines.append("  call void @GC_init()")
            uid = self.new_id()
            lines.append(f"  %st_tv_{uid} = alloca [16 x i8], align 8")
            lines.append(f"  %st_tp_{uid} = getelementptr [16 x i8], [16 x i8]* %st_tv_{uid}, i32 0, i32 0")
            lines.append(f"  call i32 @gettimeofday(i8* %st_tp_{uid}, i8* null)")
            lines.append(f"  %st_up_{uid} = getelementptr i8, i8* %st_tp_{uid}, i32 8")
            lines.append(f"  %st_up6_{uid} = bitcast i8* %st_up_{uid} to i64*")
            lines.append(f"  %st_uv_{uid} = load i64, i64* %st_up6_{uid}")
            lines.append(f"  %seed_{uid} = trunc i64 %st_uv_{uid} to i32")
            lines.append(f"  call void @srand(i32 %seed_{uid})")

        for i, (p, t) in enumerate(zip(node.params, param_types)):
            env[p] = t
            lt = self.llvm_type(t)
            lines.append(f"  %{p} = alloca {lt}, align 8")
            lines.append(f"  store {lt} %arg_{i}, {lt}* %{p}, align 8")

        # hoist: todo alloca de 'var'/'catch' do corpo inteiro nasce aqui,
        # logo no início da função — garante que sempre domine qualquer uso,
        # não importa em que ramo condicional a declaração de fato ocorra.
        locals_types = dict(env)
        self._collect_locals(node.body, locals_types)
        for name, t in locals_types.items():
            if name in env:
                continue  # já é parâmetro, não redeclara
            lt = self.llvm_type(t)
            lines.append(f"  %{name} = alloca {lt}, align 8")
            env[name] = t

        for s in node.body:
            self.gen_stmt(s, env, lines, llvm_ret)

        # terminador padrão caso o corpo não termine com return explícito
        if llvm_ret == "void":
            lines.append("  ret void")
        elif llvm_ret == "i32":
            lines.append("  ret i32 0")
        elif llvm_ret == "double":
            lines.append("  ret double 0.0")
        elif llvm_ret == "i8*":
            lines.append("  ret i8* null")
        else:
            lines.append("  ret i64 0")

        # bloco de saída por exceção não capturada nesta função. Só fica
        # "vivo" de verdade se algum throw/call dentro da função apontar
        # pra cá (ver Throw e as checagens pós-call em gen_call); se não
        # houver nenhum try/throw/call que possa lançar, esse bloco fica
        # inalcançável e o clang simplesmente descarta ele no -O2.
        lines.append(f"{self.func_exc_exit}:")
        if is_main:
            uid = self.new_id()
            lines.append(f"  %excmsg_top_{uid} = load i8*, i8** @__ares_exc_msg")
            lines.append(f"  %fmtp_{uid} = getelementptr [25 x i8], [25 x i8]* @fmt_uncaught, i32 0, i32 0")
            lines.append(f"  call i32 (i8*, ...) @printf(i8* %fmtp_{uid}, i8* %excmsg_top_{uid})")
            lines.append("  call void @exit(i32 1)")
            lines.append("  unreachable")
        elif llvm_ret == "void":
            lines.append("  ret void")
        elif llvm_ret == "i32":
            lines.append("  ret i32 0")
        elif llvm_ret == "double":
            lines.append("  ret double 0.0")
        elif llvm_ret == "i8*":
            lines.append("  ret i8* null")
        else:
            lines.append("  ret i64 0")
        lines.append("}")
        return "\n".join(lines)

    def cast(self, lines, value_type, value_reg, target_type):
        if value_type == target_type:
            return value_reg
        uid = self.new_id()
        if value_type == "i64" and target_type == "double":
            lines.append(f"  %cast_{uid} = sitofp i64 {value_reg} to double")
        elif value_type == "double" and target_type == "i64":
            lines.append(f"  %cast_{uid} = fptosi double {value_reg} to i64")
        elif value_type == "i64" and target_type == "i32":
            lines.append(f"  %cast_{uid} = trunc i64 {value_reg} to i32")
        elif value_type == "double" and target_type == "i32":
            lines.append(f"  %cast_{uid} = fptosi double {value_reg} to i32")
        elif value_type == "i32" and target_type == "i64":
            lines.append(f"  %cast_{uid} = sext i32 {value_reg} to i64")
        elif value_type == "i1" and target_type == "i64":
            lines.append(f"  %cast_{uid} = zext i1 {value_reg} to i64")
        elif value_type == "i1" and target_type == "double":
            lines.append(f"  %cast_{uid} = uitofp i1 {value_reg} to double")
        elif value_type == "i64" and target_type == "i1":
            lines.append(f"  %cast_{uid} = icmp ne i64 {value_reg}, 0")
        elif value_type == "double" and target_type == "i1":
            lines.append(f"  %cast_{uid} = fcmp une double {value_reg}, 0.0")
        else:
            return value_reg  # tipos iguais ou combinação não esperada
        return f"%cast_{uid}"

    def to_str(self, lines, t, v):
        # usado por "throw": garante que o valor lançado vire uma string,
        # convertendo números automaticamente (throw 42 -> "42").
        if t == "str":
            return v
        uid = self.new_id()
        alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
        lines.append(f"  %tsbuf_{uid} = call i8* {alloc_fn}(i64 64)")
        if t == "double":
            lines.append(f"  %tsfmt_{uid} = getelementptr [3 x i8], [3 x i8]* @fmt_float_raw, i32 0, i32 0")
            lines.append(f"  call i32 (i8*, i8*, ...) @sprintf(i8* %tsbuf_{uid}, i8* %tsfmt_{uid}, double {v})")
        else:
            v = self.cast(lines, t, v, "i64")
            lines.append(f"  %tsfmt_{uid} = getelementptr [4 x i8], [4 x i8]* @fmt_int_raw, i32 0, i32 0")
            lines.append(f"  call i32 (i8*, i8*, ...) @sprintf(i8* %tsbuf_{uid}, i8* %tsfmt_{uid}, i64 {v})")
        return f"%tsbuf_{uid}"

    def gen_stmt(self, node, env, lines, func_ret_type):
        if isinstance(node, VarDecl):
            t, v = self.gen_expr(node.expr, env, lines)
            # o alloca já foi feito no início da função (hoist, ver
            # gen_function/_collect_locals) — aqui só converte pro tipo já
            # fixado e guarda o valor. Isso garante que o registrador sempre
            # "domine" qualquer uso, mesmo quando a declaração está dentro
            # de um if/while/try condicional.
            target_t = node.decl_type if node.decl_type is not None else env.get(node.name, t)
            if not self._type_compatible(target_t, t):
                raise CompileError(
                    f"'{node.name}' já foi declarada como {self.type_name(target_t)} nesta função — "
                    f"não dá pra redeclarar com um tipo incompatível ({self.type_name(target_t)} vs {self.type_name(t)})"
                )
            if not is_opaque_type(target_t) and target_t != "str":
                v = self.cast(lines, t, v, target_t)
            lt = self.llvm_type(target_t)
            env[node.name] = target_t
            lines.append(f"  store {lt} {v}, {lt}* %{node.name}, align 8")

        elif isinstance(node, Assign):
            if node.name not in env:
                raise CompileError(f"Variável '{node.name}' não declarada — use 'var {node.name} = ...' primeiro")
            target_t = env[node.name]
            t, v = self.gen_expr(node.expr, env, lines)
            if not self._type_compatible(target_t, t):
                raise CompileError(
                    f"Tipo incompatível ao atribuir a '{node.name}' (era {self.type_name(target_t)}, veio {self.type_name(t)})"
                )
            if not is_opaque_type(target_t) and target_t != "str":
                v = self.cast(lines, t, v, target_t)
            lt = self.llvm_type(target_t)
            lines.append(f"  store {lt} {v}, {lt}* %{node.name}, align 8")

        elif isinstance(node, IndexSet):
            at, av = self.gen_expr(node.arr, env, lines)
            _, iv = self.gen_expr(node.idx, env, lines)
            t, v = self.gen_expr(node.expr, env, lines)
            uid = self.new_id()
            if at == "i64":
                v = self.cast(lines, t, v, "i64")
                lines.append(f"  %ap_{uid} = inttoptr i64 {av} to i64*")
                lines.append(f"  %ep_{uid} = getelementptr i64, i64* %ap_{uid}, i64 {iv}")
                lines.append(f"  store i64 {v}, i64* %ep_{uid}, align 8")
            elif is_array_type(at) and at[1] == "double" and at[2] == 1:
                v = self.cast(lines, t, v, "double")
                lines.append(f"  %ad_{uid} = getelementptr i8, i8* {av}, i64 8")
                lines.append(f"  %adp_{uid} = bitcast i8* %ad_{uid} to double*")
                lines.append(f"  %ep_{uid} = getelementptr double, double* %adp_{uid}, i64 {iv}")
                lines.append(f"  store double {v}, double* %ep_{uid}, align 8")
            elif is_array_type(at) and at[1] == "double" and at[2] == 2:
                if not (is_array_type(t) and t[1] == "double" and t[2] == 1):
                    raise CompileError("Atribuição em linha de matriz espera um valor do tipo double[]")
                lines.append(f"  %rowbyte_{uid} = mul nsw i64 {iv}, 8")
                lines.append(f"  %rowoff_{uid} = add nsw i64 16, %rowbyte_{uid}")
                lines.append(f"  %rowp_{uid} = getelementptr i8, i8* {av}, i64 %rowoff_{uid}")
                lines.append(f"  %rowpp_{uid} = bitcast i8* %rowp_{uid} to i8**")
                lines.append(f"  store i8* {v}, i8** %rowpp_{uid}, align 8")
            else:
                raise CompileError(f"Indexação (escrita com []) não é suportada para o tipo '{self.type_name(at)}'")

        elif isinstance(node, Print):
            if isinstance(node.expr, Str):
                uid = self.new_id()
                text = node.expr.value
                raw_len = len(text.encode("utf-8"))
                escaped = llvm_escape_string(text)
                byte_len = raw_len + 2
                self.strings.append(
                    f'@.str.{uid} = private unnamed_addr constant [{byte_len} x i8] c"{escaped}\\0A\\00"'
                )
                lines.append(f"  %pf_{uid} = getelementptr [{byte_len} x i8], [{byte_len} x i8]* @.str.{uid}, i32 0, i32 0")
                lines.append(f"  call i32 (i8*, ...) @printf(i8* %pf_{uid})")
            else:
                t, v = self.gen_expr(node.expr, env, lines)
                uid = self.new_id()
                if t == "double":
                    lines.append(f"  %pf_{uid} = getelementptr [4 x i8], [4 x i8]* @fmt_float, i32 0, i32 0")
                    lines.append(f"  call i32 (i8*, ...) @printf(i8* %pf_{uid}, {t} {v})")
                elif t == "str":
                    lines.append(f"  %pf_{uid} = getelementptr [4 x i8], [4 x i8]* @fmt_str, i32 0, i32 0")
                    lines.append(f"  call i32 (i8*, ...) @printf(i8* %pf_{uid}, i8* {v})")
                elif is_opaque_type(t):
                    raise CompileError(
                        f"print ainda não suporta diretamente valores de tipo '{self.type_name(t)}' — "
                        "use um helper específico da biblioteca ou extraia campos/elementos"
                    )
                else:
                    # normaliza pra i64 antes de imprimir — "t" pode vir como
                    # i1 (resultado cru de uma comparação, ex. print(a > b))
                    # ou i32; sem isso o printf recebia um valor cujo tipo
                    # real não batia com o "%ld" do formato (bits de cima
                    # indefinidos = número aleatório impresso).
                    v = self.cast(lines, t, v, "i64")
                    lines.append(f"  %pf_{uid} = getelementptr [5 x i8], [5 x i8]* @fmt_int, i32 0, i32 0")
                    lines.append(f"  call i32 (i8*, ...) @printf(i8* %pf_{uid}, i64 {v})")

        elif isinstance(node, If):
            uid = self.new_id()
            cond_t, cond_v = self.gen_expr(node.cond, env, lines)
            cond_v = self._to_bool(lines, cond_t, cond_v)
            lines.append(f"  br i1 {cond_v}, label %it_{uid}, label %ie_{uid}")
            lines.append(f"it_{uid}:")
            for s in node.then_b: self.gen_stmt(s, env, lines, func_ret_type)
            lines.append(f"  br label %if_end_{uid}")
            lines.append(f"ie_{uid}:")
            for s in node.else_b: self.gen_stmt(s, env, lines, func_ret_type)
            lines.append(f"  br label %if_end_{uid}")
            lines.append(f"if_end_{uid}:")

        elif isinstance(node, While):
            uid = self.new_id()
            exit_label = f"be_{uid}"
            cond_label = f"c_{uid}"
            self.loop_stack.append((cond_label, exit_label))
            lines.append(f"  br label %c_{uid}")
            lines.append(f"c_{uid}:")
            cond_t, cond_v = self.gen_expr(node.cond, env, lines)
            cond_v = self._to_bool(lines, cond_t, cond_v)
            lines.append(f"  br i1 {cond_v}, label %bt_{uid}, label %{exit_label}")
            lines.append(f"bt_{uid}:")
            for s in node.body: self.gen_stmt(s, env, lines, func_ret_type)
            lines.append(f"  br label %c_{uid}")
            self.loop_stack.pop()
            lines.append(f"{exit_label}:")

        elif isinstance(node, For):
            uid = self.new_id()
            cond_label = f"for_cond_{uid}"
            body_label = f"for_body_{uid}"
            post_label = f"for_post_{uid}"
            end_label = f"for_end_{uid}"
            self.loop_stack.append((post_label, end_label))
            if node.init is not None:
                self.gen_stmt(node.init, env, lines, func_ret_type)
            lines.append(f"  br label %{cond_label}")
            lines.append(f"{cond_label}:")
            if node.cond is not None:
                cond_t, cond_v = self.gen_expr(node.cond, env, lines)
                cond_v = self._to_bool(lines, cond_t, cond_v)
            else:
                cond_v = "1"
            lines.append(f"  br i1 {cond_v}, label %{body_label}, label %{end_label}")
            lines.append(f"{body_label}:")
            for s in node.body:
                self.gen_stmt(s, env, lines, func_ret_type)
            lines.append(f"  br label %{post_label}")
            lines.append(f"{post_label}:")
            if node.post is not None:
                self.gen_stmt(node.post, env, lines, func_ret_type)
            lines.append(f"  br label %{cond_label}")
            self.loop_stack.pop()
            lines.append(f"{end_label}:")

        elif isinstance(node, TryCatch):
            uid = self.new_id()
            catch_label = f"catch_{uid}"
            end_label = f"try_end_{uid}"
            self.catch_stack.append(catch_label)
            for s in node.try_body:
                self.gen_stmt(s, env, lines, func_ret_type)
            self.catch_stack.pop()
            lines.append(f"  br label %{end_label}")
            lines.append(f"{catch_label}:")
            # zera a flag (a exceção foi capturada aqui) e expõe a mensagem
            # na variável declarada em "catch <nome>" (sempre tipo str).
            lines.append("  store i32 0, i32* @__ares_exc_flag")
            # alloca já foi feita no início da função (hoist)
            lines.append(f"  %excmsg_{uid} = load i8*, i8** @__ares_exc_msg")
            lines.append(f"  store i8* %excmsg_{uid}, i8** %{node.catch_var}, align 8")
            env[node.catch_var] = "str"
            for s in node.catch_body:
                self.gen_stmt(s, env, lines, func_ret_type)
            lines.append(f"  br label %{end_label}")
            lines.append(f"{end_label}:")

        elif isinstance(node, FieldSet):
            base_t, base_v = self.gen_expr(node.base, env, lines)
            if not is_struct_type(base_t):
                raise CompileError(f"Campo '{node.field}' só pode ser atribuído em struct")
            struct_name = base_t[1]
            field_idx = self._struct_field_index(struct_name, node.field)
            field_t = self._struct_field_type(struct_name, node.field)
            t, v = self.gen_expr(node.expr, env, lines)
            if not self._type_compatible(field_t, t):
                raise CompileError(
                    f"Campo '{node.field}' da struct '{struct_name}' espera '{self.type_name(field_t)}', recebeu '{self.type_name(t)}'"
                )
            v = self.cast(lines, t, v, field_t)
            slot_uid = self.new_id()
            field_off = field_idx * 8
            lines.append(f"  %fldp_{slot_uid} = getelementptr i8, i8* {base_v}, i64 {field_off}")
            if is_opaque_type(field_t) or field_t == "str":
                lines.append(f"  %fldpp_{slot_uid} = bitcast i8* %fldp_{slot_uid} to i8**")
                lines.append(f"  store i8* {v}, i8** %fldpp_{slot_uid}, align 8")
            else:
                llvm_ft = self.llvm_type(field_t)
                lines.append(f"  %fldtp_{slot_uid} = bitcast i8* %fldp_{slot_uid} to {llvm_ft}*")
                lines.append(f"  store {llvm_ft} {v}, {llvm_ft}* %fldtp_{slot_uid}, align 8")

        elif isinstance(node, Break):
            if not self.loop_stack:
                raise CompileError("Instrução 'break' fora de um loop")
            _, target = self.loop_stack[-1]
            lines.append(f"  br label %{target}")
            uid = self.new_id()
            lines.append(f"unreachable_brk_{uid}:")

        elif isinstance(node, Continue):
            if not self.loop_stack:
                raise CompileError("Instrução 'continue' fora de um loop")
            target, _ = self.loop_stack[-1]
            lines.append(f"  br label %{target}")
            uid = self.new_id()
            lines.append(f"unreachable_cont_{uid}:")

        elif isinstance(node, Throw):
            t, v = self.gen_expr(node.expr, env, lines)
            v = self.to_str(lines, t, v)
            lines.append(f"  store i8* {v}, i8** @__ares_exc_msg")
            lines.append("  store i32 1, i32* @__ares_exc_flag")
            target = self.catch_stack[-1] if self.catch_stack else self.func_exc_exit
            lines.append(f"  br label %{target}")
            uid = self.new_id()
            lines.append(f"unreachable_thr_{uid}:")  # bloco morto p/ manter IR válido após br

        elif isinstance(node, Return):
            if node.expr is None:
                if func_ret_type == "void":
                    lines.append("  ret void")
                elif func_ret_type == "i8*":
                    lines.append("  ret i8* null")
                else:
                    lines.append(f"  ret {func_ret_type} 0")
            else:
                t, v = self.gen_expr(node.expr, env, lines)
                if func_ret_type == "i8*":
                    if not (t == "str" or is_opaque_type(t)):
                        raise CompileError(
                            "Função declarada retornando tipo composto/str, "
                            f"mas o valor retornado é do tipo '{self.type_name(t)}'"
                        )
                elif t == "str" or is_opaque_type(t):
                    raise CompileError(
                        "Não é possível retornar um tipo composto/string de uma função "
                        "que não declara esse retorno explicitamente"
                    )
                else:
                    v = self.cast(lines, t, v, func_ret_type)
                lines.append(f"  ret {func_ret_type} {v}")
            uid = self.new_id()
            lines.append(f"unreachable_{uid}:")  # bloco morto p/ manter blocos válidos após ret

        elif isinstance(node, ExprStmt):
            self.gen_expr(node.expr, env, lines)
        elif isinstance(node, StructDef):
            return

        else:
            raise CompileError(f"Statement não suportado: {node}")

    def gen_expr(self, node, env, lines):
        uid = self.new_id()

        if isinstance(node, Num):
            return ("double", fmt_double_literal(node.value)) if node.is_float else ("i64", str(int(node.value)))

        if isinstance(node, Str):
            text = node.value
            raw_len = len(text.encode("utf-8"))
            escaped = llvm_escape_string(text)
            byte_len = raw_len + 1
            self.strings.append(
                f'@.str.{uid} = private unnamed_addr constant [{byte_len} x i8] c"{escaped}\\00"'
            )
            lines.append(f"  %sp_{uid} = getelementptr [{byte_len} x i8], [{byte_len} x i8]* @.str.{uid}, i32 0, i32 0")
            return "str", f"%sp_{uid}"

        if isinstance(node, Bool):
            return ("i64", "1" if node.value else "0")

        if isinstance(node, Var):
            if node.name in env:
                t = env[node.name]
                lt = self.llvm_type(t)
                lines.append(f"  %reg_{uid} = load {lt}, {lt}* %{node.name}, align 8")
                return t, f"%reg_{uid}"
            if node.name in self.functions:
                # referência a uma função top-level usada como valor (callback).
                # Convenção: só funções que retornam i64 podem virar ponteiro de
                # função dessa forma (é o formato que a chamada indireta espera).
                sig = self.functions[node.name]
                if sig["ret"] != "i64":
                    raise CompileError(
                        f"'{node.name}' não pode ser usada como callback: "
                        f"só funções que retornam número inteiro são suportadas como valor"
                    )
                params_ty = ", ".join(["i64"] * len(sig["params"]))
                fnty = f"i64 ({params_ty})"
                lines.append(f"  %fnp_{uid} = ptrtoint {fnty}* @{node.name} to i64")
                return "i64", f"%fnp_{uid}"
            raise CompileError(f"Variável '{node.name}' usada antes de declarar")

        if isinstance(node, FieldGet):
            base_t, base_v = self.gen_expr(node.base, env, lines)
            if not is_struct_type(base_t):
                raise CompileError(f"Acesso a campo '{node.field}' exige um struct, veio '{self.type_name(base_t)}'")
            struct_name = base_t[1]
            field_idx = self._struct_field_index(struct_name, node.field)
            field_t = self._struct_field_type(struct_name, node.field)
            field_off = field_idx * 8
            slot_uid = self.new_id()
            lines.append(f"  %fldp_{slot_uid} = getelementptr i8, i8* {base_v}, i64 {field_off}")
            if is_opaque_type(field_t) or field_t == "str":
                lines.append(f"  %fldpp_{slot_uid} = bitcast i8* %fldp_{slot_uid} to i8**")
                lines.append(f"  %fldv_{slot_uid} = load i8*, i8** %fldpp_{slot_uid}, align 8")
                return field_t, f"%fldv_{slot_uid}"
            llvm_ft = self.llvm_type(field_t)
            lines.append(f"  %fldpp_{slot_uid} = bitcast i8* %fldp_{slot_uid} to {llvm_ft}*")
            lines.append(f"  %fldv_{slot_uid} = load {llvm_ft}, {llvm_ft}* %fldpp_{slot_uid}, align 8")
            return field_t, f"%fldv_{slot_uid}"

        if isinstance(node, UnaryOp):
            t, v = self.gen_expr(node.operand, env, lines)
            if t == "double":
                lines.append(f"  %neg_{uid} = fsub double 0.0, {v}")
            else:
                lines.append(f"  %neg_{uid} = sub nsw i64 0, {v}")
            return t, f"%neg_{uid}"

        if isinstance(node, BinOp):
            t1, v1 = self.gen_expr(node.left, env, lines)
            t2, v2 = self.gen_expr(node.right, env, lines)

            if t1 == "str" or t2 == "str":
                if t1 != "str" or t2 != "str":
                    raise CompileError(
                        "Operações com string exigem que os dois operandos sejam strings "
                        "(ainda não existe conversão automática número -> string; use str(x))"
                    )
                if node.op in ("==", "!="):
                    lines.append(f"  %scmp_{uid} = call i32 @strcmp(i8* {v1}, i8* {v2})")
                    pred = "eq" if node.op == "==" else "ne"
                    lines.append(f"  %cmp_{uid} = icmp {pred} i32 %scmp_{uid}, 0")
                    return "i1", f"%cmp_{uid}"
                if node.op != "+":
                    raise CompileError(f"Operador '{node.op}' não é suportado para strings (só '+', '==' e '!=')")
                lines.append(f"  %l1_{uid} = call i64 @strlen(i8* {v1})")
                lines.append(f"  %l2_{uid} = call i64 @strlen(i8* {v2})")
                lines.append(f"  %lt_{uid} = add nsw i64 %l1_{uid}, %l2_{uid}")
                lines.append(f"  %la_{uid} = add nsw i64 %lt_{uid}, 1")
                alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
                lines.append(f"  %buf_{uid} = call i8* {alloc_fn}(i64 %la_{uid})")
                lines.append(f"  call i8* @strcpy(i8* %buf_{uid}, i8* {v1})")
                lines.append(f"  call i8* @strcat(i8* %buf_{uid}, i8* {v2})")
                return "str", f"%buf_{uid}"

            is_float = t1 == "double" or t2 == "double"
            if is_float:
                v1 = self.cast(lines, t1, v1, "double")
                v2 = self.cast(lines, t2, v2, "double")

            if node.op in ("==", "!=", "<", ">", "<=", ">="):
                if is_float:
                    om = {"<": "olt", ">": "ogt", "==": "oeq", "!=": "one", "<=": "ole", ">=": "oge"}[node.op]
                    lines.append(f"  %cmp_{uid} = fcmp {om} double {v1}, {v2}")
                else:
                    om = {"<": "slt", ">": "sgt", "==": "eq", "!=": "ne", "<=": "sle", ">=": "sge"}[node.op]
                    lines.append(f"  %cmp_{uid} = icmp {om} i64 {v1}, {v2}")
                return "i1", f"%cmp_{uid}"

            if node.op in ("&", "|", "^"):
                if is_float:
                    raise CompileError(f"Operador '{node.op}' (bitwise) não é suportado com float — use inteiros")
                v1i = self.cast(lines, t1, v1, "i64")
                v2i = self.cast(lines, t2, v2, "i64")
                instr = {"&": "and", "|": "or", "^": "xor"}[node.op]
                lines.append(f"  %tmp_{uid} = {instr} i64 {v1i}, {v2i}")
                return "i64", f"%tmp_{uid}"

            if is_float:
                instr = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv"}.get(node.op)
                if instr is None:
                    raise CompileError("'%' (módulo) não é suportado com float")
                if node.op == "/":
                    err_uid = self.new_id()
                    err_text = "divisao por zero"
                    err_escaped = llvm_escape_string(err_text)
                    err_byte_len = len(err_text.encode("utf-8")) + 1
                    self.strings.append(
                        f'@.str.{err_uid} = private unnamed_addr constant [{err_byte_len} x i8] c"{err_escaped}\\00"'
                    )
                    lines.append(f"  %cond_div_zero_{uid} = fcmp oeq double {v2}, 0.0")
                    lines.append(f"  br i1 %cond_div_zero_{uid}, label %div_zero_err_{uid}, label %div_ok_{uid}")
                    lines.append(f"div_zero_err_{uid}:")
                    lines.append(f"  %err_sp_{uid} = getelementptr [{err_byte_len} x i8], [{err_byte_len} x i8]* @.str.{err_uid}, i32 0, i32 0")
                    lines.append(f"  store i8* %err_sp_{uid}, i8** @__ares_exc_msg")
                    lines.append("  store i32 1, i32* @__ares_exc_flag")
                    target = self.catch_stack[-1] if self.catch_stack else self.func_exc_exit
                    lines.append(f"  br label %{target}")
                    lines.append(f"div_ok_{uid}:")
                    lines.append(f"  %tmp_{uid} = fdiv double {v1}, {v2}")
                else:
                    lines.append(f"  %tmp_{uid} = {instr} double {v1}, {v2}")
                return "double", f"%tmp_{uid}"
            else:
                # normaliza operandos "estranhos" (ex.: i1 vindo direto de uma
                # comparação, tipo "1 + (a > b)") pra i64 antes da aritmética —
                # sem isso, a instrução declarava i64 mas o registrador real
                # podia ser i1, o que o LLVM rejeita (tipo incompatível).
                v1i = self.cast(lines, t1, v1, "i64")
                v2i = self.cast(lines, t2, v2, "i64")
                instr = {"+": "add nsw", "-": "sub nsw", "*": "mul nsw", "/": "sdiv", "%": "srem"}[node.op]
                if node.op in ("/", "%"):
                    err_uid = self.new_id()
                    err_text = "divisao por zero"
                    err_escaped = llvm_escape_string(err_text)
                    err_byte_len = len(err_text.encode("utf-8")) + 1
                    self.strings.append(
                        f'@.str.{err_uid} = private unnamed_addr constant [{err_byte_len} x i8] c"{err_escaped}\\00"'
                    )
                    lines.append(f"  %cond_div_zero_{uid} = icmp eq i64 {v2i}, 0")
                    lines.append(f"  br i1 %cond_div_zero_{uid}, label %div_zero_err_{uid}, label %div_ok_{uid}")
                    lines.append(f"div_zero_err_{uid}:")
                    lines.append(f"  %err_sp_{uid} = getelementptr [{err_byte_len} x i8], [{err_byte_len} x i8]* @.str.{err_uid}, i32 0, i32 0")
                    lines.append(f"  store i8* %err_sp_{uid}, i8** @__ares_exc_msg")
                    lines.append("  store i32 1, i32* @__ares_exc_flag")
                    target = self.catch_stack[-1] if self.catch_stack else self.func_exc_exit
                    lines.append(f"  br label %{target}")
                    lines.append(f"div_ok_{uid}:")
                    lines.append(f"  %tmp_{uid} = {instr} i64 {v1i}, {v2i}")
                else:
                    lines.append(f"  %tmp_{uid} = {instr} i64 {v1i}, {v2i}")
                return "i64", f"%tmp_{uid}"

        if isinstance(node, IndexGet):
            at, av = self.gen_expr(node.arr, env, lines)
            _, iv = self.gen_expr(node.idx, env, lines)
            if at == "i64":
                lines.append(f"  %ap_{uid} = inttoptr i64 {av} to i64*")
                lines.append(f"  %ep_{uid} = getelementptr i64, i64* %ap_{uid}, i64 {iv}")
                lines.append(f"  %ev_{uid} = load i64, i64* %ep_{uid}, align 8")
                return "i64", f"%ev_{uid}"
            if is_array_type(at):
                if at[1] == "double" and at[2] == 1:
                    lines.append(f"  %ad_{uid} = getelementptr i8, i8* {av}, i64 8")
                    lines.append(f"  %adp_{uid} = bitcast i8* %ad_{uid} to double*")
                    lines.append(f"  %ep_{uid} = getelementptr double, double* %adp_{uid}, i64 {iv}")
                    lines.append(f"  %ev_{uid} = load double, double* %ep_{uid}, align 8")
                    return "double", f"%ev_{uid}"
                if at[1] == "double" and at[2] == 2:
                    row_off = self.new_id()
                    lines.append(f"  %rowbyte_{row_off} = mul nsw i64 {iv}, 8")
                    lines.append(f"  %rowoff_{row_off} = add nsw i64 16, %rowbyte_{row_off}")
                    lines.append(f"  %rowp_{row_off} = getelementptr i8, i8* {av}, i64 %rowoff_{row_off}")
                    lines.append(f"  %rowpp_{row_off} = bitcast i8* %rowp_{row_off} to i8**")
                    lines.append(f"  %rowv_{row_off} = load i8*, i8** %rowpp_{row_off}, align 8")
                    return ("array", "double", 1), f"%rowv_{row_off}"
            raise CompileError(f"Indexação com [] não é suportada para o tipo '{self.type_name(at)}'")

        if isinstance(node, Call):
            return self.gen_call(node, env, lines, uid)

        if isinstance(node, StructLiteral):
            if node.name not in self.structs:
                raise CompileError(f"Struct '{node.name}' não foi declarada")
            fields = self.structs[node.name]
            field_map = {k: v for k, v in node.fields}
            missing = [name for name, _ in fields if name not in field_map]
            extra = [name for name in field_map if name not in dict(fields)]
            if missing:
                raise CompileError(
                    f"Literal da struct '{node.name}' está incompleto, faltam campos: {', '.join(missing)}"
                )
            if extra:
                raise CompileError(
                    f"Literal da struct '{node.name}' tem campos desconhecidos: {', '.join(extra)}"
                )
            alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
            size_bytes = len(fields) * 8
            lines.append(f"  %slit_{uid} = call i8* {alloc_fn}(i64 {size_bytes})")
            for idx, (fname, ft) in enumerate(fields):
                et, ev = self.gen_expr(field_map[fname], env, lines)
                if not self._type_compatible(ft, et):
                    raise CompileError(
                        f"Campo '{fname}' da struct '{node.name}' espera '{self.type_name(ft)}', recebeu '{self.type_name(et)}'"
                    )
                ev = self.cast(lines, et, ev, ft)
                slot_uid = self.new_id()
                off = idx * 8
                lines.append(f"  %slotp_{slot_uid} = getelementptr i8, i8* %slit_{uid}, i64 {off}")
                if is_opaque_type(ft) or ft == "str":
                    lines.append(f"  %slotpp_{slot_uid} = bitcast i8* %slotp_{slot_uid} to i8**")
                    lines.append(f"  store i8* {ev}, i8** %slotpp_{slot_uid}, align 8")
                else:
                    lft = self.llvm_type(ft)
                    lines.append(f"  %slottp_{slot_uid} = bitcast i8* %slotp_{slot_uid} to {lft}*")
                    lines.append(f"  store {lft} {ev}, {lft}* %slottp_{slot_uid}, align 8")
            return ("struct", node.name), f"%slit_{uid}"

        raise CompileError(f"Expressão não suportada: {node}")

    def gen_call(self, node, env, lines, uid):
        name = node.name
        if name == "to_raw":
            # reinterpreta os bits de um double como i64 (não converte valor,
            # preserva o padrão de bits) — pra poder guardar double dentro de
            # um array, que só armazena i64 por slot.
            if len(node.args) != 1:
                raise CompileError("'to_raw' espera 1 argumento: to_raw(double)")
            t, v = self.gen_expr(node.args[0], env, lines)
            v = self.cast(lines, t, v, "double")
            lines.append(f"  %traw_{uid} = bitcast double {v} to i64")
            return "i64", f"%traw_{uid}"

        if name == "from_raw":
            # inverso de to_raw: reinterpreta os bits de um i64 (lido de um
            # array) de volta como double.
            if len(node.args) != 1:
                raise CompileError("'from_raw' espera 1 argumento: from_raw(i64)")
            t, v = self.gen_expr(node.args[0], env, lines)
            v = self.cast(lines, t, v, "i64")
            lines.append(f"  %fraw_{uid} = bitcast i64 {v} to double")
            return "double", f"%fraw_{uid}"

        if name == "sqrt":
            t, v = self.gen_expr(node.args[0], env, lines)
            v = self.cast(lines, t, v, "double")
            lines.append(f"  %sq_{uid} = call double @sqrt(double {v})")
            return "double", f"%sq_{uid}"

        if name == "time":
            lines.append(f"  %tv_{uid} = alloca [16 x i8], align 8")
            lines.append(f"  %tp_{uid} = getelementptr [16 x i8], [16 x i8]* %tv_{uid}, i32 0, i32 0")
            lines.append(f"  call i32 @gettimeofday(i8* %tp_{uid}, i8* null)")
            lines.append(f"  %sp_{uid} = bitcast i8* %tp_{uid} to i64*")
            lines.append(f"  %sv_{uid} = load i64, i64* %sp_{uid}")
            lines.append(f"  %sd_{uid} = sitofp i64 %sv_{uid} to double")
            lines.append(f"  %up_{uid} = getelementptr i8, i8* %tp_{uid}, i32 8")
            lines.append(f"  %up6_{uid} = bitcast i8* %up_{uid} to i64*")
            lines.append(f"  %uv_{uid} = load i64, i64* %up6_{uid}")
            lines.append(f"  %ud_{uid} = sitofp i64 %uv_{uid} to double")
            lines.append(f"  %uf_{uid} = fdiv double %ud_{uid}, 1000000.0")
            lines.append(f"  %now_{uid} = fadd double %sd_{uid}, %uf_{uid}")
            return "double", f"%now_{uid}"

        if name == "array":
            t, sv = self.gen_expr(node.args[0], env, lines)
            sv = self.cast(lines, t, sv, "i64")
            lines.append(f"  %bt_{uid} = mul nsw i64 {sv}, 8")
            alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
            lines.append(f"  %mr_{uid} = call i8* {alloc_fn}(i64 %bt_{uid})")
            lines.append(f"  %mi_{uid} = ptrtoint i8* %mr_{uid} to i64")
            return "i64", f"%mi_{uid}"

        if name == "input":
            lines.append(f"  %iv_{uid} = alloca i64, align 8")
            lines.append(f"  %fs_{uid} = getelementptr [4 x i8], [4 x i8]* @fmt_scan, i32 0, i32 0")
            lines.append(f"  call i32 (i8*, ...) @scanf(i8* %fs_{uid}, i64* %iv_{uid})")
            lines.append(f"  %rv_{uid} = load i64, i64* %iv_{uid}, align 8")
            return "i64", f"%rv_{uid}"

        if name == "sleep":
            if len(node.args) != 1:
                raise CompileError("'sleep' espera 1 argumento: sleep(segundos) — aceita inteiro ou float")
            t, v = self.gen_expr(node.args[0], env, lines)
            v = self.cast(lines, t, v, "double")
            lines.append(f"  %slus_d_{uid} = fmul double {v}, 1000000.0")
            lines.append(f"  %slus_{uid} = fptosi double %slus_d_{uid} to i32")
            lines.append(f"  call i32 @usleep(i32 %slus_{uid})")
            return "i64", "0"

        if name == "random":
            t, mv = self.gen_expr(node.args[0], env, lines)
            mv = self.cast(lines, t, mv, "i64")
            lines.append(f"  %rb_{uid} = alloca i64, align 8")
            lines.append(f"  %rpb_{uid} = bitcast i64* %rb_{uid} to i8*")
            lines.append(f"  %rgr_{uid} = call i64 @getrandom(i8* %rpb_{uid}, i64 8, i32 0)")
            lines.append(f"  %rgok_{uid} = icmp eq i64 %rgr_{uid}, 8")
            lines.append(f"  %rv_{uid} = load i64, i64* %rb_{uid}, align 8")
            lines.append(f"  %rvnz_{uid} = icmp ne i64 %rv_{uid}, 0")
            lines.append(f"  %rraw_{uid} = select i1 %rvnz_{uid}, i64 %rv_{uid}, i64 1")
            lines.append(f"  %rabs_{uid} = and i64 %rraw_{uid}, 9223372036854775807")
            lines.append(f"  %rr_{uid} = urem i64 %rabs_{uid}, {mv}")
            return "i64", f"%rr_{uid}"

        # --- Strings avançadas ---

        if name == "len":
            t, sv = self.gen_expr(node.args[0], env, lines)
            if t == "str":
                lines.append(f"  %ln_{uid} = call i64 @strlen(i8* {sv})")
                return "i64", f"%ln_{uid}"
            if is_array_type(t):
                lines.append(f"  %lni_{uid} = bitcast i8* {sv} to i64*")
                lines.append(f"  %ln_{uid} = load i64, i64* %lni_{uid}, align 8")
                return "i64", f"%ln_{uid}"
            raise CompileError("'len' espera string ou array nativo")

        if name == "str":
            t, v = self.gen_expr(node.args[0], env, lines)
            return "str", self.to_str(lines, t, v)

        if name == "darray":
            if len(node.args) != 1:
                raise CompileError("'darray' espera 1 argumento: darray(tamanho)")
            t, n = self.gen_expr(node.args[0], env, lines)
            n = self.cast(lines, t, n, "i64")
            alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
            total_uid = self.new_id()
            lines.append(f"  %darr_bytes_{total_uid} = add nsw i64 1, {n}")
            lines.append(f"  %darr_bytes2_{total_uid} = mul nsw i64 %darr_bytes_{total_uid}, 8")
            lines.append(f"  %darr_mem_{total_uid} = call i8* {alloc_fn}(i64 %darr_bytes2_{total_uid})")
            lines.append(f"  %darr_i64p_{total_uid} = bitcast i8* %darr_mem_{total_uid} to i64*")
            lines.append(f"  store i64 {n}, i64* %darr_i64p_{total_uid}, align 8")
            lines.append(f"  %darr_dat_{total_uid} = getelementptr i8, i8* %darr_mem_{total_uid}, i64 8")
            lines.append(f"  %darr_dptr_{total_uid} = bitcast i8* %darr_dat_{total_uid} to double*")
            lines.append(f"  %darr_idx_{total_uid} = alloca i64, align 8")
            lines.append(f"  store i64 0, i64* %darr_idx_{total_uid}, align 8")
            lines.append(f"  br label %darr_fill_{total_uid}")
            lines.append(f"darr_fill_{total_uid}:")
            lines.append(f"  %darr_i_{total_uid} = load i64, i64* %darr_idx_{total_uid}, align 8")
            lines.append(f"  %darr_cmp_{total_uid} = icmp slt i64 %darr_i_{total_uid}, {n}")
            lines.append(f"  br i1 %darr_cmp_{total_uid}, label %darr_body_{total_uid}, label %darr_end_{total_uid}")
            lines.append(f"darr_body_{total_uid}:")
            lines.append(f"  %darr_ep_{total_uid} = getelementptr double, double* %darr_dptr_{total_uid}, i64 %darr_i_{total_uid}")
            lines.append(f"  store double 0.0, double* %darr_ep_{total_uid}, align 8")
            lines.append(f"  %darr_i2_{total_uid} = add nsw i64 %darr_i_{total_uid}, 1")
            lines.append(f"  store i64 %darr_i2_{total_uid}, i64* %darr_idx_{total_uid}, align 8")
            lines.append(f"  br label %darr_fill_{total_uid}")
            lines.append(f"darr_end_{total_uid}:")
            return ("array", "double", 1), f"%darr_mem_{total_uid}"

        if name == "dmat":
            if len(node.args) != 2:
                raise CompileError("'dmat' espera 2 argumentos: dmat(linhas, colunas)")
            tr, rv = self.gen_expr(node.args[0], env, lines)
            tc, cv = self.gen_expr(node.args[1], env, lines)
            rv = self.cast(lines, tr, rv, "i64")
            cv = self.cast(lines, tc, cv, "i64")
            alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
            uidm = self.new_id()
            lines.append(f"  %dmat_rows_{uidm} = add nsw i64 {rv}, 0")
            lines.append(f"  %dmat_cols_{uidm} = add nsw i64 {cv}, 0")
            lines.append(f"  %dmat_slots_{uidm} = add nsw i64 2, {rv}")
            lines.append(f"  %dmat_bytes_{uidm} = mul nsw i64 %dmat_slots_{uidm}, 8")
            lines.append(f"  %dmat_mem_{uidm} = call i8* {alloc_fn}(i64 %dmat_bytes_{uidm})")
            lines.append(f"  %dmat_i64p_{uidm} = bitcast i8* %dmat_mem_{uidm} to i64*")
            lines.append(f"  store i64 {rv}, i64* %dmat_i64p_{uidm}, align 8")
            lines.append(f"  %dmat_colslot_{uidm} = getelementptr i64, i64* %dmat_i64p_{uidm}, i64 1")
            lines.append(f"  store i64 {cv}, i64* %dmat_colslot_{uidm}, align 8")
            lines.append(f"  %dmat_idx_{uidm} = alloca i64, align 8")
            lines.append(f"  store i64 0, i64* %dmat_idx_{uidm}, align 8")
            lines.append(f"  br label %dmat_fill_{uidm}")
            lines.append(f"dmat_fill_{uidm}:")
            lines.append(f"  %dmat_i_{uidm} = load i64, i64* %dmat_idx_{uidm}, align 8")
            lines.append(f"  %dmat_cmp_{uidm} = icmp slt i64 %dmat_i_{uidm}, {rv}")
            lines.append(f"  br i1 %dmat_cmp_{uidm}, label %dmat_body_{uidm}, label %dmat_end_{uidm}")
            lines.append(f"dmat_body_{uidm}:")
            lines.append(f"  %rowptrslot_{uidm} = getelementptr i8, i8* %dmat_mem_{uidm}, i64 16")
            lines.append(f"  %rowbyte_{uidm} = mul nsw i64 %dmat_i_{uidm}, 8")
            lines.append(f"  %rowptrslot2_{uidm} = getelementptr i8, i8* %rowptrslot_{uidm}, i64 %rowbyte_{uidm}")
            lines.append(f"  %rowptrslot3_{uidm} = bitcast i8* %rowptrslot2_{uidm} to i8**")
            # row allocation
            rowalloc_uid = self.new_id()
            lines.append(f"  %drow_bytes_{rowalloc_uid} = add nsw i64 1, %dmat_cols_{uidm}")
            lines.append(f"  %drow_bytes2_{rowalloc_uid} = mul nsw i64 %drow_bytes_{rowalloc_uid}, 8")
            lines.append(f"  %drow_mem_{rowalloc_uid} = call i8* {alloc_fn}(i64 %drow_bytes2_{rowalloc_uid})")
            lines.append(f"  %drow_i64p_{rowalloc_uid} = bitcast i8* %drow_mem_{rowalloc_uid} to i64*")
            lines.append(f"  store i64 %dmat_cols_{uidm}, i64* %drow_i64p_{rowalloc_uid}, align 8")
            lines.append(f"  %drow_dat_{rowalloc_uid} = getelementptr i8, i8* %drow_mem_{rowalloc_uid}, i64 8")
            lines.append(f"  %drow_dptr_{rowalloc_uid} = bitcast i8* %drow_dat_{rowalloc_uid} to double*")
            lines.append(f"  %drow_idx_{rowalloc_uid} = alloca i64, align 8")
            lines.append(f"  store i64 0, i64* %drow_idx_{rowalloc_uid}, align 8")
            lines.append(f"  br label %drow_fill_{rowalloc_uid}")
            lines.append(f"drow_fill_{rowalloc_uid}:")
            lines.append(f"  %drow_i_{rowalloc_uid} = load i64, i64* %drow_idx_{rowalloc_uid}, align 8")
            lines.append(f"  %drow_cmp_{rowalloc_uid} = icmp slt i64 %drow_i_{rowalloc_uid}, %dmat_cols_{uidm}")
            lines.append(f"  br i1 %drow_cmp_{rowalloc_uid}, label %drow_body_{rowalloc_uid}, label %drow_end_{rowalloc_uid}")
            lines.append(f"drow_body_{rowalloc_uid}:")
            lines.append(f"  %drow_ep_{rowalloc_uid} = getelementptr double, double* %drow_dptr_{rowalloc_uid}, i64 %drow_i_{rowalloc_uid}")
            lines.append(f"  store double 0.0, double* %drow_ep_{rowalloc_uid}, align 8")
            lines.append(f"  %drow_i2_{rowalloc_uid} = add nsw i64 %drow_i_{rowalloc_uid}, 1")
            lines.append(f"  store i64 %drow_i2_{rowalloc_uid}, i64* %drow_idx_{rowalloc_uid}, align 8")
            lines.append(f"  br label %drow_fill_{rowalloc_uid}")
            lines.append(f"drow_end_{rowalloc_uid}:")
            lines.append(f"  store i8* %drow_mem_{rowalloc_uid}, i8** %rowptrslot3_{uidm}, align 8")
            lines.append(f"  %dmat_i2_{uidm} = add nsw i64 %dmat_i_{uidm}, 1")
            lines.append(f"  store i64 %dmat_i2_{uidm}, i64* %dmat_idx_{uidm}, align 8")
            lines.append(f"  br label %dmat_fill_{uidm}")
            lines.append(f"dmat_end_{uidm}:")
            return ("array", "double", 2), f"%dmat_mem_{uidm}"

        if name == "matmul":
            if len(node.args) != 2:
                raise CompileError("'matmul' espera 2 argumentos: matmul(a, b)")
            ta, av = self.gen_expr(node.args[0], env, lines)
            tb, bv = self.gen_expr(node.args[1], env, lines)
            if not (is_array_type(ta) and is_array_type(tb) and ta == ("array", "double", 2) and tb == ("array", "double", 2)):
                raise CompileError("matmul nativo espera matrizes double[][]")

            # Layout:
            #   [0] rows
            #   [1] cols
            #   [2..] row pointers (i8*)
            a_hdr_uid = self.new_id()
            b_hdr_uid = self.new_id()
            lines.append(f"  %a_i64p_{a_hdr_uid} = bitcast i8* {av} to i64*")
            lines.append(f"  %a_rows_{a_hdr_uid} = load i64, i64* %a_i64p_{a_hdr_uid}, align 8")
            lines.append(f"  %a_cols_p_{a_hdr_uid} = getelementptr i64, i64* %a_i64p_{a_hdr_uid}, i64 1")
            lines.append(f"  %a_cols_{a_hdr_uid} = load i64, i64* %a_cols_p_{a_hdr_uid}, align 8")
            lines.append(f"  %b_i64p_{b_hdr_uid} = bitcast i8* {bv} to i64*")
            lines.append(f"  %b_rows_{b_hdr_uid} = load i64, i64* %b_i64p_{b_hdr_uid}, align 8")
            lines.append(f"  %b_cols_p_{b_hdr_uid} = getelementptr i64, i64* %b_i64p_{b_hdr_uid}, i64 1")
            lines.append(f"  %b_cols_{b_hdr_uid} = load i64, i64* %b_cols_p_{b_hdr_uid}, align 8")
            lines.append(f"  %mm_dims_ok_{uid} = icmp eq i64 %a_cols_{a_hdr_uid}, %b_rows_{b_hdr_uid}")
            lines.append(f"  br i1 %mm_dims_ok_{uid}, label %mm_ok_{uid}, label %mm_bad_{uid}")
            lines.append(f"mm_bad_{uid}:")
            err_text = "matmul: dimensoes incompativeis"
            err_uid = self.new_id()
            err_escaped = llvm_escape_string(err_text)
            err_byte_len = len(err_text.encode("utf-8")) + 1
            self.strings.append(
                f'@.str.{err_uid} = private unnamed_addr constant [{err_byte_len} x i8] c"{err_escaped}\\00"'
            )
            lines.append(f"  %mm_errp_{uid} = getelementptr [{err_byte_len} x i8], [{err_byte_len} x i8]* @.str.{err_uid}, i32 0, i32 0")
            lines.append(f"  store i8* %mm_errp_{uid}, i8** @__ares_exc_msg")
            lines.append("  store i32 1, i32* @__ares_exc_flag")
            target = self.catch_stack[-1] if self.catch_stack else self.func_exc_exit
            lines.append(f"  br label %{target}")
            lines.append(f"mm_ok_{uid}:")

            alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
            out_uid = self.new_id()
            lines.append(f"  %mm_out_slots_{out_uid} = add nsw i64 2, %a_rows_{a_hdr_uid}")
            lines.append(f"  %mm_out_bytes_{out_uid} = mul nsw i64 %mm_out_slots_{out_uid}, 8")
            lines.append(f"  %mm_out_mem_{out_uid} = call i8* {alloc_fn}(i64 %mm_out_bytes_{out_uid})")
            lines.append(f"  %mm_out_i64p_{out_uid} = bitcast i8* %mm_out_mem_{out_uid} to i64*")
            lines.append(f"  store i64 %a_rows_{a_hdr_uid}, i64* %mm_out_i64p_{out_uid}, align 8")
            lines.append(f"  %mm_out_cols_p_{out_uid} = getelementptr i64, i64* %mm_out_i64p_{out_uid}, i64 1")
            lines.append(f"  store i64 %b_cols_{b_hdr_uid}, i64* %mm_out_cols_p_{out_uid}, align 8")

            rows_base_uid = self.new_id()
            b_rows_base_uid = self.new_id()
            out_rows_base_uid = self.new_id()
            lines.append(f"  %mm_a_rows_base_{rows_base_uid} = getelementptr i8, i8* {av}, i64 16")
            lines.append(f"  %mm_b_rows_base_{b_rows_base_uid} = getelementptr i8, i8* {bv}, i64 16")
            lines.append(f"  %mm_out_rows_base_{out_rows_base_uid} = getelementptr i8, i8* %mm_out_mem_{out_uid}, i64 16")

            i_slot_uid = self.new_id()
            lines.append(f"  %mm_i_{i_slot_uid} = alloca i64, align 8")
            lines.append(f"  store i64 0, i64* %mm_i_{i_slot_uid}, align 8")
            lines.append(f"  br label %mm_i_cond_{uid}")
            lines.append(f"mm_i_cond_{uid}:")
            lines.append(f"  %mm_i_v_{i_slot_uid} = load i64, i64* %mm_i_{i_slot_uid}, align 8")
            lines.append(f"  %mm_i_cmp_{uid} = icmp slt i64 %mm_i_v_{i_slot_uid}, %a_rows_{a_hdr_uid}")
            lines.append(f"  br i1 %mm_i_cmp_{uid}, label %mm_i_body_{uid}, label %mm_done_{uid}")

            lines.append(f"mm_i_body_{uid}:")
            row_alloc_uid = self.new_id()
            lines.append(f"  %mm_row_slots_{row_alloc_uid} = add nsw i64 1, %b_cols_{b_hdr_uid}")
            lines.append(f"  %mm_row_bytes_{row_alloc_uid} = mul nsw i64 %mm_row_slots_{row_alloc_uid}, 8")
            lines.append(f"  %mm_row_mem_{row_alloc_uid} = call i8* {alloc_fn}(i64 %mm_row_bytes_{row_alloc_uid})")
            lines.append(f"  %mm_row_i64p_{row_alloc_uid} = bitcast i8* %mm_row_mem_{row_alloc_uid} to i64*")
            lines.append(f"  store i64 %b_cols_{b_hdr_uid}, i64* %mm_row_i64p_{row_alloc_uid}, align 8")
            lines.append(f"  %mm_row_dat_{row_alloc_uid} = getelementptr i8, i8* %mm_row_mem_{row_alloc_uid}, i64 8")
            lines.append(f"  %mm_row_dptr_{row_alloc_uid} = bitcast i8* %mm_row_dat_{row_alloc_uid} to double*")

            a_row_byte_uid = self.new_id()
            lines.append(f"  %mm_a_row_byte_{a_row_byte_uid} = mul nsw i64 %mm_i_v_{i_slot_uid}, 8")
            lines.append(f"  %mm_a_row_slot_{a_row_byte_uid} = getelementptr i8, i8* %mm_a_rows_base_{rows_base_uid}, i64 %mm_a_row_byte_{a_row_byte_uid}")
            lines.append(f"  %mm_a_row_slotp_{a_row_byte_uid} = bitcast i8* %mm_a_row_slot_{a_row_byte_uid} to i8**")
            lines.append(f"  %mm_a_row_ptr_{a_row_byte_uid} = load i8*, i8** %mm_a_row_slotp_{a_row_byte_uid}, align 8")
            lines.append(f"  %mm_a_row_data_{a_row_byte_uid} = getelementptr i8, i8* %mm_a_row_ptr_{a_row_byte_uid}, i64 8")
            lines.append(f"  %mm_a_row_dptr_{a_row_byte_uid} = bitcast i8* %mm_a_row_data_{a_row_byte_uid} to double*")

            lines.append(f"  %mm_row_byte_{row_alloc_uid} = mul nsw i64 %mm_i_v_{i_slot_uid}, 8")
            lines.append(f"  %mm_row_slot_{row_alloc_uid} = getelementptr i8, i8* %mm_out_rows_base_{out_rows_base_uid}, i64 %mm_row_byte_{row_alloc_uid}")
            lines.append(f"  %mm_row_slotp_{row_alloc_uid} = bitcast i8* %mm_row_slot_{row_alloc_uid} to i8**")
            lines.append(f"  store i8* %mm_row_mem_{row_alloc_uid}, i8** %mm_row_slotp_{row_alloc_uid}, align 8")

            j_slot_uid = self.new_id()
            lines.append(f"  %mm_j_{j_slot_uid} = alloca i64, align 8")
            lines.append(f"  store i64 0, i64* %mm_j_{j_slot_uid}, align 8")
            lines.append(f"  br label %mm_j_cond_{uid}")
            lines.append(f"mm_j_cond_{uid}:")
            lines.append(f"  %mm_j_v_{j_slot_uid} = load i64, i64* %mm_j_{j_slot_uid}, align 8")
            lines.append(f"  %mm_j_cmp_{uid} = icmp slt i64 %mm_j_v_{j_slot_uid}, %b_cols_{b_hdr_uid}")
            lines.append(f"  br i1 %mm_j_cmp_{uid}, label %mm_j_body_{uid}, label %mm_j_end_{uid}")

            lines.append(f"mm_j_body_{uid}:")
            sum_slot_uid = self.new_id()
            lines.append(f"  %mm_sum_{sum_slot_uid} = alloca double, align 8")
            lines.append(f"  store double 0.0, double* %mm_sum_{sum_slot_uid}, align 8")

            k_slot_uid = self.new_id()
            lines.append(f"  %mm_k_{k_slot_uid} = alloca i64, align 8")
            lines.append(f"  store i64 0, i64* %mm_k_{k_slot_uid}, align 8")
            lines.append(f"  br label %mm_k_cond_{uid}")
            lines.append(f"mm_k_cond_{uid}:")
            lines.append(f"  %mm_k_v_{k_slot_uid} = load i64, i64* %mm_k_{k_slot_uid}, align 8")
            lines.append(f"  %mm_k_cmp_{uid} = icmp slt i64 %mm_k_v_{k_slot_uid}, %a_cols_{a_hdr_uid}")
            lines.append(f"  br i1 %mm_k_cmp_{uid}, label %mm_k_body_{uid}, label %mm_k_end_{uid}")

            lines.append(f"mm_k_body_{uid}:")
            b_row_uid = self.new_id()
            lines.append(f"  %mm_b_row_byte_{b_row_uid} = mul nsw i64 %mm_k_v_{k_slot_uid}, 8")
            lines.append(f"  %mm_b_row_slot_{b_row_uid} = getelementptr i8, i8* %mm_b_rows_base_{b_rows_base_uid}, i64 %mm_b_row_byte_{b_row_uid}")
            lines.append(f"  %mm_b_row_slotp_{b_row_uid} = bitcast i8* %mm_b_row_slot_{b_row_uid} to i8**")
            lines.append(f"  %mm_b_row_ptr_{b_row_uid} = load i8*, i8** %mm_b_row_slotp_{b_row_uid}, align 8")
            lines.append(f"  %mm_b_row_data_{b_row_uid} = getelementptr i8, i8* %mm_b_row_ptr_{b_row_uid}, i64 8")
            lines.append(f"  %mm_b_row_dptr_{b_row_uid} = bitcast i8* %mm_b_row_data_{b_row_uid} to double*")

            a_ep_uid = self.new_id()
            b_ep_uid = self.new_id()
            sum_uid = self.new_id()
            lines.append(f"  %mm_a_ep_{a_ep_uid} = getelementptr double, double* %mm_a_row_dptr_{a_row_byte_uid}, i64 %mm_k_v_{k_slot_uid}")
            lines.append(f"  %mm_b_ep_{b_ep_uid} = getelementptr double, double* %mm_b_row_dptr_{b_row_uid}, i64 %mm_j_v_{j_slot_uid}")
            lines.append(f"  %mm_a_val_{a_ep_uid} = load double, double* %mm_a_ep_{a_ep_uid}, align 8")
            lines.append(f"  %mm_b_val_{b_ep_uid} = load double, double* %mm_b_ep_{b_ep_uid}, align 8")
            lines.append(f"  %mm_mul_{sum_uid} = fmul fast double %mm_a_val_{a_ep_uid}, %mm_b_val_{b_ep_uid}")
            lines.append(f"  %mm_sumv_{sum_uid} = load double, double* %mm_sum_{sum_slot_uid}, align 8")
            lines.append(f"  %mm_sum2_{sum_uid} = fadd fast double %mm_sumv_{sum_uid}, %mm_mul_{sum_uid}")
            lines.append(f"  store double %mm_sum2_{sum_uid}, double* %mm_sum_{sum_slot_uid}, align 8")
            lines.append(f"  %mm_k_next_{k_slot_uid} = add nsw i64 %mm_k_v_{k_slot_uid}, 1")
            lines.append(f"  store i64 %mm_k_next_{k_slot_uid}, i64* %mm_k_{k_slot_uid}, align 8")
            lines.append(f"  br label %mm_k_cond_{uid}")

            lines.append(f"mm_k_end_{uid}:")
            out_elem_uid = self.new_id()
            lines.append(f"  %mm_sum_final_{out_elem_uid} = load double, double* %mm_sum_{sum_slot_uid}, align 8")
            lines.append(f"  %mm_out_elem_{out_elem_uid} = getelementptr double, double* %mm_row_dptr_{row_alloc_uid}, i64 %mm_j_v_{j_slot_uid}")
            lines.append(f"  store double %mm_sum_final_{out_elem_uid}, double* %mm_out_elem_{out_elem_uid}, align 8")
            lines.append(f"  %mm_j_next_{j_slot_uid} = add nsw i64 %mm_j_v_{j_slot_uid}, 1")
            lines.append(f"  store i64 %mm_j_next_{j_slot_uid}, i64* %mm_j_{j_slot_uid}, align 8")
            lines.append(f"  br label %mm_j_cond_{uid}")

            lines.append(f"mm_j_end_{uid}:")
            lines.append(f"  %mm_i_next_{i_slot_uid} = add nsw i64 %mm_i_v_{i_slot_uid}, 1")
            lines.append(f"  store i64 %mm_i_next_{i_slot_uid}, i64* %mm_i_{i_slot_uid}, align 8")
            lines.append(f"  br label %mm_i_cond_{uid}")

            lines.append(f"mm_done_{uid}:")
            return ("array", "double", 2), f"%mm_out_mem_{out_uid}"

        if name in ("upper", "lower"):
            t, sv = self.gen_expr(node.args[0], env, lines)
            if t != "str":
                raise CompileError(f"'{name}' espera uma string")
            libc_fn = "toupper" if name == "upper" else "tolower"
            lines.append(f"  %clen_{uid} = call i64 @strlen(i8* {sv})")
            alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
            lines.append(f"  %clen1_{uid} = add nsw i64 %clen_{uid}, 1")
            lines.append(f"  %cbuf_{uid} = call i8* {alloc_fn}(i64 %clen1_{uid})")
            lines.append(f"  %cidx_{uid} = alloca i64, align 8")
            lines.append(f"  store i64 0, i64* %cidx_{uid}, align 8")
            lines.append(f"  br label %cc_{uid}")
            lines.append(f"cc_{uid}:")
            lines.append(f"  %ci_{uid} = load i64, i64* %cidx_{uid}, align 8")
            lines.append(f"  %ccmp_{uid} = icmp slt i64 %ci_{uid}, %clen_{uid}")
            lines.append(f"  br i1 %ccmp_{uid}, label %cb_{uid}, label %ce_{uid}")
            lines.append(f"cb_{uid}:")
            lines.append(f"  %csp_{uid} = getelementptr i8, i8* {sv}, i64 %ci_{uid}")
            lines.append(f"  %cch_{uid} = load i8, i8* %csp_{uid}, align 1")
            lines.append(f"  %cchi_{uid} = sext i8 %cch_{uid} to i32")
            lines.append(f"  %ccv_{uid} = call i32 @{libc_fn}(i32 %cchi_{uid})")
            lines.append(f"  %ccc_{uid} = trunc i32 %ccv_{uid} to i8")
            lines.append(f"  %cdp_{uid} = getelementptr i8, i8* %cbuf_{uid}, i64 %ci_{uid}")
            lines.append(f"  store i8 %ccc_{uid}, i8* %cdp_{uid}, align 1")
            lines.append(f"  %ci2_{uid} = add nsw i64 %ci_{uid}, 1")
            lines.append(f"  store i64 %ci2_{uid}, i64* %cidx_{uid}, align 8")
            lines.append(f"  br label %cc_{uid}")
            lines.append(f"ce_{uid}:")
            lines.append(f"  %cep_{uid} = getelementptr i8, i8* %cbuf_{uid}, i64 %clen_{uid}")
            lines.append(f"  store i8 0, i8* %cep_{uid}, align 1")
            return "str", f"%cbuf_{uid}"

        if name == "substr":
            t0, sv = self.gen_expr(node.args[0], env, lines)
            if t0 != "str":
                raise CompileError("'substr' espera uma string como primeiro argumento")
            t1, startv = self.gen_expr(node.args[1], env, lines)
            startv = self.cast(lines, t1, startv, "i64")
            t2, lenv = self.gen_expr(node.args[2], env, lines)
            lenv = self.cast(lines, t2, lenv, "i64")
            alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
            lines.append(f"  %sblen1_{uid} = add nsw i64 {lenv}, 1")
            lines.append(f"  %sbbuf_{uid} = call i8* {alloc_fn}(i64 %sblen1_{uid})")
            lines.append(f"  %sbsrc_{uid} = getelementptr i8, i8* {sv}, i64 {startv}")
            lines.append(f"  call i8* @strncpy(i8* %sbbuf_{uid}, i8* %sbsrc_{uid}, i64 {lenv})")
            lines.append(f"  %sbend_{uid} = getelementptr i8, i8* %sbbuf_{uid}, i64 {lenv}")
            lines.append(f"  store i8 0, i8* %sbend_{uid}, align 1")
            return "str", f"%sbbuf_{uid}"

        if name == "char_at":
            t0, sv = self.gen_expr(node.args[0], env, lines)
            if t0 != "str":
                raise CompileError("'char_at' espera uma string como primeiro argumento")
            t1, idxv = self.gen_expr(node.args[1], env, lines)
            idxv = self.cast(lines, t1, idxv, "i64")
            alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
            lines.append(f"  %cabuf_{uid} = call i8* {alloc_fn}(i64 2)")
            lines.append(f"  %casrc_{uid} = getelementptr i8, i8* {sv}, i64 {idxv}")
            lines.append(f"  %cach_{uid} = load i8, i8* %casrc_{uid}, align 1")
            lines.append(f"  store i8 %cach_{uid}, i8* %cabuf_{uid}, align 1")
            lines.append(f"  %caend_{uid} = getelementptr i8, i8* %cabuf_{uid}, i64 1")
            lines.append(f"  store i8 0, i8* %caend_{uid}, align 1")
            return "str", f"%cabuf_{uid}"

        # --- I/O avançado ---

        if name == "read_line":
            alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
            lines.append(f"  %rlbuf_{uid} = call i8* {alloc_fn}(i64 1024)")
            lines.append(f"  %rln_{uid} = call i64 @read(i32 0, i8* %rlbuf_{uid}, i64 1023)")
            lines.append(f"  %rlneg_{uid} = icmp slt i64 %rln_{uid}, 0")
            lines.append(f"  %rln2_{uid} = select i1 %rlneg_{uid}, i64 0, i64 %rln_{uid}")
            lines.append(f"  %rlendp_{uid} = getelementptr i8, i8* %rlbuf_{uid}, i64 %rln2_{uid}")
            lines.append(f"  store i8 0, i8* %rlendp_{uid}, align 1")
            lines.append(f"  %rlhas_{uid} = icmp sgt i64 %rln2_{uid}, 0")
            lines.append(f"  br i1 %rlhas_{uid}, label %rlchk_{uid}, label %rlskip_{uid}")
            lines.append(f"rlchk_{uid}:")
            lines.append(f"  %rllast_{uid} = sub nsw i64 %rln2_{uid}, 1")
            lines.append(f"  %rllastp_{uid} = getelementptr i8, i8* %rlbuf_{uid}, i64 %rllast_{uid}")
            lines.append(f"  %rllastc_{uid} = load i8, i8* %rllastp_{uid}, align 1")
            lines.append(f"  %rlisnl_{uid} = icmp eq i8 %rllastc_{uid}, 10")
            lines.append(f"  br i1 %rlisnl_{uid}, label %rlstrip_{uid}, label %rlskip_{uid}")
            lines.append(f"rlstrip_{uid}:")
            lines.append(f"  store i8 0, i8* %rllastp_{uid}, align 1")
            lines.append(f"  br label %rlskip_{uid}")
            lines.append(f"rlskip_{uid}:")
            return "str", f"%rlbuf_{uid}"

        if name == "read_file":
            t, pv = self.gen_expr(node.args[0], env, lines)
            if t != "str":
                raise CompileError("'read_file' espera o caminho como string")
            alloc_fn = "@GC_malloc" if self.use_gc else "@malloc"
            lines.append(f"  %rfres_{uid} = alloca i8*, align 8")
            lines.append(f"  %rfmode_{uid} = getelementptr [2 x i8], [2 x i8]* @fmt_mode_r, i32 0, i32 0")
            lines.append(f"  %rffp_{uid} = call i8* @fopen(i8* {pv}, i8* %rfmode_{uid})")
            lines.append(f"  %rfnull_{uid} = icmp eq i8* %rffp_{uid}, null")
            lines.append(f"  br i1 %rfnull_{uid}, label %rffail_{uid}, label %rfok_{uid}")
            lines.append(f"rffail_{uid}:")
            lines.append(f"  %rfempty_{uid} = call i8* {alloc_fn}(i64 1)")
            lines.append(f"  store i8 0, i8* %rfempty_{uid}, align 1")
            lines.append(f"  store i8* %rfempty_{uid}, i8** %rfres_{uid}, align 8")
            lines.append(f"  br label %rfdone_{uid}")
            lines.append(f"rfok_{uid}:")
            lines.append(f"  call i32 @fseek(i8* %rffp_{uid}, i64 0, i32 2)")
            lines.append(f"  %rfsz_{uid} = call i64 @ftell(i8* %rffp_{uid})")
            lines.append(f"  call i32 @fseek(i8* %rffp_{uid}, i64 0, i32 0)")
            lines.append(f"  %rfsz1_{uid} = add nsw i64 %rfsz_{uid}, 1")
            lines.append(f"  %rfbuf_{uid} = call i8* {alloc_fn}(i64 %rfsz1_{uid})")
            lines.append(f"  %rfnr_{uid} = call i64 @fread(i8* %rfbuf_{uid}, i64 1, i64 %rfsz_{uid}, i8* %rffp_{uid})")
            lines.append(f"  %rfendp_{uid} = getelementptr i8, i8* %rfbuf_{uid}, i64 %rfnr_{uid}")
            lines.append(f"  store i8 0, i8* %rfendp_{uid}, align 1")
            lines.append(f"  call i32 @fclose(i8* %rffp_{uid})")
            lines.append(f"  store i8* %rfbuf_{uid}, i8** %rfres_{uid}, align 8")
            lines.append(f"  br label %rfdone_{uid}")
            lines.append(f"rfdone_{uid}:")
            lines.append(f"  %rfresult_{uid} = load i8*, i8** %rfres_{uid}, align 8")
            return "str", f"%rfresult_{uid}"

        if name in ("write_file", "append_file"):
            t0, pv = self.gen_expr(node.args[0], env, lines)
            if t0 != "str":
                raise CompileError(f"'{name}' espera o caminho como string")
            t1, cv = self.gen_expr(node.args[1], env, lines)
            if t1 != "str":
                raise CompileError(f"'{name}' espera o conteúdo como string")
            mode_const = "@fmt_mode_a" if name == "append_file" else "@fmt_mode_w"
            lines.append(f"  %wfres_{uid} = alloca i64, align 8")
            lines.append(f"  %wfmode_{uid} = getelementptr [2 x i8], [2 x i8]* {mode_const}, i32 0, i32 0")
            lines.append(f"  %wffp_{uid} = call i8* @fopen(i8* {pv}, i8* %wfmode_{uid})")
            lines.append(f"  %wfnull_{uid} = icmp eq i8* %wffp_{uid}, null")
            lines.append(f"  br i1 %wfnull_{uid}, label %wffail_{uid}, label %wfok_{uid}")
            lines.append(f"wffail_{uid}:")
            lines.append(f"  store i64 0, i64* %wfres_{uid}, align 8")
            lines.append(f"  br label %wfdone_{uid}")
            lines.append(f"wfok_{uid}:")
            lines.append(f"  %wflen_{uid} = call i64 @strlen(i8* {cv})")
            lines.append(f"  call i64 @fwrite(i8* {cv}, i64 1, i64 %wflen_{uid}, i8* %wffp_{uid})")
            lines.append(f"  call i32 @fclose(i8* %wffp_{uid})")
            lines.append(f"  store i64 1, i64* %wfres_{uid}, align 8")
            lines.append(f"  br label %wfdone_{uid}")
            lines.append(f"wfdone_{uid}:")
            lines.append(f"  %wfresult_{uid} = load i64, i64* %wfres_{uid}, align 8")
            return "i64", f"%wfresult_{uid}"

        SINGLE_ARG_MATH = {
            "sin": "sin", "cos": "cos", "tan": "tan", "atan": "atan",
            "log": "log", "log10": "log10", "exp": "exp",
            "floor": "floor", "ceil": "ceil",
        }
        if name in SINGLE_ARG_MATH:
            t, v = self.gen_expr(node.args[0], env, lines)
            v = self.cast(lines, t, v, "double")
            lines.append(f"  %m_{uid} = call double @{SINGLE_ARG_MATH[name]}(double {v})")
            return "double", f"%m_{uid}"

        if name in ("pow", "atan2"):
            llvm_name = "pow" if name == "pow" else "atan2"
            t1, v1 = self.gen_expr(node.args[0], env, lines)
            t2, v2 = self.gen_expr(node.args[1], env, lines)
            v1 = self.cast(lines, t1, v1, "double")
            v2 = self.cast(lines, t2, v2, "double")
            lines.append(f"  %m_{uid} = call double @{llvm_name}(double {v1}, double {v2})")
            return "double", f"%m_{uid}"

        if name == "pi":
            return "double", fmt_double_literal(_pymath.pi)

        if name == "abs":
            t, v = self.gen_expr(node.args[0], env, lines)
            if t == "double":
                lines.append(f"  %m_{uid} = call double @fabs(double {v})")
                return "double", f"%m_{uid}"
            lines.append(f"  %neg_{uid} = sub nsw i64 0, {v}")
            lines.append(f"  %isneg_{uid} = icmp slt i64 {v}, 0")
            lines.append(f"  %m_{uid} = select i1 %isneg_{uid}, i64 %neg_{uid}, i64 {v}")
            return "i64", f"%m_{uid}"

        if name in ("min", "max"):
            t1, v1 = self.gen_expr(node.args[0], env, lines)
            t2, v2 = self.gen_expr(node.args[1], env, lines)
            is_float = t1 == "double" or t2 == "double"
            if is_float:
                v1 = self.cast(lines, t1, v1, "double")
                v2 = self.cast(lines, t2, v2, "double")
                op = "olt" if name == "min" else "ogt"
                lines.append(f"  %cmp_{uid} = fcmp {op} double {v1}, {v2}")
                lines.append(f"  %m_{uid} = select i1 %cmp_{uid}, double {v1}, double {v2}")
                return "double", f"%m_{uid}"
            op = "slt" if name == "min" else "sgt"
            lines.append(f"  %cmp_{uid} = icmp {op} i64 {v1}, {v2}")
            lines.append(f"  %m_{uid} = select i1 %cmp_{uid}, i64 {v1}, i64 {v2}")
            return "i64", f"%m_{uid}"

        if name in env:
            # variável local (normalmente um parâmetro) guardando um ponteiro
            # de função, ex.: fn executar(func, x, y) { return func(x, y) }.
            # Convenção: assume retorno i64 e todos os parâmetros i64 — é o
            # mesmo formato usado ao passar uma função como valor (ver Var
            # em gen_expr). Não há checagem de tipo real entre o que foi
            # passado e como é chamado aqui.
            t = env[name]
            if t != "i64":
                raise CompileError(f"'{name}' não é uma função nem um ponteiro de função válido")
            arg_strs = []
            for a in node.args:
                at, av = self.gen_expr(a, env, lines)
                if at == "str":
                    raise CompileError(f"'{name}': chamada indireta ainda não aceita argumentos do tipo string")
                av = self.cast(lines, at, av, "i64")
                arg_strs.append(f"i64 {av}")
            params_ty = ", ".join(["i64"] * len(node.args))
            fnty = f"i64 ({params_ty})"
            lines.append(f"  %fpv_{uid} = load i64, i64* %{name}, align 8")
            lines.append(f"  %fp_{uid} = inttoptr i64 %fpv_{uid} to {fnty}*")
            lines.append(f"  %ind_{uid} = call {fnty} %fp_{uid}({', '.join(arg_strs)})")
            return "i64", f"%ind_{uid}"

        if name not in self.functions:
            raise CompileError(f"Função '{name}' não existe (nem foi declarada com 'extern')")
        sig = self.functions[name]
        if len(sig["params"]) != len(node.args):
            raise CompileError(f"'{name}' espera {len(sig['params'])} argumento(s), recebeu {len(node.args)}")
        arg_strs = []
        for i, a in enumerate(node.args):
            t, v = self.gen_expr(a, env, lines)
            param_t = sig["params"][i]
            if is_opaque_type(param_t):
                if t != param_t:
                    raise CompileError(
                        f"'{name}': argumento {i + 1} esperado do tipo '{self.type_name(param_t)}', recebeu '{self.type_name(t)}'"
                    )
                arg_strs.append(f"i8* {v}")
                continue
            if param_t == "str" or t == "str":
                if t != param_t:
                    raise CompileError(
                        f"'{name}': argumento {i + 1} esperado do tipo '{self.type_name(param_t)}', recebeu '{self.type_name(t)}'"
                    )
                arg_strs.append(f"i8* {v}")
                continue
            v = self.cast(lines, t, v, param_t)
            arg_strs.append(f"{param_t} {v}")
        ret_t = sig["ret"]
        is_extern = sig.get("extern", False)
        if ret_t == "void":
            lines.append(f"  call void @{name}({', '.join(arg_strs)})")
            if not is_extern:
                self._emit_exc_check(lines, uid)
            return "i64", "0"
        ret_llvm = self.llvm_type(ret_t)
        lines.append(f"  %call_{uid} = call {ret_llvm} @{name}({', '.join(arg_strs)})")
        if not is_extern:
            self._emit_exc_check(lines, uid)
        return ret_t, f"%call_{uid}"

    def _emit_exc_check(self, lines, uid):
        # Chamado logo depois de QUALQUER call a uma função aresY (não
        # extern): se a função chamada (ou algo mais fundo na pilha de
        # chamadas dela) deu throw sem capturar, a flag global fica ligada.
        # Aqui a gente detecta isso e pula direto pro catch ativo (se
        # estivermos dentro de um try) ou pro retorno antecipado da função
        # atual (propagando a exceção mais um nível pra cima). É assim que
        # o throw "atravessa" chamadas de função sem precisar de
        # invoke/landingpad de verdade.
        target = self.catch_stack[-1] if self.catch_stack else self.func_exc_exit
        cont_label = f"exc_cont_{uid}"
        lines.append(f"  %excf_{uid} = load i32, i32* @__ares_exc_flag")
        lines.append(f"  %excc_{uid} = icmp ne i32 %excf_{uid}, 0")
        lines.append(f"  br i1 %excc_{uid}, label %{target}, label %{cont_label}")
        lines.append(f"{cont_label}:")



# ---------------------------------------------------------------------------
# 5. BACKEND NATIVO (clang) — sem interpretador em Python
# ---------------------------------------------------------------------------
#
# "aresy programa.ay" e o REPL não interpretam nada em Python: os dois geram
# LLVM IR de verdade (a mesma coisa que "aresy build" gera) e chamam o clang
# por baixo dos panos pra virar binário nativo, executam esse binário e
# limpam os arquivos temporários depois. A diferença pro "build" é só que
# aqui isso é automático — você não precisa chamar o clang na mão.

import os
import shutil
import subprocess
import tempfile
import json
import urllib.request
import urllib.error


PACKAGES_DIR = "ares_packages"
MANIFEST_NAME = "aresy.json"
# Índice central de pacotes ("PyPI do aresY") — usado quando "aresy install"
# recebe só um nome, sem URL nenhuma (ex.: "aresy install numAres").
INDEX_REPO_RAW_BASE = "https://raw.githubusercontent.com/Jotaroofdioinbrando/aresy-index/main"
INDEX_URL = f"{INDEX_REPO_RAW_BASE}/index.json"


def _resolve_ay_import(name, base_dir):
    """Acha o arquivo .ay de um 'import nome'/'import "nome.ay"'.

    Ordem de busca:
    1. Caminho relativo normal (import local, como sempre funcionou).
    2. ares_packages/<nome-sem-.ay>/<nome-sem-.ay>.ay — pacote instalado
       via `aresy install` (ver PackageManager mais abaixo).
    """
    direct = os.path.normpath(os.path.join(base_dir, name))
    if os.path.isfile(direct):
        return direct
    stem = name[:-3] if name.endswith(".ay") else name
    pkg_path = os.path.normpath(os.path.join(base_dir, PACKAGES_DIR, stem, stem + ".ay"))
    if os.path.isfile(pkg_path):
        return pkg_path
    return direct  # não achou em lugar nenhum; devolve o caminho direto pro erro apontar pra ele


def _read_ay_source(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise CompileError(f"Não foi possível abrir a biblioteca '{path}': {e}")


def expand_ay_imports(stmts, base_dir, seen):
    """Resolve `import "arquivo.ay"` de forma recursiva, trazendo as fn/extern
    declaradas no arquivo importado pro programa atual — uma espécie de
    "#include" simples: sem namespace, sem exportação seletiva, tudo que a
    biblioteca declara no topo do arquivo fica visível pra quem importou.

    `import "nome_de_lib_C"` (sem terminar em .ay) continua funcionando como
    antes — vira -lNOME na hora de linkar com o clang — e não é tocado aqui.

    `seen` é um set de caminhos absolutos já importados nesse programa (ou,
    no REPL, na sessão inteira); evita reimportar o mesmo arquivo duas vezes
    e evita loop infinito em import circular (a -> b -> a)."""
    out = []
    for s in stmts:
        if isinstance(s, ImportDecl) and s.name.endswith(".ay"):
            lib_path = _resolve_ay_import(s.name, base_dir)
            if lib_path in seen:
                continue
            if not os.path.isfile(lib_path):
                stem = s.name[:-3] if s.name.endswith(".ay") else s.name
                raise CompileError(
                    f"Biblioteca '{s.name}' não encontrada (procurei em {lib_path} "
                    f"e em {PACKAGES_DIR}/{stem}/{stem}.ay). Se for um pacote de terceiros, "
                    f"rode 'aresy install' primeiro."
                )
            seen.add(lib_path)
            lib_src = _read_ay_source(lib_path)
            lib_stmts = Parser(tokenize(lib_src)).parse_program()
            if any(isinstance(x, FuncDef) and x.name == "main" for x in lib_stmts):
                raise CompileError(
                    f"'{s.name}' foi importada com 'import' — bibliotecas não podem "
                    "definir main() (só o arquivo principal pode)"
                )
            out.extend(expand_ay_imports(lib_stmts, os.path.dirname(lib_path), seen))
        else:
            out.append(s)
    return out


def find_clang():
    for candidate in ("clang", "clang-19", "clang-18", "clang-17", "clang-16"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


# =============================================================================
# Gerenciador de pacotes ("aresy install", tipo um pip bem simples)
#
# Um pacote é só um repositório git cujo topo tem um arquivo <nome>.ay
# (o mesmo padrão que "import nome" já procura localmente). O manifesto
# do projeto (aresy.json) lista as dependências como {nome: url_do_git}.
# "aresy install" clona (ou dá pull, se já existir) cada uma delas dentro
# de ares_packages/<nome>/. Depois disso, "import nome" no seu programa
# passa a enxergar o pacote automaticamente (ver _resolve_ay_import acima)
# — não precisa de nenhuma sintaxe nova.
# =============================================================================

def _load_manifest(project_dir):
    path = os.path.join(project_dir, MANIFEST_NAME)
    if not os.path.isfile(path):
        return {"name": os.path.basename(os.path.abspath(project_dir)) or "projeto-aresy",
                "dependencies": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("dependencies", {})
    return data


def _save_manifest(project_dir, data):
    path = os.path.join(project_dir, MANIFEST_NAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _pkg_name_from_url(url):
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    elif name.endswith(".ay"):
        name = name[:-3]
    return name


def _render_bar(pct, width=24):
    pct = max(0, min(100, pct))
    filled = int(width * pct / 100)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {pct:3d}%"


def _progress_line(pct, label):
    sys.stdout.write("\r" + _render_bar(pct) + f"  {label}" + " " * 10)
    sys.stdout.flush()


def _finish_progress_line(label, ok=True):
    sys.stdout.write("\r" + _render_bar(100 if ok else 0) + f"  {label}\n")
    sys.stdout.flush()


def _run_git_with_progress(args, label):
    """Roda um comando git mostrando barra de progresso de verdade, lida
    a partir da própria saída de '--progress' do git (linhas tipo
    'Receiving objects:  45% (450/1000)') — sem mostrar URL nem o output
    cru do git pro usuário."""
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, bufsize=1)
    last_pct = 0
    stderr_lines = []
    _progress_line(0, label)
    if proc.stderr is not None:
        for line in proc.stderr:
            stderr_lines.append(line)
            m = re.search(r"(\d+)%", line)
            if m:
                last_pct = int(m.group(1))
                _progress_line(last_pct, label)
    proc.wait()
    _finish_progress_line(label, ok=(proc.returncode == 0))
    return proc.returncode, "".join(stderr_lines)


def _http_get_with_progress(url, label, timeout=15):
    """Baixa um arquivo mostrando barra de progresso (percentual real,
    via Content-Length quando disponível) — sem mostrar a URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "aresy-package-manager"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total_hdr = resp.headers.get("Content-Length") if hasattr(resp, "headers") else None
            total = int(total_hdr) if total_hdr else None
            chunks = []
            read = 0
            _progress_line(0, label)
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                chunks.append(chunk)
                read += len(chunk)
                if total:
                    _progress_line(int(read * 100 / total), label)
            _finish_progress_line(label, ok=True)
            return b"".join(chunks)
    except urllib.error.HTTPError as e:
        _finish_progress_line(label, ok=False)
        raise RuntimeError(f"HTTP {e.code}")
    except urllib.error.URLError as e:
        _finish_progress_line(label, ok=False)
        raise RuntimeError(f"não consegui conectar ({e.reason})")


def _git_available():
    return shutil.which("git") is not None


def _http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "aresy-package-manager"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} ao acessar {url}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"não consegui conectar em {url} ({e.reason})")


def _looks_like_raw_file_url(url):
    """Distingue 'URL de arquivo .ay cru' (ex.: raw.githubusercontent.com/.../nome.ay)
    de 'URL de repositório git' (ex.: github.com/user/repo ou algo.git). O
    "aresy install" trata os dois de formas bem diferentes: o primeiro é um
    download HTTP direto de um arquivo; o segundo é um "git clone" de
    verdade."""
    return url.startswith("http://") or url.startswith("https://")


def _resolve_from_index(name):
    """Resolve um nome de pacote (sem URL) pesquisando no aresy-index —
    o índice central de bibliotecas da comunidade. Devolve a URL raw
    completa do arquivo .ay do pacote."""
    try:
        raw = _http_get(INDEX_URL)
    except RuntimeError as e:
        raise RuntimeError(f"não consegui acessar o índice de pacotes ({INDEX_URL}): {e}")
    try:
        index = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise RuntimeError(f"o índice de pacotes veio corrompido (JSON inválido): {e}")
    if name not in index:
        raise RuntimeError(f"pacote '{name}' não está no aresy-index (confira o nome, é sensível a maiúsculas)")
    entry = index[name]
    if _looks_like_raw_file_url(entry):
        return entry
    # caminho relativo dentro do próprio repositório aresy-index
    return f"{INDEX_REPO_RAW_BASE}/{entry.lstrip('/')}"


def _install_one_file(dest_dir, name, url):
    """Baixa um pacote de arquivo único (.ay cru) via HTTP direto — sem
    git, sem clone. É o caso comum de um pacote publicado no aresy-index."""
    try:
        data = _http_get_with_progress(url, name)
    except RuntimeError as e:
        print(f"{name}: falhou -> {e}")
        return False
    os.makedirs(dest_dir, exist_ok=True)
    entry_path = os.path.join(dest_dir, f"{name}.ay")
    try:
        with open(entry_path, "wb") as f:
            f.write(data)
    except OSError as e:
        print(f"{name}: falhou ao salvar -> {e}")
        return False
    print(f"instalado: {name}")
    return True


def _install_one(project_dir, name, url):
    dest = os.path.join(project_dir, PACKAGES_DIR, name)

    if _looks_like_raw_file_url(url) and url.endswith(".ay"):
        # é um link direto pra um arquivo .ay (o formato que o aresy-index
        # usa) — baixa o arquivo, não tenta clonar como se fosse um repo.
        return _install_one_file(dest, name, url)

    # senão, assume que é um repositório git de verdade (github.com/user/repo,
    # algo.git, etc.) — mantém o comportamento antigo pra quem publica a
    # biblioteca como um repo próprio em vez de mandar pro aresy-index.
    if not _git_available():
        print("Erro: 'git' não foi encontrado. Instala com: pkg install git")
        return False
    if os.path.isdir(os.path.join(dest, ".git")):
        rc, err = _run_git_with_progress(["git", "-C", dest, "pull", "--progress"], name)
    else:
        os.makedirs(os.path.join(project_dir, PACKAGES_DIR), exist_ok=True)
        rc, err = _run_git_with_progress(["git", "clone", "--progress", url, dest], name)
    if rc != 0:
        print(f"{name}: falhou -> {err.strip().splitlines()[-1] if err.strip() else 'erro desconhecido'}")
        return False
    entry = os.path.join(dest, f"{name}.ay")
    if not os.path.isfile(entry):
        print(f"{name}: aviso — instalado, mas não achei '{name}.ay' na raiz do pacote "
              f"(o autor deveria nomear o arquivo principal igual ao pacote)")
    else:
        print(f"instalado: {name}")
    return True


def cmd_install(args):
    project_dir = os.getcwd()
    manifest = _load_manifest(project_dir)
    if not args:
        # "aresy install" sem argumentos: instala tudo que está no manifesto
        deps = manifest["dependencies"]
        if not deps:
            print(f"Nenhuma dependência em {MANIFEST_NAME} (nada pra instalar).")
            print(f"Uso: aresy install <nome-do-pacote>          (procura no aresy-index)")
            print(f"     aresy install <url> [nome]              (git ou link .ay direto)")
            return
        ok = all(_install_one(project_dir, name, url) for name, url in deps.items())
        sys.exit(0 if ok else 1)

    first = args[0]
    if "://" in first:
        # "aresy install <url> [nome]" — URL explícita, git ou .ay cru
        url = first
        name = args[1] if len(args) > 1 else _pkg_name_from_url(url)
    else:
        # "aresy install <nome>" — sem URL, procura no índice central
        # (aresy-index), que é a forma normal de instalar hoje em dia.
        name = first
        print(f"procurando {name}...")
        try:
            url = _resolve_from_index(name)
        except RuntimeError as e:
            print(f"Erro: {e}")
            sys.exit(1)
        print(f"achou {name}")

    manifest["dependencies"][name] = url
    _save_manifest(project_dir, manifest)
    ok = _install_one(project_dir, name, url)
    sys.exit(0 if ok else 1)


def cmd_uninstall(args):
    if not args:
        print("Uso: aresy uninstall <nome>")
        sys.exit(1)
    name = args[0]
    project_dir = os.getcwd()
    manifest = _load_manifest(project_dir)
    if name in manifest["dependencies"]:
        del manifest["dependencies"][name]
        _save_manifest(project_dir, manifest)
    dest = os.path.join(project_dir, PACKAGES_DIR, name)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
        print(f"'{name}' removido.")
    else:
        print(f"'{name}' não estava instalado.")


def cmd_list(args):
    project_dir = os.getcwd()
    manifest = _load_manifest(project_dir)
    deps = manifest["dependencies"]
    if not deps:
        print("Nenhuma dependência declarada.")
        return
    for name, url in deps.items():
        dest = os.path.join(project_dir, PACKAGES_DIR, name)
        status = "instalado" if os.path.isdir(dest) else "FALTANDO (rode 'aresy install')"
        print(f"  {name}  ->  {url}  [{status}]")


class NativeError(Exception):
    pass


def compile_ir_to_binary(clang_path, ir_source, out_path, target_triple=None,
                          opt_level="-O2", extra_libs=None, use_gc=True):
    with tempfile.TemporaryDirectory() as td:
        ll_path = os.path.join(td, "prog.ll")
        with open(ll_path, "w") as f:
            f.write(ir_source)
        cmd = [clang_path, opt_level, ll_path, "-lm"]
        if use_gc:
            cmd.append("-lgc")
        for lib in (extra_libs or []):
            if lib == "m":
                continue  # -lm já foi adicionado acima
            cmd.append(f"-l{lib}")
        cmd += ["-o", out_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            msg = proc.stderr.strip() or "clang falhou ao compilar"
            if use_gc and ("-lgc" in msg or "cannot find -lgc" in msg or "libgc" in msg):
                msg += (
                    "\n\nParece que a libgc (Boehm GC) não tá instalada. "
                    "Instala com: pkg install libgc\n"
                    "(ou roda com --no-gc pra compilar sem o coletor, usando malloc puro)"
                )
            raise NativeError(msg)


def run_file_native(path, target_triple=None, use_gc=True):
    clang_path = find_clang()
    if not clang_path:
        print("clang não encontrado. Instala com: pkg install clang")
        sys.exit(1)
    with open(path) as f:
        src = f.read()
    try:
        ir, imports = compile_source(src, target_triple=target_triple, use_gc=use_gc, source_path=path)
    except (CompileError, SyntaxError) as e:
        print(f"Erro de compilação: {e}")
        sys.exit(1)
    with tempfile.TemporaryDirectory() as td:
        bin_path = os.path.join(td, "programa")
        try:
            compile_ir_to_binary(clang_path, ir, bin_path, target_triple,
                                  extra_libs=imports, use_gc=use_gc)
        except NativeError as e:
            print(f"Erro do clang:\n{e}")
            sys.exit(1)
        proc = subprocess.run([bin_path])
        if proc.returncode != 0:
            sys.exit(proc.returncode)


# ---------------------------------------------------------------------------
# 6. REPL (modo interativo — "aresy" sem argumentos, tipo digitar "python")
# ---------------------------------------------------------------------------
#
# Cada linha/bloco digitado vira um mini programa aresY, compilado com clang
# e executado de verdade (nativo, não interpretado). Funções definidas em
# rounds anteriores são reaproveitadas (o IR já gerado é reusado). Variáveis
# são "carregadas de volta" a cada round como valores literais — o processo
# anterior já terminou, então o estado precisa ser serializado e reinjetado.
#
# Limitação: arrays (array(n)) só existem dentro do bloco onde foram
# criados — o ponteiro de malloc de um processo não existe mais no próximo,
# então uma variável-array não sobrevive entre rounds do REPL. Pra usar
# arrays de verdade, escreva um arquivo .ay e rode com "aresy build".

STATE_BEGIN = "__AY_STATE_BEGIN__"
STATE_END = "__AY_STATE_END__"


def _brace_balance(text):
    """Conta chaves fora de strings/comentários pra saber se o bloco fechou."""
    depth = 0
    in_str = False
    i = 0
    while i < len(text):
        c = text[i]
        if in_str:
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "/" and i + 1 < len(text) and text[i + 1] == "/":
            break  # resto da linha é comentário
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return depth


class ReplSession:
    def __init__(self, clang_path, target_triple=None, use_gc=True):
        self.clang_path = clang_path
        self.target_triple = target_triple
        self.use_gc = use_gc
        self.codegen = CodeGen(target_triple=target_triple, use_gc=use_gc)
        self.func_ir = {}       # nome -> IR já gerado da função
        self.extern_ir = []     # linhas "declare" de funções extern registradas
        self.var_types = {}     # nome -> "i64" | "double"
        self.var_values = {}    # nome -> valor atual conhecido
        self.array_vars = set()  # variáveis que guardam array (não persistem)
        self.str_vars = set()    # variáveis do tipo string (também não persistem)
        self.opaque_vars = set()  # arrays/structs nativos não persistem entre rounds
        self._imported_ay_files = set()  # caminhos absolutos de bibliotecas .ay já importadas na sessão
        self._gc_inited = False

    def _literal(self, t, v):
        return str(int(v)) if t == "i64" else str(float(v))

    def submit(self, stmts):
        """Recebe os statements top-level de um bloco do REPL. FuncDefs só
        são registradas; o resto vira um main() compilado e rodado na hora.
        Retorna (saida_do_usuario, codigo_de_saida) ou None se não rodou
        nada (bloco só definiu função)."""
        stmts = expand_ay_imports(stmts, os.getcwd(), self._imported_ay_files)
        new_stmts = []
        for s in stmts:
            if isinstance(s, FuncDef):
                s.param_types = [
                    t if t is not None else self.codegen._infer_param_type(p, s.body)
                    for p, t in zip(s.params, s.param_types)
                ]
                ret_kind = s.ret_type if s.ret_type is not None else self.codegen._scan_return_type(s.body)
                self.codegen.functions[s.name] = {
                    "params": s.param_types,
                    "ret": ret_kind,
                    "extern": False,
                }
                self.func_ir[s.name] = self.codegen.gen_function(s)
            elif isinstance(s, StructDef):
                if s.name in self.codegen.structs:
                    raise CompileError(f"Struct '{s.name}' já foi declarada")
                self.codegen.structs[s.name] = s.fields
            elif isinstance(s, ImportDecl):
                if s.name not in self.codegen.imports:
                    self.codegen.imports.append(s.name)
            elif isinstance(s, ExternDecl):
                param_ts = [CodeGen.EXTERN_TYPE_MAP[t] for t in s.param_types]
                ret_t = CodeGen.EXTERN_TYPE_MAP[s.ret_type]
                self.codegen.functions[s.name] = {"params": param_ts, "ret": ret_t, "extern": True}
                self.extern_ir.append(
                    f"declare {ret_t} @{s.name}({', '.join(param_ts)})"
                )
            else:
                new_stmts.append(s)

        if not new_stmts:
            return None

        # eco automático: expressão solta no fim vira print (tipo REPL do python)
        if isinstance(new_stmts[-1], ExprStmt):
            new_stmts[-1] = Print(new_stmts[-1].expr)

        env = {}
        lines = []
        if self.use_gc:
            lines.append("  call void @GC_init()")

        # mesmo esquema de exceções do modo arquivo (ver gen_function):
        # precisa ser configurado aqui manualmente porque o REPL monta o
        # "main" desse round na mão, sem passar por gen_function.
        func_uid = self.codegen.new_id()
        self.codegen.func_exc_exit = f"func_exc_exit_{func_uid}"
        self.codegen.catch_stack = []
        self.codegen.loop_stack = []

        # reinjeta variáveis de rounds anteriores como literais
        for name, t in self.var_types.items():
            if name in self.array_vars:
                continue
            v = self.var_values[name]
            lines.append(f"  %{name} = alloca {t}, align 8")
            lines.append(f"  store {t} {self._literal(t, v)}, {t}* %{name}, align 8")
            env[name] = t

        newly_non_persistent = []

        # hoist (mesmo motivo do gen_function): VarDecl não gera mais seu
        # próprio alloca, então as variáveis novas deste round precisam ser
        # pré-alocadas aqui antes de qualquer statement rodar.
        locals_types = dict(env)
        self.codegen._collect_locals(new_stmts, locals_types)
        for name, t in locals_types.items():
            if name in env:
                continue  # já existe (reinjetada de round anterior)
            lt = self.codegen.llvm_type(t)
            lines.append(f"  %{name} = alloca {lt}, align 8")
            env[name] = t

        for s in new_stmts:
            if isinstance(s, VarDecl):
                if s.name in env:
                    # redeclaração vira reatribuição (o tipo já existente é mantido)
                    s = Assign(s.name, s.expr)
                else:
                    self.array_vars.discard(s.name)
                    self.str_vars.discard(s.name)
                    self.opaque_vars.discard(s.name)
                    if isinstance(s.expr, Call) and s.expr.name == "array":
                        self.array_vars.add(s.name)
                        newly_non_persistent.append(s.name)
            self.codegen.gen_stmt(s, env, lines, "i32")
            # variáveis do tipo "str" só sabemos o tipo depois de gerar o
            # statement (é o gen_stmt que preenche env[name]); então marcamos
            # aqui, olhando o tipo já resolvido.
            if isinstance(s, (VarDecl, Assign)):
                t = env.get(s.name)
                if t == "str" and s.name not in self.str_vars:
                    self.str_vars.add(s.name)
                    if s.name not in newly_non_persistent:
                        newly_non_persistent.append(s.name)
                elif is_opaque_type(t) and s.name not in self.opaque_vars:
                    self.opaque_vars.add(s.name)
                    if s.name not in newly_non_persistent:
                        newly_non_persistent.append(s.name)
                elif t == "i64" and s.name in self.array_vars:
                    pass

        # strings e arrays não sobrevivem entre rounds do REPL: strings porque
        # não temos como serializar/desserializar um ponteiro i8* de um
        # processo pro outro sem reconstituir o conteúdo, arrays pelo mesmo
        # motivo (o malloc do processo anterior já não existe mais). Excluir
        # os dois do rastreamento evita que o bug antigo aconteça de novo:
        # tentar ler a string de volta como número e ela sumir sem aviso.
        trackable = [n for n in env if n not in self.array_vars and n not in self.str_vars and n not in self.opaque_vars]
        self.codegen.gen_stmt(Print(Str('"' + STATE_BEGIN + '"')), env, lines, "i32")
        for name in trackable:
            self.codegen.gen_stmt(Print(Var(name)), env, lines, "i32")
        self.codegen.gen_stmt(Print(Str('"' + STATE_END + '"')), env, lines, "i32")

        exc_exit_block = (
            f"{self.codegen.func_exc_exit}:\n"
            f"  %excmsg_top_{func_uid} = load i8*, i8** @__ares_exc_msg\n"
            f"  %fmtp_{func_uid} = getelementptr [25 x i8], [25 x i8]* @fmt_uncaught, i32 0, i32 0\n"
            f"  call i32 (i8*, ...) @printf(i8* %fmtp_{func_uid}, i8* %excmsg_top_{func_uid})\n"
            "  call void @exit(i32 1)\n"
            "  unreachable"
        )
        body = ("define i32 @main() {\nentry:\n" + "\n".join(lines)
                + "\n  ret i32 0\n" + exc_exit_block + "\n}")

        header = ""
        if self.target_triple:
            header += f'target triple = "{self.target_triple}"\n'
        header += BUILTIN_DECLARES + FMT_CONSTANTS + EXC_GLOBALS + "\n" + "\n".join(self.extern_ir) + "\n"
        ir = (header + "\n".join(self.codegen.strings) + "\n"
              + "\n".join(self.func_ir.values()) + "\n" + body)

        with tempfile.TemporaryDirectory() as td:
            bin_path = os.path.join(td, "repl_bin")
            # -O2, igual ao modo arquivo: o custo extra de compilar com
            # otimização é irrelevante (poucos ms) comparado ao ganho em
            # blocos com loop pesado (ex.: um "while" de centenas de
            # milhões de iterações), onde -O0 deixava a execução MUITO
            # mais lenta que o binário do "aresy arquivo.ay" equivalente.
            compile_ir_to_binary(
                self.clang_path, ir, bin_path, self.target_triple,
                opt_level="-O2", extra_libs=self.codegen.imports, use_gc=self.use_gc,
            )
            proc = subprocess.run([bin_path], capture_output=True, text=True)

        out = proc.stdout
        if STATE_BEGIN in out:
            before, rest = out.split(STATE_BEGIN, 1)
            state_part = rest.split(STATE_END, 1)[0]
            state_lines = [l for l in state_part.strip("\n").split("\n") if l != ""]
        else:
            before, state_lines = out, []

        for name, line in zip(trackable, state_lines):
            t = env[name]
            try:
                self.var_values[name] = int(line) if t == "i64" else float(line)
                self.var_types[name] = t
            except ValueError:
                pass

        if newly_non_persistent:
            nomes = ", ".join(newly_non_persistent)
            before += f"(nota: {nomes} não vai persistir pra próxima linha — strings e arrays não sobrevivem entre rounds do REPL ainda; use um arquivo .ay pra isso)\n"

        return before, proc.returncode


def repl(target_triple=None, use_gc=True):
    clang_path = find_clang()
    if not clang_path:
        print("clang não encontrado. Instala com: pkg install clang")
        sys.exit(1)

    print("aresY — modo interativo (compila e roda nativo via clang)")
    if use_gc:
        print("GC (Boehm) ligado — pra desligar, sai e roda: aresy --no-gc")
    print("Ctrl+D ou Ctrl+C pra sair.\n")
    session = ReplSession(clang_path, target_triple=target_triple, use_gc=use_gc)
    buf = ""
    prompt = ">>> "
    while True:
        try:
            line = input(prompt)
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            buf = ""
            prompt = ">>> "
            continue

        buf = (buf + "\n" + line) if buf else line

        if _brace_balance(buf) > 0:
            prompt = "... "
            continue

        stripped = buf.strip()
        buf_to_run = buf
        buf = ""
        prompt = ">>> "

        if not stripped:
            continue

        try:
            tokens = tokenize(buf_to_run)
            ast = Parser(tokens).parse_program()
            result = session.submit(ast)
            if result is not None:
                out, rc = result
                if out:
                    print(out, end="" if out.endswith("\n") else "\n")
        except (CompileError, SyntaxError) as e:
            print(f"Erro de sintaxe: {e}")
        except NativeError as e:
            print(f"Erro do clang:\n{e}")


# ---------------------------------------------------------------------------
# 7. DRIVER
# ---------------------------------------------------------------------------

def compile_source(source, target_triple=None, use_gc=True, source_path=None):
    """Retorna (ir_llvm, lista_de_libs_importadas).

    source_path, quando informado, é usado como base pra resolver imports
    relativos de biblioteca .ay (ex.: import "stdlib/mathx.ay" a partir de
    onde o arquivo principal está, não do diretório em que o `aresy` foi
    chamado)."""
    tokens = tokenize(source)
    ast = Parser(tokens).parse_program()
    if source_path:
        base_dir = os.path.dirname(os.path.abspath(source_path))
        seen = {os.path.normpath(os.path.abspath(source_path))}
    else:
        base_dir = os.getcwd()
        seen = set()
    ast = expand_ay_imports(ast, base_dir, seen)
    codegen = CodeGen(target_triple=target_triple, use_gc=use_gc)
    ir = codegen.compile_program(ast)
    return ir, codegen.imports


def _build_native(argv):
    # python aresy_compiler.py build programa.ay [saida.ll] [--triple TRIPLE] [--no-gc]
    if len(argv) < 1:
        print("Uso: aresy build programa.ay [saida.ll] [--triple TRIPLE] [--no-gc]")
        sys.exit(1)
    use_gc = "--no-gc" not in argv
    argv = [a for a in argv if a != "--no-gc"]
    with open(argv[0]) as f:
        src = f.read()
    triple = None
    if "--triple" in argv:
        triple = argv[argv.index("--triple") + 1]
    out_path = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else "out.ll"
    try:
        ir, imports = compile_source(src, target_triple=triple, use_gc=use_gc, source_path=argv[0])
    except (CompileError, SyntaxError) as e:
        print(f"Erro de compilação: {e}")
        sys.exit(1)
    with open(out_path, "w") as f:
        f.write(ir)
    extra_libs = "".join(f" -l{lib}" for lib in imports if lib != "m")
    gc_flag = " -lgc" if use_gc else ""
    print(f"IR gerado em {out_path}. Compile com:\n  clang -O3 -ffast-math {out_path} -lm{gc_flag}{extra_libs} -o programa")
    if use_gc:
        print("(precisa da libgc instalada: pkg install libgc — ou use --no-gc pra compilar sem coletor)")


def _extract_triple(argv):
    triple = None
    rest = list(argv)
    if "--triple" in rest:
        i = rest.index("--triple")
        triple = rest[i + 1]
        del rest[i:i + 2]
    use_gc = "--no-gc" not in rest
    rest = [a for a in rest if a != "--no-gc"]
    return triple, use_gc, rest


def _usage():
    print(
        "Uso:\n"
        "  aresy                         entra no modo interativo (REPL, nativo via clang)\n"
        "  aresy programa.ay             compila e roda direto (nativo, sem interpretar)\n"
        "  aresy run programa.ay         mesma coisa, explícito\n"
        "  aresy build programa.ay [saida.ll] [--triple TRIPLE] [--no-gc]\n"
        "                                 gera LLVM IR pra compilar com clang na mão\n"
        "  aresy install                 instala as dependências listadas em aresy.json\n"
        "  aresy install <nome>           instala um pacote pelo nome (procura no aresy-index)\n"
        "  aresy install <url> [nome]     instala de uma URL direta (repo git ou link .ay cru)\n"
        "  aresy uninstall <nome>        remove uma dependência\n"
        "  aresy list                    lista as dependências e se estão instaladas\n"
        "  aresy --version               mostra a versão do compilador\n"
        "  aresy --help                  mostra esta ajuda\n"
        "  aresy --how                   mostra um resumo de toda a sintaxe da linguagem\n"
        "  (adicione --triple TRIPLE em qualquer comando acima se precisar\n"
        "   de um target diferente do padrão do seu aparelho)\n"
        "  (adicione --no-gc em qualquer comando acima pra compilar sem o\n"
        "   coletor de lixo — usa malloc puro, sem depender da libgc)"
    )


def _version():
    print(f"aresY {VERSION}")


def _how():
    print(HOW_TEXT)


if __name__ == "__main__":
    raw_args = sys.argv[1:]

    # --version e --how são checados antes de tudo (não fazem sentido
    # combinados com --triple/--no-gc/build/run, então nem entram no
    # parsing normal de argumentos).
    if raw_args and raw_args[0] == "--version":
        _version()
        sys.exit(0)
    if raw_args and raw_args[0] == "--how":
        _how()
        sys.exit(0)

    triple, use_gc, args = _extract_triple(raw_args)

    if len(args) == 0:
        repl(target_triple=triple, use_gc=use_gc)
    elif args[0] == "install":
        cmd_install(args[1:])
    elif args[0] == "uninstall":
        cmd_uninstall(args[1:])
    elif args[0] == "list":
        cmd_list(args[1:])
    elif args[0] == "build":
        extra = args[1:] + (["--triple", triple] if triple else []) + ([] if use_gc else ["--no-gc"])
        _build_native(extra)
    elif args[0] == "run":
        if len(args) < 2:
            _usage()
            sys.exit(1)
        run_file_native(args[1], target_triple=triple, use_gc=use_gc)
    elif args[0] in ("-h", "--help"):
        _usage()
    elif args[0] == "--version":
        _version()
    elif args[0] == "--how":
        _how()
    elif args[0].endswith(".ay"):
        run_file_native(args[0], target_triple=triple, use_gc=use_gc)
    else:
        _usage()
        sys.exit(1)
