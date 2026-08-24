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

# ---------------------------------------------------------------------------
# 1. LEXER
# ---------------------------------------------------------------------------

TOKEN_SPEC = [
    ("FLOAT",    r"\d+\.\d+(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+"),
    ("INT",      r"\d+"),
    ("STRING",   r'"[^"]*"'),
    ("ID",       r"[A-Za-z_][A-Za-z0-9_]*"),
    ("COMMENT",  r"//.*"),
    ("OP",       r"->|==|!=|<=|>=|[+\-*/%=<>(){}\[\],^&|~:]"),
    ("NEWLINE",  r"\n"),
    ("SKIP",     r"[ \t]+"),
]
MASTER_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC))
KEYWORDS = {"fn", "if", "else", "while", "return", "print", "var", "true", "false",
            "extern", "import", "try", "catch", "throw"}

# Nomes de tipo aceitos em anotações (fn e extern). Mapeiam pro vocabulário
# interno do compilador: "i64", "double", "str", "void".
TYPE_ALIASES = {
    "i64": "i64",
    "f64": "double",
    "double": "double",
    "str": "str",
    "string": "str",
    "void": "void",
}


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
    def __init__(self, value): self.value = value[1:-1]
class Bool:
    def __init__(self, value): self.value = value
class Var:
    def __init__(self, name): self.name = name
class VarDecl:
    def __init__(self, name, expr): self.name, self.expr = name, expr
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
        # tipagem unificada: cada parâmetro tem um tipo real (i64/double/str),
        # não mais travado em i64. Sem anotação -> i64 (compatível com código
        # antigo). ret_type é None quando não anotado (mantém a inferência
        # antiga por varredura do corpo, via _scan_return_type).
        self.param_types = param_types if param_types is not None else ["i64"] * len(params)
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
class TryCatch:
    def __init__(self, try_body, catch_var, catch_body):
        self.try_body, self.catch_var, self.catch_body = try_body, catch_var, catch_body
class Throw:
    def __init__(self, expr): self.expr = expr


# ---------------------------------------------------------------------------
# 3. PARSER
# ---------------------------------------------------------------------------

class Parser:
    def __init__(self, tokens):
        self.tokens, self.pos = tokens, 0

    def peek(self, offset=0): return self.tokens[self.pos + offset]
    def advance(self):
        t = self.tokens[self.pos]; self.pos += 1; return t
    def expect(self, kind):
        t = self.advance()
        if t.kind != kind:
            raise SyntaxError(f"Esperado {kind}, veio {t.kind} ({t.value})")
        return t

    def parse_program(self):
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

    EXTERN_TYPES = {"i64", "f64", "void"}

    def parse_statement(self):
        tok = self.peek()
        if tok.kind == "IMPORT":
            self.advance()
            lib = self.expect("STRING").value[1:-1]
            return ImportDecl(lib)
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
        if tok.kind == "TRY": return self.parse_try()
        if tok.kind == "THROW":
            self.advance()
            return Throw(self.parse_expr())
        if tok.kind == "VAR":
            self.advance()
            name = self.expect("ID").value
            self.expect("OP")  # =
            expr = self.parse_expr()
            return VarDecl(name, expr)
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
        if tok.kind == "ID" and self.peek(1).value == "=":
            name = self.advance().value
            self.advance()
            return Assign(name, self.parse_expr())
        if tok.kind == "ID" and self.peek(1).value == "[":
            name = self.advance().value
            indices = []
            while self.peek().value == "[":
                self.advance()  # [
                indices.append(self.parse_expr())
                self.expect("OP")  # ]
            base = Var(name)
            if self.peek().value == "=":
                self.advance()  # =
                expr = self.parse_expr()
                target = base
                for idx in indices[:-1]:
                    target = IndexGet(target, idx)
                return IndexSet(target, indices[-1], expr)
            node = base
            for idx in indices:
                node = IndexGet(node, idx)
            return ExprStmt(node)
        return ExprStmt(self.parse_expr())

    def parse_funcdef(self):
        self.advance()
        name = self.expect("ID").value
        self.expect("OP")  # (
        params = []
        param_types = []
        while self.peek().value != ")":
            pname = self.expect("ID").value
            ptype = "i64"
            if self.peek().value == ":":
                self.advance()
                traw = self.expect("ID").value
                ptype = resolve_type_name(traw)
            params.append(pname)
            param_types.append(ptype)
            if self.peek().value == ",": self.advance()
        self.expect("OP")  # )
        ret_type = None
        if self.peek().value == "->":
            self.advance()
            traw = self.expect("ID").value
            ret_type = resolve_type_name(traw)
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
            if self.peek().value == "(":
                self.advance()
                args = []
                while self.peek().value != ")":
                    args.append(self.parse_expr())
                    if self.peek().value == ",": self.advance()
                self.expect("OP")
                return Call(name, args)
            node = Var(name)
            while self.peek().value == "[":
                self.advance()
                idx = self.parse_expr()
                self.expect("OP")
                node = IndexGet(node, idx)
            return node
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


class CodeGen:
    def __init__(self, target_triple=None, use_gc=True):
        self.target_triple = target_triple
        self.use_gc = use_gc
        self.counter = 0
        self.strings = []
        self.functions = {}   # name -> {'params': [...], 'ret': 'i64'|'double'|'void', 'extern': bool}
        self.imports = []     # nomes de libs de "import" (viram -lNOME na hora de linkar)
        self.catch_stack = []      # labels dos catch ativos (mais interno primeiro), por função
        self.func_exc_exit = None  # label pra onde pular se uma exceção escapar de todo try da função atual

    def new_id(self):
        self.counter += 1
        return self.counter

    def llvm_type(self, t):
        # "str" é rastreado internamente como tipo próprio, mas em LLVM
        # é sempre um ponteiro i8* (C string terminada em \0).
        return "i8*" if t == "str" else t

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
        walk(body)
        return found["type"]

    def _guess_type(self, node):
        # heurística leve só pra declarar o cabeçalho da função no LLVM
        # quando NÃO há anotação explícita de retorno ('-> tipo'); o valor
        # real de retorno é convertido (cast) se necessário no codegen.
        if isinstance(node, Num): return "double" if node.is_float else "i64"
        if isinstance(node, Str): return "str"
        if isinstance(node, Call) and node.name in ("sqrt", "time"): return "double"
        if isinstance(node, BinOp): return self._guess_type(node.left)
        return "i64"

    EXTERN_TYPE_MAP = {"i64": "i64", "f64": "double", "void": "void"}

    def compile_program(self, stmts):
        funcdefs = [s for s in stmts if isinstance(s, FuncDef)]
        externs = [s for s in stmts if isinstance(s, ExternDecl)]
        imports = [s for s in stmts if isinstance(s, ImportDecl)]
        if not any(f.name == "main" for f in funcdefs):
            raise CompileError("Programa precisa de uma função main()")

        self.imports = [i.name for i in imports]

        extern_ir = []
        for e in externs:
            if e.name in self.functions:
                raise CompileError(f"'{e.name}' já foi declarada (extern duplicado ou conflito com fn)")
            param_ts = [self.EXTERN_TYPE_MAP[t] for t in e.param_types]
            ret_t = self.EXTERN_TYPE_MAP[e.ret_type]
            self.functions[e.name] = {"params": param_ts, "ret": ret_t, "extern": True}
            llvm_ret = "void" if ret_t == "void" else ret_t
            extern_ir.append(f"declare {llvm_ret} @{e.name}({', '.join(param_ts)})")

        for f in funcdefs:
            if f.name in self.functions:
                raise CompileError(f"'{f.name}' já foi declarada (conflito com extern)")
            # "params" agora guarda os TIPOS reais de cada parâmetro (unificado
            # com extern, que já funcionava assim). "ret" usa a anotação
            # explícita ('-> tipo') se houver; senão cai na heurística antiga
            # (varre os returns do corpo tentando adivinhar).
            ret_kind = f.ret_type if f.ret_type is not None else self._scan_return_type(f.body)
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
            env[node.name] = t
            lt = self.llvm_type(t)
            lines.append(f"  %{node.name} = alloca {lt}, align 8")
            lines.append(f"  store {lt} {v}, {lt}* %{node.name}, align 8")

        elif isinstance(node, Assign):
            if node.name not in env:
                raise CompileError(f"Variável '{node.name}' não declarada — use 'var {node.name} = ...' primeiro")
            target_t = env[node.name]
            t, v = self.gen_expr(node.expr, env, lines)
            if (target_t == "str") != (t == "str"):
                raise CompileError(
                    f"Tipo incompatível ao atribuir a '{node.name}' (era {target_t}, veio {t}) — "
                    "strings e números não se misturam automaticamente"
                )
            v = self.cast(lines, t, v, target_t)
            lt = self.llvm_type(target_t)
            lines.append(f"  store {lt} {v}, {lt}* %{node.name}, align 8")

        elif isinstance(node, IndexSet):
            _, iv = self.gen_expr(node.idx, env, lines)
            t, v = self.gen_expr(node.expr, env, lines)
            v = self.cast(lines, t, v, "i64")
            at, av = self.gen_expr(node.arr, env, lines)
            if at != "i64":
                raise CompileError("Indexação (escrita com []) só é suportada em arrays")
            uid = self.new_id()
            lines.append(f"  %ap_{uid} = inttoptr i64 {av} to i64*")
            lines.append(f"  %ep_{uid} = getelementptr i64, i64* %ap_{uid}, i64 {iv}")
            lines.append(f"  store i64 {v}, i64* %ep_{uid}, align 8")

        elif isinstance(node, Print):
            if isinstance(node.expr, Str):
                uid = self.new_id()
                text = node.expr.value
                byte_len = len(text.encode("utf-8")) + 2
                self.strings.append(
                    f'@.str.{uid} = private unnamed_addr constant [{byte_len} x i8] c"{text}\\0A\\00"'
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
                else:
                    lines.append(f"  %pf_{uid} = getelementptr [5 x i8], [5 x i8]* @fmt_int, i32 0, i32 0")
                    lines.append(f"  call i32 (i8*, ...) @printf(i8* %pf_{uid}, {t} {v})")

        elif isinstance(node, If):
            uid = self.new_id()
            cond_t, cond_v = self.gen_expr(node.cond, env, lines)
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
            lines.append(f"  br label %c_{uid}")
            lines.append(f"c_{uid}:")
            cond_t, cond_v = self.gen_expr(node.cond, env, lines)
            lines.append(f"  br i1 {cond_v}, label %bt_{uid}, label %be_{uid}")
            lines.append(f"bt_{uid}:")
            for s in node.body: self.gen_stmt(s, env, lines, func_ret_type)
            lines.append(f"  br label %c_{uid}")
            lines.append(f"be_{uid}:")

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
            lines.append(f"  %{node.catch_var} = alloca i8*, align 8")
            lines.append(f"  %excmsg_{uid} = load i8*, i8** @__ares_exc_msg")
            lines.append(f"  store i8* %excmsg_{uid}, i8** %{node.catch_var}, align 8")
            env[node.catch_var] = "str"
            for s in node.catch_body:
                self.gen_stmt(s, env, lines, func_ret_type)
            lines.append(f"  br label %{end_label}")
            lines.append(f"{end_label}:")

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
                    if t != "str":
                        raise CompileError(
                            "Função declarada retornando 'str' (ou inferida assim), "
                            f"mas o valor retornado é do tipo '{t}'"
                        )
                elif t == "str":
                    raise CompileError(
                        "Não é possível retornar uma string de uma função que não "
                        "declara retorno 'str' — anota a função com '-> str'"
                    )
                else:
                    v = self.cast(lines, t, v, func_ret_type)
                lines.append(f"  ret {func_ret_type} {v}")
            uid = self.new_id()
            lines.append(f"unreachable_{uid}:")  # bloco morto p/ manter blocos válidos após ret

        elif isinstance(node, ExprStmt):
            self.gen_expr(node.expr, env, lines)

        else:
            raise CompileError(f"Statement não suportado: {node}")

    def gen_expr(self, node, env, lines):
        uid = self.new_id()

        if isinstance(node, Num):
            return ("double", fmt_double_literal(node.value)) if node.is_float else ("i64", str(int(node.value)))

        if isinstance(node, Str):
            text = node.value
            byte_len = len(text.encode("utf-8")) + 1
            self.strings.append(
                f'@.str.{uid} = private unnamed_addr constant [{byte_len} x i8] c"{text}\\00"'
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
                    return "i64", f"%cmp_{uid}"
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
                instr = {"&": "and", "|": "or", "^": "xor"}[node.op]
                lines.append(f"  %tmp_{uid} = {instr} i64 {v1}, {v2}")
                return "i64", f"%tmp_{uid}"

            if is_float:
                instr = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv"}.get(node.op)
                if instr is None:
                    raise CompileError("'%' (módulo) não é suportado com float")
                lines.append(f"  %tmp_{uid} = {instr} double {v1}, {v2}")
                return "double", f"%tmp_{uid}"
            else:
                instr = {"+": "add nsw", "-": "sub nsw", "*": "mul nsw", "/": "sdiv", "%": "srem"}[node.op]
                lines.append(f"  %tmp_{uid} = {instr} i64 {v1}, {v2}")
                return "i64", f"%tmp_{uid}"

        if isinstance(node, IndexGet):
            at, av = self.gen_expr(node.arr, env, lines)
            if at != "i64":
                raise CompileError("Indexação com [] só é suportada em arrays")
            _, iv = self.gen_expr(node.idx, env, lines)
            lines.append(f"  %ap_{uid} = inttoptr i64 {av} to i64*")
            lines.append(f"  %ep_{uid} = getelementptr i64, i64* %ap_{uid}, i64 {iv}")
            lines.append(f"  %ev_{uid} = load i64, i64* %ep_{uid}, align 8")
            return "i64", f"%ev_{uid}"

        if isinstance(node, Call):
            return self.gen_call(node, env, lines, uid)

        raise CompileError(f"Expressão não suportada: {node}")

    def gen_call(self, node, env, lines, uid):
        name = node.name
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

        if name == "random":
            t, mv = self.gen_expr(node.args[0], env, lines)
            mv = self.cast(lines, t, mv, "i64")
            lines.append(f"  %ri_{uid} = call i32 @rand()")
            lines.append(f"  %r6_{uid} = sext i32 %ri_{uid} to i64")
            lines.append(f"  %rc_{uid} = sdiv i64 %r6_{uid}, 256")
            lines.append(f"  %rr_{uid} = srem i64 %rc_{uid}, {mv}")
            return "i64", f"%rr_{uid}"

        # --- Strings avançadas ---

        if name == "len":
            t, sv = self.gen_expr(node.args[0], env, lines)
            if t != "str":
                raise CompileError("'len' espera uma string (pra tamanho de array, guarda o tamanho numa variável à parte)")
            lines.append(f"  %ln_{uid} = call i64 @strlen(i8* {sv})")
            return "i64", f"%ln_{uid}"

        if name == "str":
            t, v = self.gen_expr(node.args[0], env, lines)
            return "str", self.to_str(lines, t, v)

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
            if param_t == "str" or t == "str":
                if t != param_t:
                    raise CompileError(
                        f"'{name}': argumento {i + 1} esperado do tipo '{param_t}', recebeu '{t}'"
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


def find_clang():
    for candidate in ("clang", "clang-19", "clang-18", "clang-17", "clang-16"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


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
        ir, imports = compile_source(src, target_triple=target_triple, use_gc=use_gc)
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
        self._gc_inited = False

    def _literal(self, t, v):
        return str(int(v)) if t == "i64" else str(float(v))

    def submit(self, stmts):
        """Recebe os statements top-level de um bloco do REPL. FuncDefs só
        são registradas; o resto vira um main() compilado e rodado na hora.
        Retorna (saida_do_usuario, codigo_de_saida) ou None se não rodou
        nada (bloco só definiu função)."""
        new_stmts = []
        for s in stmts:
            if isinstance(s, FuncDef):
                ret_kind = s.ret_type if s.ret_type is not None else self.codegen._scan_return_type(s.body)
                self.codegen.functions[s.name] = {
                    "params": s.param_types,
                    "ret": ret_kind,
                    "extern": False,
                }
                self.func_ir[s.name] = self.codegen.gen_function(s)
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

        # reinjeta variáveis de rounds anteriores como literais
        for name, t in self.var_types.items():
            if name in self.array_vars:
                continue
            v = self.var_values[name]
            lines.append(f"  %{name} = alloca {t}, align 8")
            lines.append(f"  store {t} {self._literal(t, v)}, {t}* %{name}, align 8")
            env[name] = t

        newly_non_persistent = []
        for s in new_stmts:
            if isinstance(s, VarDecl):
                if s.name in env:
                    # redeclaração vira reatribuição (o tipo já existente é mantido)
                    s = Assign(s.name, s.expr)
                else:
                    self.array_vars.discard(s.name)
                    self.str_vars.discard(s.name)
                    if isinstance(s.expr, Call) and s.expr.name == "array":
                        self.array_vars.add(s.name)
                        newly_non_persistent.append(s.name)
            self.codegen.gen_stmt(s, env, lines, "i32")
            # variáveis do tipo "str" só sabemos o tipo depois de gerar o
            # statement (é o gen_stmt que preenche env[name]); então marcamos
            # aqui, olhando o tipo já resolvido.
            if isinstance(s, (VarDecl, Assign)) and env.get(s.name) == "str" and s.name not in self.str_vars:
                self.str_vars.add(s.name)
                if s.name not in newly_non_persistent:
                    newly_non_persistent.append(s.name)

        # strings e arrays não sobrevivem entre rounds do REPL: strings porque
        # não temos como serializar/desserializar um ponteiro i8* de um
        # processo pro outro sem reconstituir o conteúdo, arrays pelo mesmo
        # motivo (o malloc do processo anterior já não existe mais). Excluir
        # os dois do rastreamento evita que o bug antigo aconteça de novo:
        # tentar ler a string de volta como número e ela sumir sem aviso.
        trackable = [n for n in env if n not in self.array_vars and n not in self.str_vars]
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

def compile_source(source, target_triple=None, use_gc=True):
    """Retorna (ir_llvm, lista_de_libs_importadas)."""
    tokens = tokenize(source)
    ast = Parser(tokens).parse_program()
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
        ir, imports = compile_source(src, target_triple=triple, use_gc=use_gc)
    except (CompileError, SyntaxError) as e:
        print(f"Erro de compilação: {e}")
        sys.exit(1)
    with open(out_path, "w") as f:
        f.write(ir)
    extra_libs = "".join(f" -l{lib}" for lib in imports)
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
        "  (adicione --triple TRIPLE em qualquer comando acima se precisar\n"
        "   de um target diferente do padrão do seu aparelho)\n"
        "  (adicione --no-gc em qualquer comando acima pra compilar sem o\n"
        "   coletor de lixo — usa malloc puro, sem depender da libgc)"
    )


if __name__ == "__main__":
    triple, use_gc, args = _extract_triple(sys.argv[1:])

    if len(args) == 0:
        repl(target_triple=triple, use_gc=use_gc)
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
    elif args[0].endswith(".ay"):
        run_file_native(args[0], target_triple=triple, use_gc=use_gc)
    else:
        _usage()
        sys.exit(1)
