# v1.0.0 support and recovery matrix

| Boundary | Verified environment | Recovery or failure behavior |
| --- | --- | --- |
| Runtime | CPython 3.11, 3.12, and 3.13 on GitHub-hosted Ubuntu | Inputs fail closed with typed schema/evaluation errors; source artifacts remain unchanged. |
| Evidence regeneration | Offline repository fixtures on each supported Python | Any missing, extra, changed, or stale evidence file fails exact verification. Regenerate from reviewed fixtures and generator. |
| Wheel | Pure Python wheel, isolated virtual environment | Reject malformed metadata/members; rebuild from the verified commit. Installation uses no index and no dependency resolution. |
| Source archive | Canonical gzip/tar built from a validated Hatchling sdist | Reject unsafe members before repacking. Rebuild from the verified commit; no archive is extracted by the verifier. |
| Checksums | SHA-256 over the selected wheel and canonical sdist | A mismatch blocks use/publication. Obtain the artifact set again from the same verified CI job. |
| Provider or network | Not supported or exercised | There is no automated recovery claim. Recorded fixtures remain the only supported judge boundary. |

Windows, macOS, alternative Python implementations, live providers, signing,
remote artifact retention, and production disaster recovery have not been
verified for v1.0.0.
