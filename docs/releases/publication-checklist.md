# v1.0.0 publication checklist

## Automated gates

- [x] Version and metadata are `1.0.0`.
- [x] Ruff lint and formatting pass.
- [x] Strict MyPy passes for `src` and `scripts`.
- [x] Risk-based unit tests pass.
- [x] All four synthetic reports regenerate byte-for-byte.
- [x] Checked release evidence matches fixtures and generator.
- [x] Two wheel builds are byte-identical.
- [x] Two canonical sdist builds are byte-identical.
- [x] Archive policy and resource budgets pass.
- [x] Verified wheel installs offline without dependencies.
- [x] Dependency consistency and known-vulnerability audit pass.

## Publication gates

- [ ] Merge the release-candidate PR after every required CI job passes.
- [ ] Record the exact merge commit and download one complete CI artifact set.
- [ ] Verify `sha256sum --check SHA256SUMS` on the selected artifact set.
- [ ] Create annotated tag `v1.0.0` at exactly the verified merge commit.
- [ ] Publish a non-prerelease GitHub Release using `docs/releases/v1.0.0.md`.
- [ ] Attach the wheel, canonical sdist, and `SHA256SUMS`.
- [ ] Confirm the public tag and release resolve to the expected commit.

Until the publication gates are complete, the repository is a release candidate,
not a published release.
