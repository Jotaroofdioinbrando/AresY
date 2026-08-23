#!/data/data/com.termux/files/usr/bin/bash
# Instala o comando "aresy" no Termux, pra poder digitar só "aresy" no
# terminal (igual "python") e cair no modo interativo.
#
# Uso:
#   pkg install clang python
#   bash install_termux.sh
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="$PREFIX/opt/aresy"
BIN_DIR="$PREFIX/bin"

mkdir -p "$DEST_DIR"
cp "$SCRIPT_DIR/aresy_compiler.py" "$DEST_DIR/aresy_compiler.py"

cat > "$BIN_DIR/aresy" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$PREFIX/opt/aresy/aresy_compiler.py" "$@"
EOF

chmod +x "$BIN_DIR/aresy"

echo "Instalado! Agora é só digitar:"
echo "  aresy                 -> abre o REPL"
echo "  aresy programa.ay     -> interpreta e roda direto"
echo "  aresy build programa.ay saida.ll  -> gera IR pra compilar com clang"
