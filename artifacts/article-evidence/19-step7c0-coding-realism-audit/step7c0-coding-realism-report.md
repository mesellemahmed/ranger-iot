# RANGER-IoT — STEP 7C.0 Coding Realism Audit

**Automated classification:** `BYTE_LEVEL_CODING_NOT_YET_DEMONSTRATED`

## Python model

- Classes: `['CodingParameters', 'CodedFragment', 'StaticErasureCoder', 'FragmentAccumulator']`
- Functions: `[]`
- Encode-like functions: `[]`
- Decode-like functions: `[]`
- Byte-type signal: `True`
- Finite-field signal: `True`
- Matrix/coefficient signal: `False`
- Payload equality test signal: `True`
- Subset recovery test signal: `True`
- Byte-level codec demonstrated: `False`

## Embedded C implementations

### `experiments/cooja/apps/ranger-adaptive-v2-rpl/ranger-adaptive-v2-rpl.c`

- coded fragment occurrences: `4`
- uint8 array sizes near coded send: `[9]`
- update indices: `[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]`
- metadata fields index/K/N: `True` / `True` / `True`
- planned delivery threshold >= K: `True`
- payload after metadata index 8: `True`
- finite-field signal: `True`
- decoder payload signal: `True`
- metadata-only shape: `False`

### `experiments/cooja/apps/ranger-recovery-rpl/ranger-recovery-rpl.c`

- coded fragment occurrences: `3`
- uint8 array sizes near coded send: `[9]`
- update indices: `[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]`
- metadata fields index/K/N: `True` / `True` / `True`
- planned delivery threshold >= K: `True`
- payload after metadata index 8: `True`
- finite-field signal: `True`
- decoder payload signal: `True`
- metadata-only shape: `False`

### `experiments/cooja/apps/ranger-static-coded-rpl/ranger-static-coded-rpl.c`

- coded fragment occurrences: `3`
- uint8 array sizes near coded send: `[9]`
- update indices: `[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]`
- metadata fields index/K/N: `True` / `True` / `True`
- planned delivery threshold >= K: `True`
- payload after metadata index 8: `True`
- finite-field signal: `True`
- decoder payload signal: `True`
- metadata-only shape: `False`

## Guardrail

Do not describe the current mechanism as byte-level erasure coding unless actual payload symbols are encoded and arbitrary qualifying subsets reconstruct the original payload in both Python and embedded validation.

**Next:** `STEP7C1_TARGETED_BYTE_LEVEL_SEMANTIC_VALIDATION`
