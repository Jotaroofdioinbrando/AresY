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
    ("COMMENT",  r"//.*"),
    ("OP",       r"==|!=|<=|>=|[+\-*/%=<>(){}\[\],]"),
    ("NEWLINE",  r"\n"),
    ("SKIP",     r"[ \t]+"),
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


def compile_ir_to_binary(clang_path, ir_source, out_path, target_triple=None, opt_level="-O2"):
    with tempfile.TemporaryDirectory() as td:
        ll_path = os.path.join(td, "prog.ll")
        with open(ll_path, "w") as f:
            f.write(ir_source)
        cmd = [clang_path, opt_level, ll_path, "-lm", "-o", out_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise NativeError(proc.stderr.strip() or "clang falhou ao compilar")


def run_file_native(path, target_triple=None):
    clang_path = find_clang()
    if not clang_path:
        print("clang não encontrado. Instala com: pkg install clang")
        sys.exit(1)
    with open(path) as f:
        src = f.read()
    try:
        ir = compile_source(src, target_triple=target_triple)
    except (CompileError, SyntaxError) as e:
        print(f"Erro de compilação: {e}")
        sys.exit(1)
    with tempfile.TemporaryDirectory() as td:
        bin_path = os.path.join(td, "programa")
        try:
            compile_ir_to_binary(clang_path, ir, bin_path, target_triple)
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
    def __init__(self, clang_path, target_triple=None):
        self.clang_path = clang_path
        self.target_triple = target_triple
        self.codegen = CodeGen(target_triple=target_triple)
        self.func_ir = {}       # nome -> IR já gerado da função
        self.var_types = {}     # nome -> "i64" | "double"
        self.var_values = {}    # nome -> valor atual conhecido
        self.array_vars = set()  # variáveis que guardam array (não persistem)

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
                self.codegen.functions[s.name] = {
                    "params": s.params,
                    "ret": self.codegen._scan_return_type(s.body),
                }
                self.func_ir[s.name] = self.codegen.gen_function(s)
            else:
                new_stmts.append(s)

        if not new_stmts:
            return None

        # eco automático: expressão solta no fim vira print (tipo REPL do python)
        if isinstance(new_stmts[-1], ExprStmt):
            new_stmts[-1] = Print(new_stmts[-1].expr)

        env = {}
        lines = []

        # reinjeta variáveis de rounds anteriores como literais
        for name, t in self.var_types.items():
            if name in self.array_vars:
                continue
            v = self.var_values[name]
            lines.append(f"  %{name} = alloca {t}, align 8")
            lines.append(f"  store {t} {self._literal(t, v)}, {t}* %{name}, align 8")
            env[name] = t

        for s in new_stmts:
            if isinstance(s, VarDecl):
                if s.name in env:
                    # redeclaração vira reatribuição (o tipo já existente é mantido)
                    s = Assign(s.name, s.expr)
                else:
                    self.array_vars.discard(s.name)
                    if isinstance(s.expr, Call) and s.expr.name == "array":
                        self.array_vars.add(s.name)
            self.codegen.gen_stmt(s, env, lines, "i32")

        trackable = [n for n in env if n not in self.array_vars]
        self.codegen.gen_stmt(Print(Str('"' + STATE_BEGIN + '"')), env, lines, "i32")
        for name in trackable:
            self.codegen.gen_stmt(Print(Var(name)), env, lines, "i32")
        self.codegen.gen_stmt(Print(Str('"' + STATE_END + '"')), env, lines, "i32")

        body = "define i32 @main() {\nentry:\n" + "\n".join(lines) + "\n  ret i32 0\n}"

        header = ""
        if self.target_triple:
            header += f'target triple = "{self.target_triple}"\n'
        header += BUILTIN_DECLARES + FMT_CONSTANTS + "\n"
        ir = (header + "\n".join(self.codegen.strings) + "\n"
              + "\n".join(self.func_ir.values()) + "\n" + body)

        with tempfile.TemporaryDirectory() as td:
            bin_path = os.path.join(td, "repl_bin")
            # -O2, igual ao modo arquivo: o custo extra de compilar com
            # otimização é irrelevante (poucos ms) comparado ao ganho em
            # blocos com loop pesado (ex.: um "while" de centenas de
            # milhões de iterações), onde -O0 deixava a execução MUITO
            # mais lenta que o binário do "aresy arquivo.ay" equivalente.
            compile_ir_to_binary(self.clang_path, ir, bin_path, self.target_triple, opt_level="-O2")
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

        return before, proc.returncode


def repl(target_triple=None):
    clang_path = find_clang()
    if not clang_path:
        print("clang não encontrado. Instala com: pkg install clang")
        sys.exit(1)

    print("aresY — modo interativo (compila e roda nativo via clang)")
    print("Ctrl+D ou Ctrl+C pra sair.\n")
    session = ReplSession(clang_path, target_triple=target_triple)
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

def compile_source(source, target_triple=None):
    tokens = tokenize(source)
    ast = Parser(tokens).parse_program()
    return CodeGen(target_triple=target_triple).compile_program(ast)


def _build_native(argv):
    # python aresy_compiler.py build programa.ay [saida.ll] [--triple TRIPLE]
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


def _extract_triple(argv):
    triple = None
    rest = list(argv)
    if "--triple" in rest:
        i = rest.index("--triple")
        triple = rest[i + 1]
        del rest[i:i + 2]
    return triple, rest


def _usage():
    print(
        "Uso:\n"
        "  aresy                         entra no modo interativo (REPL, nativo via clang)\n"
        "  aresy programa.ay             compila e roda direto (nativo, sem interpretar)\n"
        "  aresy run programa.ay         mesma coisa, explícito\n"
        "  aresy build programa.ay [saida.ll] [--triple TRIPLE]\n"
        "                                 gera LLVM IR pra compilar com clang na mão\n"
        "  (adicione --triple TRIPLE em qualquer comando acima se precisar\n"
        "   de um target diferente do padrão do seu aparelho)"
    )


if __name__ == "__main__":
    triple, args = _extract_triple(sys.argv[1:])

    if len(args) == 0:
        repl(target_triple=triple)
    elif args[0] == "build":
        _build_native(args[1:] + (["--triple", triple] if triple else []))
    elif args[0] == "run":
        if len(args) < 2:
            _usage()
            sys.exit(1)
        run_file_native(args[1], target_triple=triple)
    elif args[0] in ("-h", "--help"):
        _usage()
    elif args[0].endswith(".ay"):
        run_file_native(args[0], target_triple=triple)
    else:
        _usage()
        sys.exit(1)
