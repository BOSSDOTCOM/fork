# ChessTB: endgame tablebases up to 7 pieces (and 8 with an opposing pawn pair)

Created 2026-11-09 for the owner's order of that day: ChessTB's formats,
sizes, probing code, licences, download sources and online explorer, a
proposed data-policy line, and the input for the endgame slice v2 design
(branch `research/endgame-slice-v2`, docs/research/endgame-slice-v2/design.md).

**How this file was written (concepts and docs only).**
- No ChessTB source file was opened: only its README, LICENSE, the abstract
  and introduction of CORRECTNESS.md (prose), the project's web pages, the
  mirrors' directory listings and README files, the explorer's API
  description and its Space README. For the python-chess fork that probes
  ChessTB, only the repository metadata, the list of changed file names,
  the README change and the API documentation page (docs/chesstb.rst) were
  read; the prober module itself was not opened.
- No table file was downloaded. Sizes come from directory listings and the
  Hugging Face bucket's file-list API (metadata only).
- One request was sent to the online explorer (a single KRK probe, to read
  its rate-limit headers).
- Every page opened is logged in [sources.md](sources.md), section "ChessTB
  (chesstb.md), 2026-11-09". Verified on 2026-11-09 unless marked.

## 1. What it is

- ChessTB (github.com/noobpwnftw/chesstb, by the chessdb.cn author, GitHub
  user noobpwnftw) is a generator, compressor and prober of chess endgame
  tablebases by retrograde analysis. No engine search or evaluation is
  involved in producing a value.
- Five metrics:
  - **WDL**: win, draw or loss under the fifty-move rule, with the cursed-win
    and blessed-loss classes (the same five-class idea as Syzygy WDL).
  - **DTZ**: plies to the next zeroing move (capture, promotion or pawn
    move). Its encoding is **not** Syzygy's: ChessTB stores a plain
    distance in every class and leaves the class to WDL, while Syzygy folds
    the cursed band into the DTZ magnitude (python-chess fork docs). A
    ChessTB DTZ value must never be read as a Syzygy DTZ value.
  - **DTC**: pawn pushes still owed before the next conversion, then plies
    to the next zeroing move (pawnful materials only, up to 6 pieces).
  - **DTM**: distance to mate ignoring the fifty-move rule (up to 7 pieces).
  - **DTM50**: distance to mate at every halfmove clock 0-99, in one file
    with unbounded DTM (up to 6 pieces).
- Coverage published (homepage, 2026-11-09): WDL and DTZ for all materials
  up to 7 pieces, plus 8-piece materials that contain **one opposing pawn
  pair** ("Op1": a white and a black pawn on the same file, white below
  black); DTM up to 7; DTM50 and DTC up to 6. Every set also has tables
  with castling rights (a separate `castling/` tree; Chess960 included).
- Correctness: the repository carries CORRECTNESS.md, a written proof (the
  abstract states that the generator and prober return the exact
  game-theoretic class under the fifty-move rule, exact DTZ, DTM and DTM50,
  with one documented one-ply tolerance for cursed DTZ in a one-byte storage
  tier). The proof was not checked here (**UNVERIFIED**: a proof document is
  not an independent test; see §7 for the cross-checks the design plans).
- Repository state (GitHub API, 2026-11-09): created 2026-05-17, **one
  commit** (73eeb2c4b157fc59c895c3868cfb05d9c68d8beb, dated 2026-09-12),
  last pushed 2026-11-09; no releases or tags. History appears to be
  rewritten on push (a 2026-09-12 commit pushed on 2026-11-09), so any
  reference must pin the commit SHA (**UNVERIFIED** that it is force-pushed;
  inferred from the dates).
- **Why it matters for Fork:** Phase 4 training data. Fork's endgame slice
  (ideas.md idea 45; tools/datagen/endgame_slice.py) labels random positions
  of at most 5 pieces with Syzygy WDL from the local 3-4-5 tables. ChessTB
  publishes WDL per material file in a public-domain dedication, smaller
  than Syzygy's files for most 6-7-piece materials (§3), with a pure-Python
  prober (§4), so a slice of 6-7-piece (and selected 8-piece) positions can
  be labelled from a handful of downloaded files. The engine itself keeps
  Syzygy through Fathom (TCEC supplies 7-man Syzygy); ChessTB is a
  training-data tool only.

## 2. File formats (README, "Format" and "Generate")

- One file per material and metric, in a directory per metric:
  `wdl/<material>.lzw`, `dtz/<material>.lzdtz`, `dtc/<material>.lzdtc`,
  `dtm/<material>.lzdtm`, `dtm50/<material>.lzdtm50`, plus `.info` files
  (orbit-weighted W/D/L/illegal counts and the longest win with its FEN).
- **Material names** list White's pieces then Black's with no separator
  (`KRPKR`), and the stronger side is not always first (`KRKBPP` is stored
  as `KBPPKR`). Lowercase `p` marks the opposing pair (`KRPPpKRp`) and
  lowercase `r` a rook with castling rights. **File names are
  case-sensitive**: the README asks for a case-sensitive file system (on
  Windows, an empty folder switched to case sensitivity with `fsutil` as
  Administrator; on Linux, ext4 is case-sensitive already).
- **WDL**: a 4-bit class code per position (two per byte), in independent
  64 KiB blocks compressed with LZ4-HC and a dictionary trained on the
  table. Two spare codes mark positions on the fifty-move boundary; ordinary
  readers map them to win or loss.
- **Distance tables** (DTZ, DTC, DTM, DTM50): values mapped to
  frequency-ranked codes of 1 or 2 bytes, LZMA-compressed in 1 MiB blocks.
- **Index**: built for paging, with king and pawn dimensions; the opposing
  pair is one 120-placement dimension, which is what makes 8-piece Op1
  tables affordable.
- **Shipping forms versus full forms.** The `full/` tree holds the raw
  generator output. The shipping tree (the root `wdl/`, `dtz/`, ...) is
  post-processed by `shrink` and possibly `transcribe`, which may:
  - **drop one side-to-move frame** when it can be rebuilt at probe time by
    a one-ply search over the kept frame, reading capture and promotion
    children from **other material files** (sub-tables);
  - store **loss-only** distance frames, or **relaxed** WDL/DTZ frames whose
    cells are filled with whatever compresses best where a capture or
    promotion already proves the class (again needing sub-tables).
  - A full table decodes from its own file alone, except for en-passant
    captures (each legal one adds a probe of that capture's sub-table).
  - **Which shipping files carry a dropped or relaxed frame is UNVERIFIED**:
    it is recorded in each file's per-colour flag byte, which was not read
    (no table bytes were downloaded). Consequence for Fork: labelling with
    shipping files needs every capture and promotion child material on disk
    (for a pawnful 7-piece material that includes other 7-piece materials);
    labelling with `full/` files of the chosen materials needs nothing else,
    provided the positions carry no en-passant right.

## 3. Sizes

### 3.1 Totals by piece count

Published by the README (shipping forms, castling tables included):

| Pieces | WDL | DTZ | DTM |
|---|---:|---:|---:|
| up to 6 | 35.7 GiB | 75.6 GiB | 301 GiB |
| up to 7 | 4.21 TiB | 7.79 TiB | 37.2 TiB |
| 8 (Op1 only) | 5.83 TiB | 7.6 TiB | not planned |

DTM50 up to 6 is 1.1 TiB and DTC up to 6 is 178 GiB (README).

Summed here from the Hugging Face bucket's file list (no castling tables;
GiB = 2^30 bytes; 1,876 materials per metric):

| Pieces | files | WDL shipping | WDL `full/` | DTZ shipping | DTZ `full/` |
|---|---:|---:|---:|---:|---:|
| 3-5 | 145 | 0.19 GiB | 0.80 GiB | 0.49 GiB | 1.55 GiB |
| 6 | 365 | 33.9 GiB | 134.2 GiB | 70.3 GiB | 232.6 GiB |
| 7 | 1,001 | 4,055 GiB | 15,239 GiB | 7,423 GiB | 24,486 GiB |
| 8 Op1 | 365 | 5,799 GiB | 21,347 GiB | 7,503 GiB | 27,064 GiB |

- The whole bucket: 275,154,247,966,122 bytes (about 250 TiB; Hugging Face
  shows "275 TB") in 31,497 files (API, 2026-11-09).
- For comparison, Syzygy's 7-piece WDL files on the Lichess mirror total
  8.47 TiB (summed from its `bytes.tsv`); ChessTB's shipping 7-piece WDL is
  about half that.

### 3.2 Per material (WDL, the endgame slice v2 candidates)

Sizes from the bucket listing, 2026-11-09. "Shipping" is the root `wdl/`
file, "full" the `full/wdl/` file; the Syzygy column is the `.rtbw` file on
the Lichess Syzygy mirror (`bytes.tsv`), for comparison.

| Material | Pieces | ChessTB shipping | ChessTB full | Syzygy WDL |
|---|---:|---:|---:|---:|
| KRPPvKR | 6 | 0.11 GiB | 0.49 GiB | 0.23 GiB |
| KRPvKRP | 6 | 0.50 GiB | 0.93 GiB | 0.48 GiB |
| KRPPPvKR | 7 | 0.65 GiB | 3.70 GiB | 1.00 GiB |
| KRPPvKRP | 7 | 10.93 GiB | 34.48 GiB | 21.66 GiB |
| KRPPpKRp (KRPPP v KRP with one opposing pair) | 8 | 10.69 GiB | 44.94 GiB | none (8 pieces) |
| KRPvKBP | 6 | 0.52 GiB | 1.82 GiB | 1.16 GiB |
| KRPvKNP | 6 | 0.42 GiB | 1.51 GiB | 1.04 GiB |
| KRvKBPP | 6 | 0.24 GiB | 0.85 GiB | 0.51 GiB |
| KRvKNPP | 6 | 0.23 GiB | 0.78 GiB | 0.52 GiB |
| KRPPvKB | 6 | 0.03 GiB | 0.19 GiB | 0.03 GiB |
| KRPPvKN | 6 | 0.02 GiB | 0.14 GiB | 0.03 GiB |
| KRPPvKBP | 7 | 6.13 GiB | 23.75 GiB | 10.65 GiB |
| KRPPvKNP | 7 | 4.53 GiB | 17.91 GiB | 8.97 GiB |
| KQPPvKQ | 6 | 0.22 GiB | 0.86 GiB | 0.41 GiB |
| KQPvKQP | 6 | 0.63 GiB | 1.31 GiB | 0.48 GiB |
| KQPvKRB | 6 | 0.65 GiB | 2.05 GiB | 1.00 GiB |
| KQPvKRN | 6 | 0.52 GiB | 1.81 GiB | 0.90 GiB |
| KQvKRBP | 6 | 0.93 GiB | 3.01 GiB | 1.86 GiB |
| KQvKRNP | 6 | 1.07 GiB | 2.93 GiB | 1.96 GiB |
| KQPvKRR | 6 | 0.45 GiB | 1.47 GiB | 0.76 GiB |
| KQvKRRP | 6 | 0.42 GiB | 1.47 GiB | 0.86 GiB |
| KQPPPvKQ | 7 | 1.62 GiB | 8.67 GiB | 3.49 GiB |
| KQPPvKRB | 7 | 6.97 GiB | 26.37 GiB | 8.96 GiB |
| KQPPvKRN | 7 | 5.15 GiB | 23.64 GiB | 7.98 GiB |
| KBvKPPP | 6 | 0.05 GiB | 0.14 GiB | 0.11 GiB |
| KNvKPPP | 6 | 0.04 GiB | 0.12 GiB | 0.09 GiB |
| KRvKPPP | 6 | 0.06 GiB | 0.18 GiB | 0.16 GiB |
| KBPvKPP | 6 | 0.20 GiB | 0.63 GiB | 0.50 GiB |
| KNPvKPP | 6 | 0.24 GiB | 0.60 GiB | 0.55 GiB |
| KRPvKPP | 6 | 0.07 GiB | 0.37 GiB | 0.23 GiB |
| KQvKPPP | 6 | 0.01 GiB | 0.13 GiB | 0.08 GiB |
| KRvKPPPP | 7 | 0.68 GiB | 1.90 GiB | 1.64 GiB |
| KBvKPPPP | 7 | 0.31 GiB | 1.04 GiB | 0.59 GiB |
| KNvKPPPP | 7 | 0.20 GiB | 0.71 GiB | 0.41 GiB |
| KQvKPPPP | 7 | 0.27 GiB | 1.77 GiB | 1.12 GiB |
| KRPvKPPP | 7 | 1.90 GiB | 6.88 GiB | 4.33 GiB |
| KBPvKPPP | 7 | 3.64 GiB | 10.14 GiB | 7.06 GiB |
| KNPvKPPP | 7 | 3.30 GiB | 8.77 GiB | 6.22 GiB |

The shipping and Syzygy columns are not like for like: both may need
sub-tables to answer every position (§2; for Syzygy the dependency rule was
not re-checked here, **UNVERIFIED**), while a `full/` file stands alone.
The per-material W/D/L statistics are published in the project's
`stats.json` (generated 2026-11-08), which the design can use to anticipate
each material's draw share.

## 4. Probing code

| Prober | Language | Licence | Form | Status for Fork |
|---|---|---|---|---|
| ChessTB `src/probe/` (with `tools/probe_fen`) | C++ (the proof's introduction: a C++17 system of about 34,500 lines; GitHub reports C and C++, the C presumably the vendored LZ4, LZMA and zstd in `lib/`) | The Unlicense (LICENSE.md; GitHub API SPDX `Unlicense`) | The README calls `src/probe/` a standalone probe library, and the project's "What's new" page names its API header `src/probe/probe.h`; `probe_fen` is a separate diagnostic program that prints every metric for one FEN | **REFERENCE ONLY** (not needed: Fork's engine probes Syzygy through Fathom). Whether the library builds on its own outside the repository, and whether `probe_fen` accepts a batch of FENs, is **UNVERIFIED** (code not opened). Vendoring or linking it would need an owner decision like Fathom's |
| `chess.chesstb` in the python-chess fork noobpwnftw/python-chess, branch `add-chesstb-tablebases`, commit 38c108efd992538dc078750cba9fee30b9f030ce (2026-09-01) | pure Python (standard library only; uses `python-lz4` for WDL blocks when installed) | GPL-3.0 (the fork's licence per the GitHub API; the upstream is niklasf/python-chess) | A Python module. Documented API: `open_tablebase(dir)`, `probe_wdl(board)` returning +2 (win) to -2 (loss), `probe_dtz`, `probe_dtc`, `probe_dtm`, `probe_dtm50`, `MissingTableError`; tables are memory-mapped, omitted frames are reconstructed from sub-tables; the caller must pass a legal position (`Board.is_valid()` first) | **USE** as a data-generation tool dependency outside the engine (like python-chess for Syzygy today), pinned at the commit SHA, in its own virtual environment so Fork's pinned python-chess is untouched. One commit ahead of the fork's master (GitHub compare API). Probe speed **UNVERIFIED** (to be measured) |
| ChessTB Explorer (§6) | Python (Flask) backend, React frontend | GPL-3.0-or-later (Space metadata and README) | A web service over the Hugging Face bucket | **USE for spot checks only**, within its limits |

## 5. Licence and the public-domain claim

- **Code**: LICENSE.md is the standard Unlicense text: a dedication of the
  software to the public domain, with a fallback permission to copy, modify,
  publish, use, compile, sell or distribute it for any purpose, and no
  warranty. It speaks of "this software"; it does not mention table files.
- **Table files**: the README in the Hugging Face bucket and the identical
  README on the Lichess mirror both state that the tablebase data is
  dedicated to the public domain under **CC0 1.0** (linked to
  creativecommons.org/publicdomain/zero/1.0/). The project homepage says the
  same in plain words: the source code and the table files are public
  domain, for any purpose.
- The CC0 legal code itself was not reopened here (it is a standard
  instrument; the statement verified is that the data is released under
  it).
- Tag for the table files: **USE** (as labels, once the owner adopts the
  policy line in §8). Licence: CC0 1.0 (data), Unlicense (code).
- Provenance: retrograde analysis with no engine evaluation, so rule 2 of
  [data-policy.md](data-policy.md) (Stockfish-touched data) does not apply.
  chessdb.cn's own position database stays OFF-LIMITS (its scorer is not
  stated); that verdict is about the database, not these tables.

## 6. Download sources and the online explorer

### 6.1 Mirrors (README, "Download")

| Mirror | What is there (2026-11-09) | Notes |
|---|---|---|
| Hugging Face Storage Bucket `chesstb/chesstb` (huggingface.co/buckets/chesstb/chesstb; `hf://buckets/chesstb/chesstb/`) | All metrics, shipping and `full/` forms, castling tables: 31,497 files, about 250 TiB | A **bucket**, not a dataset: the chesstb organisation has no datasets or models on Hugging Face (API). Downloads by `hf buckets sync` or `hf buckets cp` (huggingface_hub CLI), with `--include` patterns per material; single files also over HTTPS under `.../resolve/<path>`. The file-list API gives size and a Xet content hash per file. CDN regions in the US and EU (GCP and AWS) |
| Lichess mirror https://chesstb.lichess.ovh/tables/ | Plain HTTP directory listings: `wdl/`, `dtz/`, `dtc/`, `dtm/`, `dtm50/`, `castling/`, `info/`, `full/` | Shipping `wdl/` and `dtz/` files have the same sizes as the bucket's for all 1,876 materials. Its `full/wdl/` entries are **0-byte placeholders** on 2026-11-09, so the full forms come from the bucket (or the FTP mirror). No usage terms published for this host (**UNVERIFIED**: none found) |
| FTP `ftp.chessdb.cn/pub/chesstb/` (public login given in the README) and the matching rsync module | Same top-level layout, `full/` included | One spot check: KRPKRP.lzw has the bucket's size (540,075,720 bytes) |

- **Checksums**: no SHA-256 list is published for ChessTB (none found on the
  Lichess mirror, unlike its Syzygy tree). The bucket's Xet hash is a
  content hash, but whether it can be recomputed locally without the
  Hugging Face tools is **UNVERIFIED**. A download is therefore pinned by
  its size and Xet hash from the listing, plus a SHA-256 computed locally
  and recorded in the slice's manifest.
- The bucket README's ready-made commands fetch every material up to N
  pieces (WDL and DTZ up to 6 pieces with castling: about 111 GiB). Fork
  needs a few named materials only (the design's budget), so downloads go
  file by file with exact paths.

### 6.2 The online explorer

- https://chesstb-explorer.hf.space/ (Hugging Face Space `chesstb/explorer`,
  Docker, created 2026-10-09), deployed from the third-party repository
  PunisherChess/ChessTB-Explorer-Render at commit 4969e401 (Space README).
  It probes the bucket over HTTP byte ranges through the python-chess fork,
  preferring `full/` tables.
- **API** (its OpenAPI description at `/openapi.yaml`): `POST /probe` with a
  JSON FEN returns WDL, DTZ, DTC, DTM and DTM50 for the position **and every
  legal move ranked under each metric**, so each request is heavy for the
  server; `POST /probe/stream` is the same as server-sent events;
  `GET /health`.
- **Limits** (verified): rate limited per client IP. The response to one
  probe on 2026-11-09 carried `X-RateLimit-Limit: 300` and
  `Retry-After: 60`, i.e. 300 probes per minute per IP; over the limit the
  answer is HTTP 429. Request bodies at most 4 KB, FEN strings at most 100
  characters. Requests marked `X-Prefetch: 1` have a separate, smaller limit
  (the Space README's default is 120 per minute; the deployed value was not
  observed). Probe timeouts return 503; an unreachable table source 502.
- **Terms**: no usage terms beyond the rate limits are published by the
  Space (**UNVERIFIED**: none found); Hugging Face's own terms of service
  apply to the host. The explorer's code is GPL-3.0-or-later.
- **Use for Fork**: spot checks only (a few hundred positions, one request at
  a time at about one every 2 seconds, a tenth of the limit). Labelling
  millions of positions through it would take days at the full limit and
  would load a free community service; local tables are the only labelling
  route.

## 7. Planned verification before any label is used

These are design steps (docs/research/endgame-slice-v2/design.md), not
results; nothing here has been run.
1. **Prober against Syzygy at 3-5 pieces**: the ChessTB shipping WDL set up
   to 5 pieces (0.19 GiB; its sub-tables are all within the set) against
   Fork's local Syzygy 3-4-5 through upstream python-chess, on random legal
   positions without en-passant or castling rights: every WDL class must
   agree, the cursed and blessed classes included.
2. **6-7 pieces against independent sources**: a few hundred slice positions
   against the Lichess Syzygy tablebase API (one request at a time, KB
   tools.md §6.9) and the ChessTB explorer (§6.2).
3. **Self-contained files**: each `full/` file is probed alone in an empty
   directory; any `MissingTableError` stops the run.

## 8. Data-policy line (proposed here; adopted by the owner 2026-11-09, data-policy.md and DESIGN.md training-data decision 1)

Proposed text for the "Source status" table of
[data-policy.md](data-policy.md), and for rule 1's list of exceptions in
data-policy.md and DESIGN.md §5.3 ("Training-data decisions"):

- Rule 1, amended: "Every eval, score or search statistic used to train a
  Fork net comes from a Fork binary, with three exceptions: game results,
  Syzygy tablebase results and ChessTB tablebase results (exact
  retrograde-analysis facts, not engine output)."
- New row:

| Source | Use | Status | Why |
|---|---|---|---|
| ChessTB tablebases (WDL/DTZ), noobpwnftw/chesstb, CC0 1.0 data | labels for positions of up to 7 pieces, and 8-piece positions with an opposing pawn pair; never in the engine | **ALLOWED** (proposed) | Exact retrograde results like Syzygy's, with a public-domain dedication (CC0 1.0 for the tables, the Unlicense for the code). Conditions: (1) **labels only**: WDL classes (and DTZ distances if ever used, read by ChessTB's own convention, never as Syzygy DTZ); no engine-generated evaluation or move from any source enters with them, and the slice's score field is derived from the WDL class alone; (2) **provenance recorded** in the slice manifest and ORIGINALITY.md: mirror URL, form (`full/` or shipping), each file's size, Xet hash and locally computed SHA-256, the prober and its pinned commit; (3) **verified before use** (§7: agreement with Syzygy where both exist, independent spot checks at 6-7 pieces, self-contained files); (4) **files stay outside the repository** (download-only, deleted when the slice is sealed, re-fetchable from the manifest); (5) the online explorer is a spot-check tool within its published limits, never a labelling route |

## 9. Tags

| Item | Tag | Licence |
|---|---|---|
| ChessTB table files (WDL; DTZ if ever needed) | **USE** for training labels once §8 is adopted | CC0 1.0 |
| ChessTB DTM, DTM50, DTC tables | REFERENCE ONLY (not needed) | CC0 1.0 |
| ChessTB generator and C++ probe library | **REFERENCE ONLY** (not opened, not needed) | Unlicense |
| python-chess fork `chess.chesstb` (pinned 38c108e) | **USE** as a data-tool dependency outside the engine | GPL-3.0 |
| ChessTB Explorer (hosted) | **USE** for spot checks within its limits | GPL-3.0-or-later (code) |
| chessdb.cn position database (unrelated to the tables) | OFF-LIMITS (unchanged) | see data-policy.md |
