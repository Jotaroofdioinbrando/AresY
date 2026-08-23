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

# ---------------------------------------------------------------------------
# 1. LEXER
# ---------------------------------------------------------------------------

TOKEN_SPEC = [
    ("FLOAT",    r"\d+\.\d+"),
    ("INT",      r"\d+"),
    ("STRING",   r'"[^"]*"'),
    ("ID",       r"[A-Za-z_][A-Za-z0-9_]*"),
    ("OP",       r"==|!=|<=|>=|[+\-*/%=<>(){}\[\],]"),
    ("NEWLINE",  r"\n"),
    ("SKIP",     r"[ \t]+"),
    ("COMMENT",  r"//.*"),
]
MASTER_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC))
KEYWORDS = {"fn", "if", "else", "while", "return", "print", "var", "true", "false"}


class Token:
    def __init__(self, kind, value):
        self.kind, self.value = kind, value
    def __repr__(self):
        return f"{self.kind}:{self.value}"


def tokenize(code):
    tokens = []
    for m in MASTER_RE.finditer(code):
        kind, value = m.lastgroup, m.group()
        if kind in ("SKIP", "COMMENT", "NEWLINE"):
            continue
        if kind == "ID" and value in KEYWORDS:
            kind = value.upper()
        tokens.append(Token(kind, value))
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
    def __init__(self, name, params, body): self.name, self.params, self.body = name, params, body
class Return:
    def __init__(self, expr): self.expr = expr
class ExprStmt:
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

    def parse_statement(self):
        tok = self.peek()
        if tok.kind == "FN": return self.parse_funcdef()
        if tok.kind == "IF": return self.parse_if()
        if tok.kind == "WHILE": return self.parse_while()
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
            self.advance()  # [
            idx = self.parse_expr()
            self.expect("OP")  # ]
            if self.peek().value == "=":
                self.advance()  # =
                expr = self.parse_expr()
                return IndexSet(name, idx, expr)
            return ExprStmt(IndexGet(name, idx))
        return ExprStmt(self.parse_expr())

    def parse_funcdef(self):
        self.advance()
        name = self.expect("ID").value
        self.expect("OP")
        params = []
        while self.peek().value != ")":
            params.append(self.expect("ID").value)
            if self.peek().value == ",": self.advance()
        self.expect("OP")
        body = self.parse_block()
        return FuncDef(name, params, body)

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

    def parse_expr(self): return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_add_sub()
        while self.peek().value in ("==", "!=", "<", ">", "<=", ">="):
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
            if self.peek().value == "[":
                self.advance()
                idx = self.parse_expr()
                self.expect("OP")
                return IndexGet(name, idx)
            return Var(name)
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
)
FMT_CONSTANTS = (
    '@fmt_int = private unnamed_addr constant [5 x i8] c"%ld\\0A\\00"\n'
    '@fmt_float = private unnamed_addr constant [4 x i8] c"%f\\0A\\00"\n'
    '@fmt_scan = private unnamed_addr constant [4 x i8] c"%ld\\00"\n'
)

class CompileError(Exception):
    pass


class CodeGen:
    def __init__(self, target_triple=None):
        self.target_triple = target_triple
        self.counter = 0
        self.strings = []
        self.functions = {}   # name -> {'params': [...], 'ret': 'i64'|'double'|'void'}

    def new_id(self):
        self.counter += 1
        return self.counter

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
        # heurística leve só pra declarar o cabeçalho da função no LLVM;
        # o valor real de retorno é convertido (cast) se necessário no codegen.
        if isinstance(node, Num): return "double" if node.is_float else "i64"
        if isinstance(node, Call) and node.name in ("sqrt", "time"): return "double"
        if isinstance(node, BinOp): return self._guess_type(node.left)
        return "i64"

    def compile_program(self, stmts):
        funcdefs = [s for s in stmts if isinstance(s, FuncDef)]
        if not any(f.name == "main" for f in funcdefs):
            raise CompileError("Programa precisa de uma função main()")

        for f in funcdefs:
            self.functions[f.name] = {"params": f.params, "ret": self._scan_return_type(f.body)}

        body_ir = []
        for f in funcdefs:
            body_ir.append(self.gen_function(f))

        header = ""
        if self.target_triple:
            header += f'target triple = "{self.target_triple}"\n'
        header += BUILTIN_DECLARES + FMT_CONSTANTS + "\n"
        return header + "\n".join(self.strings) + "\n" + "\n".join(body_ir)

    def gen_function(self, node):
        env = {}
        lines = []
        is_main = node.name == "main"
        ret_kind = self.functions[node.name]["ret"]
        llvm_ret = "i32" if is_main else {"void": "void", "i64": "i64", "double": "double"}[ret_kind]

        params_sig = ", ".join(f"i64 %arg_{i}" for i in range(len(node.params)))
        lines.append(f"define {llvm_ret} @{node.name}({params_sig}) {{")
        lines.append("entry:")

        if is_main:
            uid = self.new_id()
            lines.append(f"  %st_tv_{uid} = alloca [16 x i8], align 8")
            lines.append(f"  %st_tp_{uid} = getelementptr [16 x i8], [16 x i8]* %st_tv_{uid}, i32 0, i32 0")
            lines.append(f"  call i32 @gettimeofday(i8* %st_tp_{uid}, i8* null)")
            lines.append(f"  %st_up_{uid} = getelementptr i8, i8* %st_tp_{uid}, i32 8")
            lines.append(f"  %st_up6_{uid} = bitcast i8* %st_up_{uid} to i64*")
            lines.append(f"  %st_uv_{uid} = load i64, i64* %st_up6_{uid}")
            lines.append(f"  %seed_{uid} = trunc i64 %st_uv_{uid} to i32")
            lines.append(f"  call void @srand(i32 %seed_{uid})")

        for i, p in enumerate(node.params):
            env[p] = "i64"
            lines.append(f"  %{p} = alloca i64, align 8")
            lines.append(f"  store i64 %arg_{i}, i64* %{p}, align 8")

        for s in node.body:
            self.gen_stmt(s, env, lines, llvm_ret)

        # terminador padrão caso o corpo não termine com return explícito
        if llvm_ret == "void":
            lines.append("  ret void")
        elif llvm_ret == "i32":
            lines.append("  ret i32 0")
        elif llvm_ret == "double":
            lines.append("  ret double 0.0")
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

    def gen_stmt(self, node, env, lines, func_ret_type):
        if isinstance(node, VarDecl):
            t, v = self.gen_expr(node.expr, env, lines)
            env[node.name] = t
            lines.append(f"  %{node.name} = alloca {t}, align 8")
            lines.append(f"  store {t} {v}, {t}* %{node.name}, align 8")

        elif isinstance(node, Assign):
            if node.name not in env:
                raise CompileError(f"Variável '{node.name}' não declarada — use 'var {node.name} = ...' primeiro")
            target_t = env[node.name]
            t, v = self.gen_expr(node.expr, env, lines)
            v = self.cast(lines, t, v, target_t)
            lines.append(f"  store {target_t} {v}, {target_t}* %{node.name}, align 8")

        elif isinstance(node, IndexSet):
            _, iv = self.gen_expr(node.idx, env, lines)
            t, v = self.gen_expr(node.expr, env, lines)
            v = self.cast(lines, t, v, "i64")
            uid = self.new_id()
            lines.append(f"  %ai_{uid} = load i64, i64* %{node.arr}, align 8")
            lines.append(f"  %ap_{uid} = inttoptr i64 %ai_{uid} to i64*")
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

        elif isinstance(node, Return):
            if node.expr is None:
                lines.append("  ret void" if func_ret_type == "void" else f"  ret {func_ret_type} 0")
            else:
                t, v = self.gen_expr(node.expr, env, lines)
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
            return ("double", f"{float(node.value)}") if node.is_float else ("i64", str(int(node.value)))

        if isinstance(node, Bool):
            return ("i64", "1" if node.value else "0")

        if isinstance(node, Var):
            if node.name not in env:
                raise CompileError(f"Variável '{node.name}' usada antes de declarar")
            t = env[node.name]
            lines.append(f"  %reg_{uid} = load {t}, {t}* %{node.name}, align 8")
            return t, f"%reg_{uid}"

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
            _, iv = self.gen_expr(node.idx, env, lines)
            lines.append(f"  %ai_{uid} = load i64, i64* %{node.arr}, align 8")
            lines.append(f"  %ap_{uid} = inttoptr i64 %ai_{uid} to i64*")
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
            lines.append(f"  %mr_{uid} = call i8* @malloc(i64 %bt_{uid})")
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

        if name not in self.functions:
            raise CompileError(f"Função '{name}' não existe")
        sig = self.functions[name]
        if len(sig["params"]) != len(node.args):
            raise CompileError(f"'{name}' espera {len(sig['params'])} argumento(s), recebeu {len(node.args)}")
        arg_strs = []
        for a in node.args:
            t, v = self.gen_expr(a, env, lines)
            v = self.cast(lines, t, v, "i64")
            arg_strs.append(f"i64 {v}")
        ret_t = sig["ret"]
        if ret_t == "void":
            lines.append(f"  call void @{name}({', '.join(arg_strs)})")
            return "i64", "0"
        lines.append(f"  %call_{uid} = call {ret_t} @{name}({', '.join(arg_strs)})")
        return ret_t, f"%call_{uid}"


# ---------------------------------------------------------------------------
# 5. INTERPRETADOR (modo dinâmico — sem LLVM/clang, roda direto em Python)
# ---------------------------------------------------------------------------
#
# Esse modo não gera IR nem binário: ele anda pela AST e executa na hora.
# É o que dá suporte ao "python arquivo.ay" e ao REPL interativo (aresy sem
# argumentos, tipo digitar "python" no Termux). Variáveis aqui não têm tipo
# fixo (i64/double deixam de existir — é tudo número/bool/lista/string do
# Python por baixo dos panos), então isso é mais permissivo que o compilador:
# coisas como "1 + 2.0" ou passar float pra função funcionam sem reclamar.

import math
import random as _random
import time as _time


class AresyRuntimeError(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, value): self.value = value


class Interpreter:
    def __init__(self):
        self.functions = {}   # nome -> FuncDef
        self.globals = {}     # variáveis do escopo top-level (persistem no REPL)

    def run_program(self, stmts):
        """Executa uma lista de statements no escopo global (usado no REPL,
        um bloco por vez, e também pra rodar um arquivo inteiro)."""
        result = None
        for s in stmts:
            if isinstance(s, FuncDef):
                self.functions[s.name] = s
                result = None
            else:
                result = self.exec_stmt(s, self.globals)
        return result

    def run_file(self, stmts):
        """Registra as funções e chama main(), como o binário compilado faz."""
        for s in stmts:
            if isinstance(s, FuncDef):
                self.functions[s.name] = s
        if "main" not in self.functions:
            raise AresyRuntimeError("Programa precisa de uma função main()")
        try:
            self.call_function("main", [])
        except ReturnSignal:
            pass

    def call_function(self, name, args):
        if name not in self.functions:
            raise AresyRuntimeError(f"Função '{name}' não existe")
        fn = self.functions[name]
        if len(fn.params) != len(args):
            raise AresyRuntimeError(
                f"'{name}' espera {len(fn.params)} argumento(s), recebeu {len(args)}")
        scope = dict(zip(fn.params, args))
        try:
            for s in fn.body:
                self.exec_stmt(s, scope)
        except ReturnSignal as r:
            return r.value
        return 0

    # ---- statements ----
    def exec_stmt(self, node, scope):
        if isinstance(node, VarDecl):
            scope[node.name] = self.eval_expr(node.expr, scope)
            return None

        if isinstance(node, Assign):
            if node.name not in scope:
                raise AresyRuntimeError(
                    f"Variável '{node.name}' não declarada — use 'var {node.name} = ...' primeiro")
            scope[node.name] = self.eval_expr(node.expr, scope)
            return None

        if isinstance(node, IndexSet):
            arr = self._get_array(node.arr, scope)
            idx = int(self.eval_expr(node.idx, scope))
            self._check_bounds(arr, idx, node.arr)
            arr[idx] = self.eval_expr(node.expr, scope)
            return None

        if isinstance(node, Print):
            if isinstance(node.expr, Str):
                print(node.expr.value)
            else:
                v = self.eval_expr(node.expr, scope)
                print(self._fmt(v))
            return None

        if isinstance(node, If):
            if self._truthy(self.eval_expr(node.cond, scope)):
                for s in node.then_b: self.exec_stmt(s, scope)
            else:
                for s in node.else_b: self.exec_stmt(s, scope)
            return None

        if isinstance(node, While):
            while self._truthy(self.eval_expr(node.cond, scope)):
                for s in node.body: self.exec_stmt(s, scope)
            return None

        if isinstance(node, Return):
            v = self.eval_expr(node.expr, scope) if node.expr is not None else 0
            raise ReturnSignal(v)

        if isinstance(node, ExprStmt):
            return self.eval_expr(node.expr, scope)

        raise AresyRuntimeError(f"Statement não suportado no interpretador: {node}")

    # ---- expressions ----
    def eval_expr(self, node, scope):
        if isinstance(node, Num):
            return node.value
        if isinstance(node, Bool):
            return node.value
        if isinstance(node, Str):
            return node.value
        if isinstance(node, Var):
            if node.name not in scope:
                raise AresyRuntimeError(f"Variável '{node.name}' usada antes de declarar")
            return scope[node.name]
        if isinstance(node, UnaryOp):
            v = self.eval_expr(node.operand, scope)
            return -v
        if isinstance(node, BinOp):
            l = self.eval_expr(node.left, scope)
            r = self.eval_expr(node.right, scope)
            return self._binop(node.op, l, r)
        if isinstance(node, IndexGet):
            arr = self._get_array(node.arr, scope)
            idx = int(self.eval_expr(node.idx, scope))
            self._check_bounds(arr, idx, node.arr)
            return arr[idx]
        if isinstance(node, Call):
            return self._call(node, scope)
        raise AresyRuntimeError(f"Expressão não suportada no interpretador: {node}")

    def _get_array(self, name, scope):
        if name not in scope:
            raise AresyRuntimeError(f"Variável '{name}' usada antes de declarar")
        v = scope[name]
        if not isinstance(v, list):
            raise AresyRuntimeError(f"'{name}' não é um array")
        return v

    def _check_bounds(self, arr, idx, name):
        if idx < 0 or idx >= len(arr):
            raise AresyRuntimeError(
                f"Índice {idx} fora dos limites de '{name}' (tamanho {len(arr)})")

    def _binop(self, op, l, r):
        if op == "+": return l + r
        if op == "-": return l - r
        if op == "*": return l * r
        if op == "/":
            if isinstance(l, float) or isinstance(r, float):
                return l / r
            if r == 0:
                raise AresyRuntimeError("Divisão por zero")
            # divisão inteira truncada em direção a zero, igual ao sdiv do LLVM
            q = abs(l) // abs(r)
            return q if (l < 0) == (r < 0) else -q
        if op == "%":
            if isinstance(l, float) or isinstance(r, float):
                raise AresyRuntimeError("'%' (módulo) não é suportado com float")
            if r == 0:
                raise AresyRuntimeError("Módulo por zero")
            rem = abs(l) % abs(r)
            return rem if l >= 0 else -rem
        if op == "==": return l == r
        if op == "!=": return l != r
        if op == "<": return l < r
        if op == ">": return l > r
        if op == "<=": return l <= r
        if op == ">=": return l >= r
        raise AresyRuntimeError(f"Operador não suportado: {op}")

    def _truthy(self, v):
        return bool(v)

    def _fmt(self, v):
        if isinstance(v, bool):
            return "1" if v else "0"
        if isinstance(v, float):
            return f"{v:.6f}"
        return str(v)

    def _call(self, node, scope):
        name = node.name
        if name == "sqrt":
            return math.sqrt(self.eval_expr(node.args[0], scope))
        if name == "time":
            return _time.time()
        if name == "random":
            n = int(self.eval_expr(node.args[0], scope))
            if n <= 0:
                raise AresyRuntimeError("random(n) precisa de n > 0")
            return _random.randrange(n)
        if name == "array":
            n = int(self.eval_expr(node.args[0], scope))
            return [0] * n
        if name == "input":
            raw = input()
            try:
                return int(raw)
            except ValueError:
                try:
                    return float(raw)
                except ValueError:
                    return raw
        args = [self.eval_expr(a, scope) for a in node.args]
        return self.call_function(name, args)


def interpret_source(source, interpreter=None):
    """Interpreta um programa completo (precisa ter main())."""
    tokens = tokenize(source)
    ast = Parser(tokens).parse_program()
    interp = interpreter or Interpreter()
    interp.run_file(ast)
    return interp


# ---------------------------------------------------------------------------
# 6. REPL (modo interativo — "aresy" sem argumentos, tipo digitar "python")
# ---------------------------------------------------------------------------

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


def repl():
    print("aresY — modo interativo (dinâmico, sem compilar pra binário)")
    print("Ctrl+D ou Ctrl+C pra sair.\n")
    interp = Interpreter()
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
            result = interp.run_program(ast)
            if result is not None:
                print(interp._fmt(result))
        except (CompileError, SyntaxError) as e:
            print(f"Erro de sintaxe: {e}")
        except AresyRuntimeError as e:
            print(f"Erro: {e}")
        except ZeroDivisionError:
            print("Erro: divisão por zero")


# ---------------------------------------------------------------------------
# 7. DRIVER
# ---------------------------------------------------------------------------

def compile_source(source, target_triple=None):
    tokens = tokenize(source)
    ast = Parser(tokens).parse_program()
    return CodeGen(target_triple=target_triple).compile_program(ast)


def _run_file_dynamic(path):
    with open(path) as f:
        src = f.read()
    try:
        interpret_source(src)
    except (CompileError, SyntaxError) as e:
        print(f"Erro de sintaxe: {e}")
        sys.exit(1)
    except AresyRuntimeError as e:
        print(f"Erro: {e}")
        sys.exit(1)


def _build_native(argv):
    # uso antigo: python aresy_compiler.py build programa.ay [saida.ll] [--triple TRIPLE]
    if len(argv) < 1:
        print("Uso: aresy build programa.ay [saida.ll] [--triple TRIPLE]")
        sys.exit(1)
    with open(argv[0]) as f:
        src = f.read()
    triple = None
    if "--triple" in argv:
        triple = argv[argv.index("--triple") + 1]
    out_path = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else "out.ll"
    try:
        ir = compile_source(src, target_triple=triple)
    except (CompileError, SyntaxError) as e:
        print(f"Erro de compilação: {e}")
        sys.exit(1)
    with open(out_path, "w") as f:
        f.write(ir)
    print(f"IR gerado em {out_path}. Compile com:\n  clang -O3 -ffast-math {out_path} -lm -o programa")


def _usage():
    print(
        "Uso:\n"
        "  aresy                         entra no modo interativo (REPL)\n"
        "  aresy programa.ay             interpreta e roda direto (dinâmico)\n"
        "  aresy run programa.ay         mesma coisa, explícito\n"
        "  aresy build programa.ay [saida.ll] [--triple TRIPLE]\n"
        "                                 gera LLVM IR pra compilar com clang"
    )


if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) == 0:
        repl()
    elif args[0] == "build":
        _build_native(args[1:])
    elif args[0] == "run":
        if len(args) < 2:
            _usage()
            sys.exit(1)
        _run_file_dynamic(args[1])
    elif args[0] in ("-h", "--help"):
        _usage()
    elif args[0].endswith(".ay"):
        _run_file_dynamic(args[0])
    else:
        _usage()
        sys.exit(1)
