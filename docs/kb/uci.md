# Fork KB: the UCI protocol (Phase 2)

A paraphrased, cited summary of the UCI specification for Fork's Phase 2
(UCI front end) spec, plus the places where the spec is silent and real
runners fill the gap. Verified **2026-10-23**. Every page opened is logged
in [sources.md](sources.md) under "UCI protocol (uci.md)".

## The source

- **What:** "Description of the universal chess interface (UCI)", dated
  **April 2006** in its header, by Stefan Meyer-Kahlen (Shredder). The
  protocol was designed by Rudolf Huber and Stefan Meyer-Kahlen in 2000
  (Shredder UCI page; CPW says it was released in November 2000).
- **Distribution used:** the Shredder site's own download,
  https://www.shredderchess.com/download/div/uci.zip, linked as "Start
  Download" under "Download UCI Chess Engine Protocol" on
  https://www.shredderchess.com/download.html. The Shredder UCI page
  (https://www.shredderchess.com/chess-features/uci-universal-chess-interface.html)
  calls this "the current specification", and CPW's UCI page links that
  Shredder page as "The UCI Specification". No other mirror was needed.
  - `uci.zip`: 8553 bytes, sha256
    `966de351d34302ad1c0ab7c148bd365b26c5ece7eed7a75a7ca08b5925e6343e`.
  - It holds one file, `engine-interface.txt`: 26211 bytes, ASCII with CRLF
    line endings, zip timestamp 2006-04-22 16:10, sha256
    `cda40659c9f047743ebfe8328f8554d7fa2e3587b7f511f102390b6bdcc21e02`.
  - All 543 lines were read on 2026-10-23. Line numbers below (`L123`)
    refer to that file.
- **License:** the Shredder UCI page says the protocol is open and anyone
  may use it without licence fees. The text file itself carries no licence
  or copyright notice, so **UNVERIFIED** whether the document may be
  redistributed. Don't commit a copy into Fork's repo; link to it and cite
  the hash.
- **Tag:** **USE** (Fork must implement the protocol; the implementation is
  Fork's own code).
- **Why it matters for Fork:** Phase 2 (UCI front end, option handling,
  info output), Phase 5 (time management reads `go` arguments), Phase 6
  (`Threads`, `Hash` sizing), Phase 3 (`SyzygyPath`, `tbhits`) and the
  Phase 2 acceptance runners (`fastchess --compliance`, cutechess-cli;
  see [tools.md](tools.md)). TCEC's conditions (Threads up to 512,
  Hash 262144, SyzygyPath, ponder off, other options default unless the
  author asks) are in [competition.md](competition.md).

---

## 1. General rules (L6-L42)

- The interface is OS-independent; on Windows the engine is an ordinary exe
  (console or GUI). All traffic is text lines over stdin/stdout.
- **Fast boot.** The engine should start quickly and do its heavy setup
  only when `isready` or `setoption` arrives (L11-L13). The boot example
  adds that the GUI may send `quit` right after `uciok` just to read the
  engine's details, so nothing should be initialised before that point
  (L461-L463).
- **Input is always live.** The engine must keep reading stdin while it
  searches (L15). In practice this means a dedicated input thread or a
  search that polls; the spec doesn't say which.
- **Line endings.** Every command ends in a newline, but the spec warns that
  the newline may be CR, CRLF or some other mix depending on the OS, which
  matters when a Linux engine talks to a Windows GUI (L17-L21). Fork's
  reader should accept LF, CRLF and stray CR.
- **Whitespace.** Any amount of spaces and tabs between tokens is legal
  (L23-L25).
- **Forced mode.** The engine never starts calculating or pondering until it
  gets `go` (L27-L28). A `position` command always comes before a search
  (L30-L31).
- **Books.** The GUI handles the opening book by default; `OwnBook` lets
  the engine use its own (L33-L34).
- **Unknown input.** Unknown commands or tokens are skipped and the rest of
  the line is still parsed. The spec's example: an unknown word *before*
  `debug on` still turns debug on, but an unknown word *between* `debug`
  and `on` gives undefined behaviour (L36-L39).
- **Unexpected commands.** A command that makes no sense in the current
  state (e.g. `stop` while idle) is ignored (L41-L42).

## 2. Move format (L45-L50)

- Long algebraic coordinates: from-square then to-square, e.g. `e2e4`.
- Castling is sent as the king's move: `e1g1` is white short castling.
- Promotion appends the piece letter: `e7e8q`. The spec shows only the
  lowercase `q` example; it doesn't spell out the other letters or the
  case, so Fork should emit lowercase `n b r q` and accept them (the
  lowercase convention for all four letters is **UNVERIFIED** from the
  spec text itself).
- A null move sent from engine to GUI is `0000`.
- **Chess960 exception** (L533-L536): with `UCI_Chess960` on, castling is
  sent as "king takes own rook", e.g. `e1h1` for white short castling from
  the standard start position.

## 3. GUI to engine (L54-L182)

| Command | Syntax | What the spec says |
|---|---|---|
| `uci` | `uci` | Sent once, first, after start-up. The engine answers with `id` (name and author), then its `option` lines, then `uciok`. If `uciok` doesn't come within some time limit the GUI kills the engine (L59-L66). |
| `debug` | `debug on` / `debug off` | Turns debug mode on or off; debug mode means extra output such as `info string` lines (e.g. echoing received commands). Off by default. May arrive at any time, including during a search (L68-L73). |
| `isready` | `isready` | Synchronisation and liveness ping. The GUI sends it after slow commands (the spec's example is setting a tablebase path), and it is **required once before the first search** so the engine can finish initialising. It must **always** be answered with `readyok`. If it arrives during a search, the engine answers **immediately and keeps searching** (L75-L84). |
| `setoption` | `setoption name <id> [value <x>]` | Changes one engine parameter per line. Buttons have no `value` part. Only sent while the engine is idle ("waiting"). Names and values should be treated case-insensitively and may contain spaces. The words `name` and `value` should not appear inside `<id>` or `<x>`, so parsing stays unambiguous: the name is everything between `name` and `value`, and the value is everything after `value` (L86-L98). The examples include a button (`setoption name Clear Hash`) and a value with backslashes and semicolons (a tablebase path list). |
| `register` | `register later` / `register name <x> code <y>` | Registration attempt, or "not now". The GUI must send it if the engine reported `registration error` at start-up (L100-L113). Irrelevant for a free engine. |
| `ucinewgame` | `ucinewgame` | The next search is from a different game (a new game, a new analysis, or the next position of a test suite). The engine must not *depend* on it: if none arrives before the first `position`, the GUI probably doesn't support it. Because handling it can be slow (e.g. clearing the hash), the GUI should follow it with `isready` (L115-L123). |
| `position` | `position [fen <fenstring> \| startpos] moves <m1> ... <mi>` | Set up the FEN or the start position and then play the listed moves on the internal board. No separate "new" command is needed, but positions from a different game should be preceded by `ucinewgame` (L125-L130). The `moves` part can be absent: the spec's own `searchmoves` example uses a bare `position startpos` (L138). |
| `go` | `go [sub-arguments...]` | Start searching the current position. All sub-arguments come on the same line. **A sub-argument that isn't sent should be treated as not limiting the search** (L132-L135). Sub-arguments are listed below. |
| `stop` | `stop` | Stop as soon as possible. The engine still has to send `bestmove` (and `ponder` if it has one) (L173-L175). |
| `ponderhit` | `ponderhit` | The opponent played the move the engine was pondering on. The engine keeps searching but switches from ponder mode to a normal, clock-bound search (L177-L179). |
| `quit` | `quit` | Exit as soon as possible (L181-L182). |

### `go` sub-arguments (L136-L171)

| Token | Meaning |
|---|---|
| `searchmoves <m1> ... <mi>` | Search only these root moves. Example: `go infinite searchmoves e2e4 d2d4` searches only those two from the start position. |
| `ponder` | Search in ponder mode. The last move in the preceding `position` line is the expected opponent move. **Don't end a ponder search on your own, even on a found mate.** After `ponderhit` the engine should play the line it was pondering on. If the engine ponders on some other move instead, it shouldn't print main lines, since the GUI will read them as lines for the suggested move. |
| `wtime <x>` / `btime <x>` | White's / Black's remaining clock time in ms. |
| `winc <x>` / `binc <x>` | White's / Black's increment per move in ms, when x > 0. |
| `movestogo <x>` | Moves left until the next time control. Sent only when x > 0. **If `wtime`/`btime` arrive without `movestogo`, the game is sudden death** (with or without increment). |
| `depth <x>` | Search x plies only. |
| `nodes <x>` | Search x nodes only. |
| `mate <x>` | Search for a mate in x moves. |
| `movetime <x>` | Search exactly x ms. |
| `infinite` | Search until `stop`. **Don't exit the search without being told to.** |

Points the spec leaves open about `go`: whether limits may be combined
(e.g. `nodes` with `wtime`), what a bare `go` means, and whether a time
value can be negative or zero. The "unsent means unlimited" rule (L135)
implies a bare `go` searches without limit; that reading is our inference,
not explicit text (**UNVERIFIED**). Section 7 shows what the runners send.

## 4. Engine to GUI (L185-L313)

| Command | Syntax | What the spec says |
|---|---|---|
| `id` | `id name <x>` / `id author <x>` | Both must be sent in reply to `uci` (L188-L194). |
| `uciok` | `uciok` | Sent after `id` and any `option` lines: the engine is now in UCI mode (L196-L198). |
| `readyok` | `readyok` | Reply to `isready` once all earlier input has been processed and the engine can take new commands. Allowed at any time, including mid-search (L200-L205). Note: L205 literally says `readyok` "must always be answered with isready"; this is an evident wording slip, as L83 states the real rule (`isready` is answered with `readyok`). |
| `bestmove` | `bestmove <move1> [ponder <move2>]` | The search has ended and this is the move. The optional `ponder` move is the reply the engine would like to ponder on. **Every `go` needs exactly one `bestmove`**, including a ponder search ended by `stop`. The engine must not start pondering on its own. Just before `bestmove` the engine should send a final `info` line so the GUI has the complete statistics (L207-L213). |
| `copyprotection` | `copyprotection checking` then `copyprotection ok` / `error` | Optional, after `uciok`. On error the engine should keep running but work badly, and the GUI should not use it (L215-L228). Not relevant to Fork. |
| `registration` | `registration checking` then `registration ok` / `error` | Like copyprotection, but the GUI may still use an unregistered engine; it must reply with `register` (L230-L246). Not relevant to Fork. |
| `info` | `info <field> <value> ...` | See below (L248-L313). |
| `option` | `option name <id> type <t> [default <x>] [min <x>] [max <x>] [var <x>]...` | See section 5 (L316-L428). |

**No-legal-move case.** The spec says nothing about what `bestmove` should
contain when the root position has no legal move (mate or stalemate). Only
`0000` (null move, L49) is defined as a "no move" token. See section 7 for
how runners and python-chess behave.

### `info` fields (L248-L313)

General rules: send `info` whenever something changes; one line may carry
one field or many; **everything that belongs to a PV goes on one line**
(the spec's example has depth, score, time, nodes, nps and pv together).
The spec suggests holding back `currmove`, `currmovenumber`, `currline`
and `refutation` until about one second into the search, to limit
traffic (L255-L256).

| Field | Meaning |
|---|---|
| `depth <x>` | Search depth in plies. |
| `seldepth <x>` | Selective depth in plies. If sent, `depth` must be on the same line. |
| `time <x>` | Search time so far in ms; should accompany the `pv`. |
| `nodes <x>` | Nodes searched; send regularly. |
| `pv <m1> ... <mi>` | Best line found. |
| `multipv <num>` | Line number in multi-PV mode; the best line carries `multipv 1`. In k-best mode all k lines are sent together. |
| `score cp <x>` | Score in centipawns **from the engine's point of view** (side to move). |
| `score mate <y>` | Mate in y **moves, not plies**; negative when the engine is being mated. `mate 0` is not addressed. |
| `score ... lowerbound` / `upperbound` | The score is only a bound (e.g. after a fail-high or fail-low). |
| `currmove <move>` | Root move now being searched. |
| `currmovenumber <x>` | Its index; the first move is 1, not 0. |
| `hashfull <x>` | Hash fill in permille; send regularly. |
| `nps <x>` | Nodes per second; send regularly. |
| `tbhits <x>` | Positions found in endgame tablebases. |
| `sbhits <x>` | Positions found in Shredder endgame databases. |
| `cpuload <x>` | CPU usage in permille. |
| `string <str>` | Free text for display; **the rest of the line is the string**, so it must come last. |
| `refutation <m1> <m2> ... <mi>` | Move m1 is refuted by the line m2...mi (i >= 1); `refutation <m1>` alone means none found. Only when `UCI_ShowRefutations` is true. |
| `currline <cpunr> <m1> ... <mi>` | Line currently being searched; `cpunr` (1, 2, ...) may be omitted on a single CPU; with several CPUs send all lines together. Only when `UCI_ShowCurrLine` is true. |

Not in the 2006 spec but parsed by tools: python-chess v1.11.2 also reads
`info ... wdl <w> <d> <l>` and `ebf <x>` (see section 7). These are
extensions; Fork may emit `wdl` only behind its own decision (not needed
for TCEC).

## 5. Options (L316-L428)

- Sent once after `uci` and `id`, one line per option. The GUI builds a
  settings dialog from them; some options (e.g. `Ponder`,
  `UCI_AnalyseMode`) are handled automatically rather than shown. **The GUI
  need not send `setoption` for options it leaves at the default**
  (L323-L325), so Fork's defaults must be the values it should play with.
- The spec lists the allowed token combinations only through examples
  (L326-L327, L422-L428).

### Types (L400-L413)

| Type | Value | Example line in the spec's format |
|---|---|---|
| `check` | `true` / `false` | `option name Nullmove type check default true` |
| `spin` | an integer between `min` and `max` | `option name Selectivity type spin default 2 min 0 max 4` |
| `combo` | one of the listed `var` strings | `option name Style type combo default Normal var Solid var Normal var Risky` |
| `button` | no value; pressing it sends a command | `option name Clear Hash type button` |
| `string` | free text; the empty string is written `<empty>` | `option name NalimovPath type string default <empty>` |

Keywords: `default <x>`, `min <x>`, `max <x>`, `var <x>` (repeatable,
one per predefined combo value). `spin` is integer-only in the spec, so
non-integer tunables have to be exposed some other way (tools.md notes
that SPSA tools use `string` options for floats).

### Option names with fixed meaning (L329-L398, L524-L531)

Names with fixed semantics carry the `UCI_` prefix, except the first six
below. A GUI should ignore (not display) unknown `UCI_` options (L335-L337).

| Name | Type | Meaning |
|---|---|---|
| `Hash` | spin | Hash table memory in **MB**. "Should be supported by all engines." The GUI should send it as the first `setoption` at boot if the engine declared it, so the engine should start with a very small hash by default (L338-L343). |
| `NalimovPath` | string | Path(s) to Nalimov tablebases; several directories joined with `;` (L344-L346). |
| `NalimovCache` | spin | Nalimov cache size in MB (L347-L350). |
| `Ponder` | check | The engine can ponder. The GUI sets it when pondering is turned on or off. It does **not** tell the engine to ponder by itself; it exists so time management can adapt when pondering is allowed (L351-L355). L333 calls it "Pondering", a naming slip in the same text. |
| `OwnBook` | check | The engine has its own book; when set, the GUI never plays book moves for it; when false, the engine must not use its book (L356-L360). |
| `MultiPV` | spin | Multi-PV / k-best mode; default 1 (L361-L362). |
| `UCI_ShowCurrLine` | check, default false | Engine may send `info currline` (L363-L364). |
| `UCI_ShowRefutations` | check, default false | Engine may send `info refutation` (L365-L366; the text calls the field "refutations"). |
| `UCI_LimitStrength` | check, default false | Engine can play at a reduced Elo; implement together with `UCI_Elo` (L367-L369). |
| `UCI_Elo` | spin | Target Elo, used only when `UCI_LimitStrength` is true (L370-L374). |
| `UCI_AnalyseMode` | check | False when playing a game, true when analysing; lets the engine behave differently (e.g. learning only in games) (L375-L378). |
| `UCI_Opponent` | string | Opponent info in the form `[GM\|IM\|FM\|WGM\|WIM\|none] [<elo>\|none] [computer\|human] <name>` (L379-L385). |
| `UCI_EngineAbout` | string | Engine's "about" text, e.g. a licence notice; the GUI normally shouldn't change it (L386-L390). |
| `UCI_ShredderbasesPath` | string | Folder or file of Shredder endgame databases (L391-L393). |
| `UCI_SetPositionValue` | string | GUI tells the engine to use a given value (centipawns, **White's** point of view) for a specific position. Formats: `<value> + <fen>`, `clear + <fen>`, `clearall` (L394-L398). |
| `UCI_Chess960` | check, default false | Present in this version as an appended section, not in the main option list. An engine that knows Chess960 declares it; the GUI sets it true for Chess960 games. Castling then uses king-takes-rook notation, and FEN castling rights use rook file letters (upper case White, lower case Black), e.g. `... w AHah -` (L521-L543). |

**Not defined by the spec:** `Threads`, `SyzygyPath`, `Move Overhead` /
`MoveOverhead`, `Clear Hash` (only an example button name), `UCI_Variant`.
These are de facto conventions. TCEC sets `Threads`, `Hash` and
`SyzygyPath` and leaves other options at their defaults unless the author
asks (one engine runs with `MoveOverhead=1000`); see competition.md. Fork's
exact spelling for its overhead option is a Phase 2/5 decision. Both
runners match option names exactly (see section 7), so the name Fork
declares is the name TCEC must type.

## 6. Timing rules and the boot sequence

Collected from the text:

1. No searching or pondering before `go` (L27-L28).
2. Answer `isready` at once, even mid-search, without stopping (L83-L84).
3. Exactly one `bestmove` per `go`, including after `stop` in ponder mode
   (L210-L211); `stop` must lead to `bestmove` "as soon as possible"
   (L174-L175).
4. In `ponder` and `infinite` modes the engine must not end the search on
   its own (L142, L171). If a ponder or infinite search runs out of
   things to do (e.g. it found a mate, or hit a depth cap), it must keep
   waiting for `stop`/`ponderhit` before printing `bestmove`.
5. A final `info` line right before `bestmove` (L212-L213).
6. Hold `currmove`/`currmovenumber`/`currline`/`refutation` for about the
   first second (L255-L256). `nodes`, `nps` and `hashfull` should be sent
   "regularly" (no interval is given).
7. `setoption` only arrives while idle (L89).

The boot example (L435-L517): `uci` -> `id name`, `id author`, `option`
lines -> `uciok`; then `setoption` lines (hash first); then `isready` ->
`readyok` (the comment marks this pair as required); then `ucinewgame`,
optionally `setoption name UCI_AnalyseMode value true`, `position
startpos moves e2e4 e7e5`, `go infinite`; info lines; `stop` -> `bestmove
g1f3 ponder d8f6`.

## 7. Gaps in the spec and how runners handle them

Read from source at the pinned versions in tools.md. These describe tool
behaviour, not protocol rules. Tags: fastchess (MIT) **USE**; cutechess
(GPLv3+) and python-chess (GPL-3.0+) **REFERENCE ONLY** for what is read
here (they remain USE as tools, never linked into Fork).

**fastchess v1.8.2-alpha** (`app/src/engine/uci_engine.cpp`,
`app/src/matchmaking/match/match.cpp`, `app/src/engine/option/*.hpp`):
- **Per game:** sends the configured options with `Threads` moved to the
  front, then `setoption name UCI_Chess960 value true` for FRC, then
  `ucinewgame` followed by `isready`, with its own timeout for the reply.
- **Per move:** before writing `position`, it sends `isready` and treats a
  missing `readyok` as a stall or crash; it then sends `position` with
  `startpos` or `fen ...` plus `moves` only if there are moves. It checks
  for game end (mate, stalemate, repetition, 50 moves) and adjudication
  *before* asking for a move, so in a fastchess game Fork is never sent
  `go` in a position with no legal move.
- **`go` line:** `nodes` and `depth` are written first if configured.
  With a fixed time per move it sends only `movetime` (plus those limits).
  Otherwise `wtime`/`btime`, `winc`/`binc` only when the clock has an
  increment, and `movestogo` for moves-based controls. So limits *can* be
  combined with clock arguments.
- **`bestmove`:** it waits for a line starting with `bestmove`, takes the
  next token, and checks it against the legal moves; anything illegal or
  unparsable (including `0000` or `(none)` in a live game) is scored as an
  illegal-move loss. If the engine overruns its clock, fastchess sends
  `stop` and waits up to 10 s for `bestmove`.
- **Score used for adjudication:** the most recent `info` line that has
  ` score ` and is not `info string` (and is `multipv 1` when multipv is
  present), preferring an exact score over a bound.
- **PV checks (warnings):** illegal PV moves, PVs that continue past mate,
  stalemate, threefold or the 50-move rule, a `bestmove` that differs from
  the first PV move of the last scored `info` line (multipv 1; no check
  if that line is a bound), and (when enabled)
  mate-PV length: it expects `mate N` with N > 0 to have 2N-1 plies and
  N < 0 to have -2N plies, ending in checkmate.
- **Latency:** wall time from `go` to `bestmove` minus the last reported
  `info ... time`.
- **Options:** option names are matched **case-sensitively** (plain string
  compare), unlike the spec's "should not be case sensitive". An unknown
  name, or a `spin` value outside `[min, max]`, is not sent (a warning is
  printed). A `button` is sent as `setoption name <id>` with no value.
  `combo` `var` values are split on whitespace, so combo values with
  spaces don't survive. A `string` default is the rest of the line.
  `spin` also accepts non-integer min/max/default (a fastchess extension).
- **Compliance mode** checks are listed in tools.md.

**cutechess v1.5.1** (`projects/lib/src/uciengine.cpp`):
- **New game:** `debug on` if enabled, `ucinewgame`, then `setoption` for
  `Ponder` (if declared) and `UCI_Opponent` as `none none computer|human
  <name>` (if declared), then `position`.
- **`go` line:** `go ponder` when pondering; `go infinite` only for an
  infinite control with no ply/node limit; fixed time per move as
  `movetime`; otherwise `wtime` and `btime` always, `winc`/`binc` only
  when > 0, `movestogo` only when > 0; then `depth`/`nodes` appended.
- **Scores:** `cp` is used as is; `mate N` is turned into a large internal
  score depending on N's sign; `mate 0` falls through as 0; a score with
  `lowerbound` or `upperbound` is **ignored** (not recorded).
- **`bestmove`:** an unparsable or illegal move forfeits the game; a
  `bestmove` received while the engine is not thinking is logged as
  unexpected; a `bestmove` during pondering is warned as premature. The
  ponder move is used only if the engine declared `Ponder`.
- **Options:** `UCI_*` options are hidden except `UCI_LimitStrength` and
  `UCI_Elo`; `UCI_Chess960` (and other `UCI_<variant>` names) are taken
  as variant support; `Ponder` marks ponder support. `registration error`
  is answered with `register later`.
- **Game end before `go`** (resolved 2026-10-24 from
  `projects/lib/src/chessgame.cpp` at tag v1.5.1): after every move,
  `ChessGame::onMoveMade` asks the board for a result (and then the
  adjudicator) and only calls `startTurn`, which sends `go`, when there is
  no result; forced opening moves are checked the same way in `startGame`.
  One gap: if the game *starts* from a FEN that is already mate or
  stalemate and no opening moves are played, `startGame` calls `startTurn`
  without a check, so the engine would get `go` in a finished position.
  Source: https://raw.githubusercontent.com/cutechess/cutechess/v1.5.1/projects/lib/src/chessgame.cpp

**python-chess v1.11.2** (`chess/engine.py`; Fork's difftest and scripts
use it):
- `bestmove (none)` and `bestmove NULL` are read as "no move"; the same
  tokens after `ponder` mean no ponder move. Comments in the code name
  engines that send `NULL` or uppercase promotion letters, which it
  lowercases.
- It sends `searchmoves 0000` when asked to search an empty move list.
- When it sends `go`, `wtime`, `btime`, `movetime`, `depth`, `nodes` and
  `mate` are clamped to at least 1; `movestogo` is sent only when > 0.

**Implications for Fork's Phase 2 spec** (our reading, to be decided in
DESIGN.md):
- Accept limits in any order and in combination; handle `wtime` without
  `btime` (fastchess compliance sends `go wtime 100` alone).
- Answer `isready` from the input thread at any time.
- Print a final exact-score `info` line (with `score`, `time`, `nodes`,
  `pv`) before every `bestmove`, with `bestmove` equal to the PV's first
  move; fastchess compliance requires the last info line to carry a
  score, and fastchess takes adjudication scores and latency (`time`)
  from the latest `info` lines.
- For a root with no legal move, the spec defines nothing. `0000` is the
  only token the spec defines; python-chess also accepts `(none)`. Pick
  one, document it, and test it, but note that neither runner should ask
  for one in a normal game (fastchess confirmed; cutechess confirmed
  2026-10-24 except for a start FEN that is already finished, see above).
- Declare option names exactly as TCEC will type them; don't rely on case
  folding by the runner, but still fold case when parsing `setoption`, as
  the spec asks.

## UNVERIFIED items

- Redistribution terms of `engine-interface.txt` itself (no notice in the
  file; only the Shredder page's "open, no licence fees" statement).
- That promotion letters other than `q` are lowercase `n b r` (the spec
  shows only `e7e8q`; runners and python-chess were not checked for
  uppercase rejection beyond python-chess lowercasing).
- What a bare `go` (no sub-arguments) should do; "unlimited" is inferred
  from L135.
- ~~Whether cutechess v1.5.1 avoids sending `go` in a finished position.~~
  Resolved 2026-10-24 (section 7, cutechess): it does, except when the
  start FEN itself is finished.
- Which match runner and version TCEC's servers use (open question in
  competition.md); runner behaviour above is for fastchess and stock
  cutechess only.
