p// bench.ay
fn main() {
    var soma = 0
    var i = 0
    while i < 100000000 {
        soma = soma + i
        i = i + 1
    }
    print(soma)
    return 0
}
