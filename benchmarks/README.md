## How to run

```bash
just bench
```

The benchmark runner writes a machine/environment header and all tables to
`benchmarks/results.txt`.

## What is measured

- **Serializers**: `dump`, `load`, and `roundtrip` are measured separately.
  Roundtrip correctness is checked once before timing, so assertions are not part
  of the hot loop.
- **TypeAdapters**: `dump`, `load`, and `roundtrip` are measured for every
  available adapter.
- **Jobify APP**: sequential `push + wait` latency and concurrent throughput are
  measured separately on fresh application/storage instances for each sample.

Each benchmark performs warmup rounds, then reports best and median microseconds
per operation, best operations per second, standard-deviation percentage, and
payload size when it is meaningful.

## Tuning run size

Use environment variables when you need quicker local checks or longer stable
runs:

```bash
JOBIFY_BENCH_SERIALIZER_ITERATIONS=10000 \
JOBIFY_BENCH_TYPEADAPTER_ITERATIONS=10000 \
JOBIFY_BENCH_APP_LATENCY_ITERATIONS=2000 \
JOBIFY_BENCH_APP_THROUGHPUT_ITERATIONS=10000 \
just bench
```

Every benchmark group also supports `_WARMUP` and `_ROUNDS` variables with the
same prefix, for example `JOBIFY_BENCH_SERIALIZER_ROUNDS=10`.

## Adding a serializer or typeadapter

Add a new case to `benchmarks/registry.py`:

- `SERIALIZER_CASES` for serializers. Choose `payloads={"json"}` for plain
  JSON-compatible payloads, `payloads={"extended"}` for extended Jobify types,
  or both.
- `TYPE_ADAPTER_CASES` for typeadapters. Return `(dumper, loader)` from the
  factory. Set `jobify_enabled=False` for adapters that should only be measured
  in the standalone TypeAdapters benchmark.

Factories may raise `ImportError`; the runner will show the case as skipped
instead of failing the whole benchmark run.
