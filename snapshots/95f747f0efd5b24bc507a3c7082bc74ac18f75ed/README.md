# Snapshot of development commit 95f747f

b1 and cap were sealed against the development repository commit
`95f747f0efd5b24bc507a3c7082bc74ac18f75ed`.
This public repository starts a new history, so that commit object is not present.
The code content at seal time is in this directory. Tree hashes below are
content-addressed (git tree objects); anyone can recompute them with
`git hash-object -t tree` after rebuilding the tree, or by comparing file
SHA-1 blobs listed here.

Full commit: `95f747f0efd5b24bc507a3c7082bc74ac18f75ed`
Subject: G3: freeze GSM8K-test indexes 0..119

## Top-level git trees / blobs at 95f747f

```
100644 blob fc6931d34fe5fa5f2c7ffcd23db36cc3722bd428	.gitignore
100644 blob e5649d918473f9f23394e30b4690dc5fffe4e886	MANIFEST.md
100644 blob 55bc8423e5aa87651dbbdf7bb33fdc67312153e7	README.md
100644 blob 7786c0da98130ead162c5f84af5b4938e2acb626	STATUS.md
040000 tree 20aae0cbab1832edd1825ba1bdced2f18f1bf921	article
100644 blob 07d399bf0ce57aadb112bcb6e83ad0b58f98a0fc	go.mod
100644 blob 69356be2ff7396f2c3f0e14ddef14a7cc5107b8d	go.sum
100644 blob 6679e3dbf7d2af5c93185c38e0698eb0a2118ff7	package-lock.json
100644 blob 32f74ec7550efa48ccc0d328745df8d7c8442fd7	package.json
100644 blob 228af71e95ce4e9050546da33b4036c4ef1c092f	requirements.txt
040000 tree b3d413a50a0912b937134eb6e391325cc62fc17d	results
040000 tree 4a23dd17f7ece1b80909cf96ee69f4d7f4f149a2	sealedbench
040000 tree 87a7b166d012407c101badc51b5d8ca1947c8abb	tools
```

## sealedbench/ tree

```
100644 blob daad910692954540acc00f7bda6323cefbd60cfd	sealedbench/__init__.py
100644 blob dc49ea6fc0b771a723141a0d309104487b4f4133	sealedbench/__main__.py
100644 blob 2c049d84d8b4d413ead5af8080f3cc5ddf8c4899	sealedbench/cli.py
100644 blob 4f1846b3bd59ddba38fb57169b4fe019996f52a2	sealedbench/entropy.py
100644 blob a155097e80044bb8fc01355443f7607c5e6b3039	sealedbench/extract.py
100644 blob 151dee4fec5b2e7a4429d55a80c07dbef42a84cf	sealedbench/families/__init__.py
100644 blob 43a85628d7c2d2c5d72cc23a1699799da1d2682c	sealedbench/families/arith_word.py
100644 blob 53557ed14c51f1582061afcaec40531f517d321d	sealedbench/families/code_output.py
100644 blob e3ca6b5ec9af59113ac5c3a16e2fa1418331cb33	sealedbench/families/graph_path.py
100644 blob 1d09375b66a0a73f21f8416b81b5378fe000d31a	sealedbench/generate.py
100644 blob e4bbd2e4dd47d4923d120aad45022029d268298b	sealedbench/grade.py
100644 blob 6e51c8d0de2443eea3dbd736952ab2eb08ba4b1a	sealedbench/infer.py
100644 blob 56a062799e0c7702bf764313f068349042dbc46a	sealedbench/items.py
100644 blob 969d1fadae943c0272281edb49aa8a3d0cca8366	sealedbench/manifest.py
100644 blob b9b0c057ee55cd00becd63b2599e44b22e43be44	sealedbench/net.py
100644 blob 3c0881c1c02e543b46f610e46eff5805a7737767	sealedbench/observe.py
100644 blob f23b9dedb335a380f06437172df5fdc655290fb9	sealedbench/protocol.py
100644 blob 59e7321792f5fc9bc68520dea4a70ee2cf48dda6	sealedbench/publish.py
100644 blob 68df8302d165d0e5df1f6e1eca557acfa8af6b7f	sealedbench/reference.py
100644 blob 63bd5bc870d8bf2aa1c409ddf392ff61f4eab671	sealedbench/release.py
100644 blob 5c43c18accf6f1d860f83cf3c64c66a8e419bf3d	sealedbench/replay.py
100644 blob f8e27569c25d9deabc8eb1dc82e0b8948c7f3927	sealedbench/rng.py
100644 blob bea123de6f2af794f039503e176cbb04af27ea6a	sealedbench/score.py
100644 blob 840ea03289be12fb343e20c2efc4d087fdb9e4eb	sealedbench/seal.py
100644 blob d6357d8e85854f5bd4b68467a645f511a51017ef	sealedbench/seed.py
100644 blob 7b3549b68d7c074299442dfd8d6d9ffcabed977b	sealedbench/statuslog.py
100644 blob cd9b9c32bb1f7befbd14de0477b28df2c0f22ee1	sealedbench/tarball.py
100644 blob d1b2fa40ad2d5545e1463dc66f57c810cb85f575	sealedbench/verify.py
100644 blob 29a79a15fd70ccbd9ffdc6b4595546637c0c9cd3	sealedbench/wilson.py
```

## Sealed generator paths (from b1/cap manifest)

```
100644 blob daad910692954540acc00f7bda6323cefbd60cfd	sealedbench/__init__.py
100644 blob d6357d8e85854f5bd4b68467a645f511a51017ef	sealedbench/seed.py
100644 blob f8e27569c25d9deabc8eb1dc82e0b8948c7f3927	sealedbench/rng.py
100644 blob a155097e80044bb8fc01355443f7607c5e6b3039	sealedbench/extract.py
100644 blob e4bbd2e4dd47d4923d120aad45022029d268298b	sealedbench/grade.py
100644 blob 56a062799e0c7702bf764313f068349042dbc46a	sealedbench/items.py
100644 blob 1d09375b66a0a73f21f8416b81b5378fe000d31a	sealedbench/generate.py
100644 blob 151dee4fec5b2e7a4429d55a80c07dbef42a84cf	sealedbench/families/__init__.py
100644 blob 43a85628d7c2d2c5d72cc23a1699799da1d2682c	sealedbench/families/arith_word.py
100644 blob 53557ed14c51f1582061afcaec40531f517d321d	sealedbench/families/code_output.py
100644 blob e3ca6b5ec9af59113ac5c3a16e2fa1418331cb33	sealedbench/families/graph_path.py
```

## How to check

1. Compare any sealed path under `snapshots/95f747f.../sealedbench/` to the
   blob id above: `git hash-object <file>` must equal the blob SHA-1.
2. Or compare byte-for-byte to a checkout of the private development history
   at `95f747f` (if you have access).
3. Tree ids (directories) depend only on child names and blob/tree ids.
