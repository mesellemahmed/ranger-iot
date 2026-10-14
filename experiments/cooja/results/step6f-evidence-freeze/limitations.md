# Experimental Limitations

The evidence freeze intentionally bounds the claims.

- The Cooja comparative campaign uses an 8-node RPL-Lite topology.
- Comparative radio results use ten paired simulation seeds per TX regime.
- TX degradation is applied after successful bootstrap to isolate rekey resilience.
- The radio study therefore does not measure end-to-end bootstrap-plus-rekey availability under the same degraded regime.
- The coding layer uses the experiment's k-of-n fragment reconstruction abstraction; these results are not a microbenchmark of a production erasure-code implementation.
- No physical-hardware campaign is included in this evidence freeze.
- Per-case manifests and checksums are the provenance authority.
