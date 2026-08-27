# aresNeuro

Biblioteca de simulação neural para aresY.

O foco é manter a API curta e publicável no `aresy index`, sem entrar no
`stdlib/`.

O pacote traz:
- neurônio LIF discreto
- neurônio Hodgkin-Huxley clássico
- sinapses densas
- sinapses condutivas
- `TimedArray`
- `PoissonGroup`
- monitor de estado e spikes

API principal:
- `NeuronGroup(...)`
- `Synapses(...)`
- `StateMonitor(...)`
- `SpikeMonitor(...)`
- `TimedArray(values, dt)`
- `PoissonGroup(n, rate, dt)`
- `PoissonGroupRates(n, rates, dt)`
- `ares_lif_group(n, v_rest, v_reset, v_thresh, tau_m, tau_ref, dt)`
- `ares_lif_step(g)`
- `ares_drive(g, idx, current)`
- `ares_run_lif(pre, syn, post, mon, steps)`
- `ares_run_poisson_lif(pre, syn, post, mon, steps)`
- `ares_dense_synapses(pre_n, post_n, weight)`
- `ares_propagate(pre, syn, post)`
- `ares_monitor(steps, n)`
- `ares_monitor_step(mon, g)`
- `ares_hh_group(n, c_m, g_na, g_k, g_l, e_na, e_k, e_l, dt)`
- `ares_hh_step(g)`
- `ares_hh_drive(g, idx, current)`
- `ares_hh_monitor_step(mon, g)`
- `ares_cond_synapses(pre_n, post_n, weight, tau, e_rev)`
- `ares_cond_propagate(pre, syn, post)`
- `ares_run_hh(g, mon, steps)`
- `ares_run_hh_cond(g, syn, mon, steps)`

Exemplo:

```aresy
import "aresNeuro.ay"   // localmente, se o arquivo estiver no mesmo diretório
// depois de publicar no índice:
// import aresNeuro

fn main() {
    var g = ares_lif_group(3, -65.0, -70.0, -50.0, 10.0, 2.0, 0.1)
    var syn = ares_dense_synapses(3, 3, 0.0)
    ares_set_weight(syn, 0, 1, 2.0)
    ares_set_weight(syn, 1, 2, 2.0)

    var mon = ares_monitor(100, 3)
    var t = 0
    while t < 100 {
        if t == 0 {
            ares_drive(g, 0, 20.0)
        }
        ares_lif_step(g)
        ares_propagate(g, syn, g)
        ares_monitor_step(mon, g)
        t = t + 1
    }

    print(mon.v[0][0])
    print(mon.spikes[0][0])
    return 0
}
```

HH mínimo:

```aresy
import "aresNeuro.ay"

fn main() {
    var h = ares_hh_group(1, 1.0, 120.0, 36.0, 0.3, 50.0, -77.0, -54.4, 0.1)
    ares_hh_drive(h, 0, 10.0)
    ares_hh_step(h)
    print(ares_hh_voltage(h, 0))
    return 0
}
```

Poisson + `TimedArray`:

```aresy
import "aresNeuro.ay"

fn main() {
    var ta = ares_timed_array_from_shape(4, 1, 0.1)
    ares_timed_array_set(ta, 0, 0, 5.0)
    ares_timed_array_set(ta, 1, 0, 10.0)

    var rates = darray(2)
    rates[0] = 15.0
    rates[1] = 20.0
    var pg = PoissonGroupRates(2, rates, 0.1)
    ares_poisson_step(pg)
    print(ares_poisson_spike_count(pg))
    print(ares_timed_array_get(ta, 1, 0))
    return 0
}
```
