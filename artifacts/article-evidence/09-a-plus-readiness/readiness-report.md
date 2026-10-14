# RANGER-IoT — Scientific Readiness

Hard reproducibility gate: FAIL

## Checks

- tag_matches_head: PASS
- scientific_worktree_clean: PASS
- global_scientific_hashes: PASS
- step6f1_checksums: FAIL
- step6f2_checksums: PASS
- freeze_checksums: PASS
- required_files: PASS
- independent_recomputation: FAIL
- manifest_audit: PASS
- step6f_table_inventory: PASS
- core_ci: PASS

## Paired signals requiring scrutiny

- {"completion_p": 0.0703125, "left": "recovery", "mean_reconstructed_delta": "0.6", "reconstruction_p": 0.0703125, "right": "static", "tx": "0.3"}
- {"completion_p": 0.5, "left": "adaptive-v2", "mean_reconstructed_delta": "0.2", "reconstruction_p": 0.5, "right": "recovery", "tx": "0.3"}
- {"completion_p": 1.0, "left": "adaptive-v2", "mean_reconstructed_delta": "-0.2", "reconstruction_p": 1.0, "right": "recovery", "tx": "0.2"}

## Interpretation

PASS here means the evidence package is internally reproducible and ready for claim-level scientific review.

It does not by itself imply that no additional experiment is needed. External-validity, coding-abstraction, and formal-security gaps are evaluated separately in a-plus-risk-register.md.
