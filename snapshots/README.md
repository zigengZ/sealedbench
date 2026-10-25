# Development-commit snapshots

Public history of this repository starts fresh. Batches **b1** and **cap** bind
generator commit `95f747f0efd5b24bc507a3c7082bc74ac18f75ed` from the private
development repository. That commit is not in this git history.

See `95f747f0efd5b24bc507a3c7082bc74ac18f75ed/` for the code content at seal
time and the git tree/blob hashes anyone can recompute from the files.

## Checking the hashes

`95f747f0efd5b24bc507a3c7082bc74ac18f75ed.TREES.md` lists the commit's top-level tree entries and the blob hash of every file
under `sealedbench/` and `tools/`. Recompute them from the snapshot:

```bash
cd snapshots/95f747f0efd5b24bc507a3c7082bc74ac18f75ed
git hash-object sealedbench/manifest.py          # compare with the blob line in 95f747f0efd5b24bc507a3c7082bc74ac18f75ed.TREES.md
tmp=$(mktemp -d); cp -a sealedbench tools "$tmp"; cd "$tmp"; git init -q; git add -A
git ls-tree $(git write-tree)                    # sealedbench and tools tree hashes match the top-level list
```

The snapshot omits the commit's `STATUS.md` and its article drafts, and its `README.md` is replaced by
the public one, so the root tree hash is not reproducible here; the `sealedbench` and `tools` subtrees
and every other file are byte-identical. Other development-commit ids quoted in the docs (for example
`e6b8795`) also refer to the private development repository.
