---
paths:
  - "src/**/*.{cpp,hpp}"
  - "tests/**/*.{cpp,hpp}"
---
# SIMD rules (DESIGN.md section 7, performance doctrine)

- Use compiler intrinsics (`<immintrin.h>`) only. No inline or hand-written
  assembly.
- **Every SIMD path has a scalar reference implementation** in the same
  module, always compiled, with the same signature.
- **Every SIMD path has an equivalence test** proving it gives exactly the
  scalar result:
  - integer kernels must be bit-identical;
  - inputs are randomized (fixed seed) plus edge cases: zero, minimum and
    maximum values, saturation boundaries, unaligned tails if supported.
- Target selection is by build preset:
  - AVX2 (`x86-64-v3`), AVX-512 (`x86-64-v4`), AVX-512 VNNI (added in
    Phase 4), and scalar;
  - select with `#if defined(__AVX512F__)` etc. at compile time, never with
    runtime CPU dispatch in hot paths;
  - bench must be identical on all of them (bench_parity).
- Buffers used by SIMD kernels are 64-byte aligned (`alignas(64)`), with
  sizes a multiple of the widest vector.
- A SIMD optimization is accepted only with a measured gain from
  `bench/ab.py` and the equivalence test passing on every preset.
