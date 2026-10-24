# Fork KB: OS memory and stdin facts behind the Hash code (Phase 2)

Checks, against primary sources, of the operating-system behaviour that
Fork's `Hash` memory code (`src/search/hash_memory.{hpp,cpp}`) and the
Windows stdin set-up in `src/main.cpp` rely on. Several of these were first
written from memory; each claim below gets a verdict: **CONFIRMED**,
**WRONG** (with the correct statement) or **UNVERIFIED**. Verified
**2026-10-24**. Every page opened is logged in [sources.md](sources.md)
under "OS memory facts (os-memory.md)".

Source types used: the Linux man-pages project (man7.org, man-pages 6.19),
the Linux kernel tree on GitHub (`torvalds/linux`, `master` at commit
`5b0764a53235` on 2026-10-24, plus tags `v4.0`, `v4.19`, `v4.20`, `v5.0` to
`v5.3` where history mattered) and Microsoft Learn. These are OS
documentation and kernel source, not chess-engine code, so they raise no
originality issue.

- **Tag (whole file):** **USE.** These are platform facts Fork's own code
  depends on; no code is copied.
- **License:** man-pages and kernel documentation are used as reference
  only (nothing reproduced beyond short quotes); no license applies to Fork.
- **Why it matters for Fork:** Phase 2 (`Hash` option: allocation, refusal
  of sizes that do not fit, parallel clear; UCI stdin on Windows), Phase 3
  (the transposition table lives in this memory), Phase 6 (TCEC-sized
  `Hash`, up to 262144 MB per [competition.md](competition.md), on many
  threads).

---

## 1. Linux `/proc/meminfo` `MemAvailable`

| Claim | Verdict |
|---|---|
| Meaning: "an estimate of how much memory is available for starting new applications, without swapping" | **CONFIRMED** |
| Added in Linux 3.14 | **CONFIRMED** |
| Line format `MemAvailable:   <n> kB` | **CONFIRMED** |

- proc_meminfo(5) lists the field as "MemAvailable %lu (since Linux 3.14)"
  and describes it, word for word as Fork's comment quotes, as an estimate of
  the memory available for starting new applications without swapping. Its
  introduction says each line is a name, a colon, the value and an optional
  unit "(e.g., "kB")".
  https://man7.org/linux/man-pages/man5/proc_meminfo.5.html (man-pages
  6.19, 2026-02-08), read 2026-10-24.
- Kernel `Documentation/filesystems/proc.rst` gives the same description
  and adds how it is computed: from MemFree, SReclaimable, the file LRU
  lists and the per-zone low watermarks, allowing for page cache the system
  needs and slab that is not actually reclaimable. Its sample output shows
  `MemAvailable:   27214312 kB` (name, colon, padding spaces, decimal, `kB`).
  https://raw.githubusercontent.com/torvalds/linux/master/Documentation/filesystems/proc.rst,
  read 2026-10-24.
- The kernel commit that added the field,
  `34e431b0ae398fc54ea69ff85ec700722c9da773` ("/proc/meminfo: provide
  estimated available memory", committed 2014-01-22), is not in tag `v3.13`
  and is in tag `v3.14` (GitHub compare API: `v3.13...commit` "ahead",
  `v3.14...commit` "behind").
  https://api.github.com/repos/torvalds/linux/commits/34e431b0ae398fc54ea69ff85ec700722c9da773,
  read 2026-10-24.
- **Note on Fork's comment** (`hash_memory.cpp`, "free memory plus what
  the kernel can reclaim without swapping"): close, but the kernel calls it
  an *estimate*, and it subtracts the zone low watermarks and discounts page
  cache and slab that cannot really be reclaimed. Suggest "the kernel's
  estimate of memory available without swapping".
- **Parsing:** Fork reads the number after `MemAvailable:` with `strtoull`
  (which skips the padding) and multiplies by 1024. The unit is the literal
  `kB`; the man page does not define it further. That `kB` here means 1024
  bytes is **UNVERIFIED** from the documentation text (the kernel source
  that prints it was not read); it is the universal reading.

## 2. Linux overcommit, mode 0 (heuristic)

Fork's claim: "the heuristic checks each allocation on its own against RAM +
swap, so one huge mmap is refused, while many smaller mmaps that add up to
more can all succeed; the memory is only really committed when pages are
touched, so touching them can trigger the OOM killer".

| Part | Verdict |
|---|---|
| Mode 0 is heuristic and is the default | **CONFIRMED** |
| Each allocation is checked on its own against total RAM + swap | **CONFIRMED for Linux 5.2 and later.** Before 5.2 the per-allocation check was against an estimate of *currently free* memory plus swap (see below). |
| One huge mmap is refused; many smaller ones adding up to more can all succeed | **CONFIRMED** (follows from the source: mode 0 never compares against the running commit total) |
| Memory is "only really committed when touched" | **WRONG wording.** In Linux terms the mapping *is* committed (charged to `Committed_AS`) at mmap time even in mode 0; what is deferred is the *physical page allocation*, which happens on first touch. |
| Touching the pages can trigger the OOM killer | **CONFIRMED** |

- `Documentation/mm/overcommit-accounting.rst`: mode 0 refuses "obvious
  overcommits of address space", is meant to make a "seriously wild
  allocation" fail, and is the default. Mode 2 is the one that limits the
  *total* commit (swap plus a share of RAM, default 50%), and the doc says
  that mode is what keeps a process from being killed while it accesses
  pages. A private writable anonymous map costs its full size in the
  accounting.
  https://raw.githubusercontent.com/torvalds/linux/master/Documentation/mm/overcommit-accounting.rst,
  read 2026-10-24.
- `Documentation/admin-guide/sysctl/vm.rst`, `overcommit_memory`: with 0
  "the kernel compares the userspace memory request size against total
  memory plus swap and rejects obvious overcommits"; default 0; points to
  `mm/util.c::__vm_enough_memory()`.
  https://raw.githubusercontent.com/torvalds/linux/master/Documentation/admin-guide/sysctl/vm.rst,
  read 2026-10-24.
- `mm/util.c` (`master`), `__vm_enough_memory()`: it first adds the request
  to the commit counter (`vm_acct_memory(pages)`), then in
  `OVERCOMMIT_GUESS` (mode 0) fails only if `pages > totalram_pages() +
  total_swap_pages`, and otherwise returns success. The running total
  `vm_committed_as` is compared against a limit only in mode 2. So the test
  is per request, against *total* RAM plus *total* swap (not free memory).
  https://raw.githubusercontent.com/torvalds/linux/master/mm/util.c, read
  2026-10-24.
- History: in tags `v4.0` (`mm/mmap.c`), `v4.19`, `v4.20`, `v5.0` and `v5.1`
  (`mm/util.c`) the mode-0 branch instead summed free pages, file pages
  (minus shmem), free swap, reclaimable slab and reclaimable kernel memory,
  subtracted reserves, and accepted the request if that sum was larger. Tag
  `v5.2` has the current `totalram + total_swap` test. Either way the check
  is per request and ignores what is already committed, so Fork's design
  argument (chunks would each pass) holds on all of these kernels.
  https://raw.githubusercontent.com/torvalds/linux/v5.1/mm/util.c and
  https://raw.githubusercontent.com/torvalds/linux/v5.2/mm/util.c, read
  2026-10-24.
- OOM risk: proc_sys_vm(5) says that in mode 0 the default check "is very
  weak", which risks the process being "OOM-killed", and that mode 0 does
  not check mmap calls with `MAP_NORESERVE` at all.
  https://man7.org/linux/man-pages/man5/proc_sys_vm.5.html, read
  2026-10-24. mmap(2) BUGS: by default any process can be killed at any
  moment when the system runs out of memory.
  https://man7.org/linux/man-pages/man2/mmap.2.html, read 2026-10-24.
- That anonymous pages get physical memory only at first touch is not
  stated in so many words in the pages above. It is implied by the overcommit
  doc (mode 2 lets applications rely on allocations "without having to
  initialize every page"), vm.rst (programs that allocate a lot and use
  little) and transhuge.rst (one fault per 2M region "touched"). The kernel
  fault path itself was not read: **UNVERIFIED** as an explicit statement,
  well supported by inference.
- **Consequence for Fork's guard:** because mode 0 compares with *total*
  RAM + swap (5.2+), a request smaller than that passes mmap even when most
  RAM is in use. Fork's extra `MemAvailable` check before mmap is therefore
  the only thing standing between an oversized `Hash` and the OOM killer
  during the clear. This matches the comment in `hash_memory.hpp`.

## 3. `madvise(MADV_HUGEPAGE)` and transparent huge pages

| Claim | Verdict |
|---|---|
| Enables THP for the range | **CONFIRMED** |
| Needs `CONFIG_TRANSPARENT_HUGEPAGE` | **CONFIRMED** (without it the call fails with `EINVAL`) |
| Failure is harmless | **CONFIRMED for the no-THP-kernel case** from kernel source; other failure modes **UNVERIFIED** as an explicit doc statement |
| x86-64 THP (PMD) size is 2 MiB | **CONFIRMED** |
| The range needs 2 MiB alignment to get huge pages | **Partly WRONG.** The range itself need not be aligned (only `addr` must be page-aligned). Huge pages can only back 2 MiB-aligned 2 MiB blocks that lie entirely inside the mapping; aligning the mapping, as Fork does, lets every 2 MiB of it qualify. |

- madvise(2), `MADV_HUGEPAGE` (since Linux 2.6.38): enables THP for pages
  in the range; khugepaged scans marked areas to replace them with huge
  pages, and the kernel allocates huge pages directly when the region is
  naturally aligned to the huge page size. Since 5.4, replacement happens
  only "on hugepage-aligned boundaries". The operation is available only if
  the kernel was built with `CONFIG_TRANSPARENT_HUGEPAGE`. Errors: `EINVAL`
  if `addr` is not page-aligned or the advice is not valid. The man page
  also notes most common kernel configurations already give
  `MADV_HUGEPAGE`-style behaviour by default.
  https://man7.org/linux/man-pages/man2/madvise.2.html (man-pages 6.19,
  2026-02-08), read 2026-10-24.
- `mm/madvise.c` (`master`): `madvise_behavior_valid()` lists
  `MADV_HUGEPAGE` only under `#ifdef CONFIG_TRANSPARENT_HUGEPAGE`, and the
  syscall returns `-EINVAL` on an invalid behaviour before touching any
  mapping. So on a kernel without THP the call fails and the mapping is
  unchanged.
  https://raw.githubusercontent.com/torvalds/linux/master/mm/madvise.c, read
  2026-10-24.
- `include/linux/huge_mm.h` (`master`), `thp_vma_suitable_order()`: for an
  anonymous mapping a huge page at a fault address is allowed only if the
  address rounded down to the huge page size, plus that size, lies inside
  the VMA. This is the alignment rule above.
  https://raw.githubusercontent.com/torvalds/linux/master/include/linux/huge_mm.h,
  read 2026-10-24.
- x86-64 size: `arch/x86/include/asm/pgtable_64_types.h` defines
  `PMD_SHIFT 21` (`PMD_SIZE` = 2 MiB); `hugetlbpage.rst` says x86 CPUs
  normally support 4K and 2M pages (1G where available); transhuge.rst
  presumes a 2M huge page in its examples, says it varies by architecture,
  and points to `/sys/kernel/mm/transparent_hugepage/hpage_pmd_size` for
  the real value. Links:
  https://raw.githubusercontent.com/torvalds/linux/master/arch/x86/include/asm/pgtable_64_types.h,
  https://raw.githubusercontent.com/torvalds/linux/master/Documentation/admin-guide/mm/hugetlbpage.rst,
  https://raw.githubusercontent.com/torvalds/linux/master/Documentation/admin-guide/mm/transhuge.rst,
  all read 2026-10-24.
- transhuge.rst, sysfs: THP for anonymous memory can be `always`,
  `madvise` (only inside `MADV_HUGEPAGE` regions) or `never`; the default
  `defrag` setting is `madvise` (direct reclaim only for advised regions).
  So `MADV_HUGEPAGE` matters most on systems set to `madvise`, and it also
  makes the kernel try harder (reclaim/compaction) on `always` systems.
  Modern kernels also support smaller "multi-size THP" (mTHP), off by
  default for non-PMD sizes.
- What this means for Fork's "failure is fine" comment: the documented
  failure modes (`EINVAL`, `ENOMEM` for an unmapped range) leave the
  mapping usable; the call only adds a flag to the VMA. A doc sentence
  saying "a failed `MADV_HUGEPAGE` changes nothing" was not found:
  **UNVERIFIED** in those words.
- Not checked: whether recent kernels already align large anonymous
  mappings to 2 MiB on their own (which would make Fork's trim a no-op).
  **UNVERIFIED**; Fork's over-allocate-and-trim works either way.

## 4. Windows `VirtualAlloc`, `VirtualFree`, `GlobalMemoryStatusEx`

| Claim | Verdict |
|---|---|
| `MEM_RESERVE \| MEM_COMMIT` charges commit (RAM + page files) | **CONFIRMED** |
| The commit limit is system-wide and cumulative across allocations | **CONFIRMED** |
| Returns `NULL` on failure | **CONFIRMED** |
| Pages are zero-initialised | **CONFIRMED** |
| `VirtualFree(p, 0, MEM_RELEASE)` frees the whole allocation | **CONFIRMED** (size must be 0, `p` the base returned by `VirtualAlloc`) |
| `ullAvailPhys` = physical memory available now | **CONFIRMED**, with detail: it is the standby + free + zero lists, i.e. memory reusable without writing to disk first |

- VirtualAlloc: memory it allocates "is automatically initialized to
  zero"; `MEM_COMMIT` takes charges from the overall size of memory and the
  paging files and guarantees zero contents on first access, while physical
  pages are not allocated until the addresses are accessed; `MEM_COMMIT |
  MEM_RESERVE` reserves and commits in one step; on failure the return is
  `NULL` (details from `GetLastError`).
  https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualalloc
  (ms.date 2024-02-05), read 2026-10-24.
- VirtualFree: with `MEM_RELEASE`, `dwSize` must be 0 and `lpAddress` the
  base returned by `VirtualAlloc`; the whole region is released; the call
  fails otherwise. Nonzero return on success, 0 on failure.
  https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualfree
  (ms.date 2024-02-05), read 2026-10-24.
- Commit limit: the page-file article says the system commit limit is the
  sum of physical memory and all page files, and the commit charge is the
  total committed memory of everything on the system; when the charge
  reaches the limit, processes may not get committed memory. It adds that
  system-managed page files grow automatically when the charge reaches 90%
  of the limit (if disk space allows), so the limit is not fixed.
  https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file
  (ms.date 2026-02-12), read 2026-10-24. "Page State": committed pages are
  charged against RAM plus paging files and loaded into physical memory
  only at first access.
  https://learn.microsoft.com/en-us/windows/win32/memory/page-state
  (ms.date 2018-05-31), read 2026-10-24. "Reserving and Committing Memory":
  pre-committing a very large allocation can run the system out of
  committable pages and make virtual memory allocations fail.
  https://learn.microsoft.com/en-us/windows/win32/memory/reserving-and-committing-memory
  (ms.date 2018-05-31), read 2026-10-24.
- "Memory Limits for Windows and Windows Server Releases": a 64-bit
  process on x64 Windows 8.1 / Server 2012 R2 or later has 128 TB of
  user-mode virtual address space (8 TB on earlier releases), far above
  any `Hash` size. (The "or system commit limit, whichever is smaller"
  wording on that page is about the kernel's paged pool, not user
  allocations.)
  https://learn.microsoft.com/en-us/windows/win32/memory/memory-limits-for-windows-releases
  (ms.date 2025-06-11), read 2026-10-24.
- MEMORYSTATUSEX: `ullAvailPhys` is the physical memory currently
  available, reusable without first writing it to disk, the sum of the
  standby, free and zero lists. `ullAvailPageFile` is the most memory the
  current process can commit (at most the system-wide available commit).
  `dwLength` must be set before the call.
  https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/ns-sysinfoapi-memorystatusex
  (ms.date 2018-12-05), read 2026-10-24.
- GlobalMemoryStatusEx: nonzero on success, zero on failure; the figures
  are volatile; `ullAvailPhys` covers all NUMA nodes.
  https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-globalmemorystatusex
  (ms.date 2018-12-05), read 2026-10-24.
- **Consequence for Fork:** on Windows, whether `VirtualAlloc` succeeds is
  decided by commit (what `ullAvailPageFile` reports), not by
  `ullAvailPhys`. Fork's `ullAvailPhys` guard is a separate policy check
  (do not make the table bigger than free RAM, to avoid paging). A size can
  pass it and still get `NULL` from `VirtualAlloc` when commit is short; the
  code handles `NULL`. Unlike Linux mode 0, once `VirtualAlloc` commits, the
  docs guarantee the memory on access; no OOM-killer equivalent applies.
  Whether a commit request that exceeds the current limit waits for the
  page file to grow or fails at once is **UNVERIFIED** (not stated).

## 5. Windows CRT text mode and `_setmode`

| Claim | Verdict |
|---|---|
| `_setmode(_fileno(stdin), _O_BINARY)` switches stdin to untranslated mode | **CONFIRMED** (the doc's own example does exactly this) |
| Text mode turns CR-LF into LF on input | **CONFIRMED** |
| Text mode treats Ctrl-Z (0x1A) as end of file on input | **CONFIRMED** (doc says "CTRL+Z"; the byte value 0x1A is the ASCII SUB code, not restated in these pages) |
| stdin starts in text mode | **CONFIRMED** |

- `_setmode`: `_O_TEXT` is translated mode, where CR-LF pairs become a
  single LF on input and LF becomes CR-LF on output; `_O_BINARY` suppresses
  those translations. Returns the previous mode, or -1 with `errno`
  (`EBADF`/`EINVAL`) after the invalid-parameter handler. Call it before any
  input or output on the stream (flush first if anything was written).
  Header `<io.h>`, with `<fcntl.h>` for the constants. The example sets
  stdin to binary with `_setmode(_fileno(stdin), _O_BINARY)`.
  https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/setmode
  (ms.date 2020-04-02), read 2026-10-24.
- fopen, mode `t`: CR-LF becomes LF on input, LF becomes CR-LF on output,
  and CTRL+Z is taken as end of file on input; `b` suppresses the CR/LF
  translations.
  https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/fopen-wfopen
  (ms.date 2023-04-27), read 2026-10-24.
- `_read`: in text mode a read stops at CTRL+Z, which is treated as end of
  file, and CR-LF pairs are returned as LF.
  https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/read
  (ms.date 2020-04-02), read 2026-10-24.
- "Text and binary mode file I/O": stdin, stdout and stderr always open in
  text mode by default; `_setmode` changes the mode of an open descriptor.
  https://learn.microsoft.com/en-us/cpp/c-runtime-library/text-and-binary-mode-file-i-o
  (ms.date 2018-04-11), read 2026-10-24.
- `_fileno`: returns the descriptor of a stream; stdin is descriptor 0 in
  the doc's example.
  https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/fileno
  (ms.date 2020-04-02), read 2026-10-24.
- **Caveats:** these pages document Microsoft's CRT (UCRT). Fork's Windows
  builds use LLVM-MinGW and MinGW GCC; which CRT each toolchain links
  (UCRT or the older `msvcrt.dll`) and whether `msvcrt.dll` behaves the same
  is **UNVERIFIED** here. The Ctrl-Z rule is documented for text-mode files
  and `_read`; that it applies to a pipe on stdin is an inference from
  "stdin opens in text mode" plus `_read`'s rule, not a separate statement.
  Fork's call order (only `forkeng::init()` runs before `_setmode`, and the
  UCI path does no stdin I/O before it) satisfies the "before any I/O" rule.

## 6. Linux `mmap` / `munmap`

| Claim | Verdict |
|---|---|
| `MAP_PRIVATE \| MAP_ANONYMOUS` memory is zero-filled | **CONFIRMED** |
| Failure returns `MAP_FAILED` | **CONFIRMED** (`(void *) -1`, with `errno`) |
| `munmap` of a page-aligned sub-range is allowed | **CONFIRMED** |

- mmap(2): `MAP_ANONYMOUS` mappings are not file-backed and their contents
  "are initialized to zero"; `fd` should be -1 for portability and offset
  0. On error mmap returns `MAP_FAILED`, that is `(void *) -1`. munmap
  deletes the mappings for the given address range; `addr` must be a
  multiple of the page size (length need not be); every page containing
  part of the range is unmapped; it is not an error if the range holds no
  mapped pages. munmap returns 0 on success, -1 on failure. With `addr`
  NULL the kernel picks a page-aligned address.
  https://man7.org/linux/man-pages/man2/mmap.2.html (man-pages 6.19,
  2026-03-19), read 2026-10-24.
- Fork's trim (`munmap(start, head)` and `munmap(aligned + bytes, tail)`)
  uses page-aligned addresses: `start` is page-aligned (kernel-chosen),
  `head` is a difference of a 2 MiB multiple and a page-aligned address, and
  `aligned + bytes` is 2 MiB-aligned plus a whole number of MiB. So both
  calls meet the rule.

---

## Fork code comments the sources contradict or qualify

1. `hash_memory.cpp`, `available_memory()`: "free memory plus what the
   kernel can reclaim without swapping" is a loose paraphrase; the kernel
   calls MemAvailable an *estimate* that also subtracts low watermarks and
   discounts unreclaimable cache/slab. Not wrong in spirit; suggest
   rewording.
2. The overcommit reasoning in `hash_memory.hpp` ("Linux checks each mmap
   against RAM + swap on its own") is right for Linux 5.2+; on older kernels
   the per-request check was against current free memory + swap. The
   conclusion (chunks slip past) holds on both. If the design note or a
   comment says memory is "only committed when touched", that is the wrong
   term: commit accounting happens at mmap; physical allocation happens at
   first touch.
3. `hash_memory.hpp` "2 MiB aligned on Linux, where transparent huge pages
   are requested": fine. If any comment or doc claims alignment is
   *required* for `MADV_HUGEPAGE` to work at all, that is too strong; the
   kernel uses huge pages for every aligned 2 MiB block inside the range,
   and alignment just makes the whole table eligible.
4. `hash_memory.hpp` "A size is tried only if it fits in the physical memory
   available now ... so an overcommitted mmap never reaches the clear":
   true for Linux. On Windows, `VirtualAlloc` success depends on commit
   (`ullAvailPageFile`), not `ullAvailPhys`; the physical check is extra
   policy, and Windows does not overcommit, so the clear cannot be
   OOM-killed there anyway.
5. `main.cpp`'s stdin comment matches the Microsoft docs (CR-LF
   translation and Ctrl-Z end-of-file in text mode), subject to the
   MinGW CRT caveat in section 5.

## UNVERIFIED items

- That the `kB` unit in `/proc/meminfo` means 1024 bytes (not stated in the
  man page or proc.rst; the printing code was not read).
- An explicit kernel-doc statement that anonymous pages receive physical
  memory only on first touch (well supported by inference from three docs;
  the fault-path source was not read).
- A doc sentence stating that a failed `MADV_HUGEPAGE` leaves the mapping
  unchanged (the no-THP case is confirmed from `mm/madvise.c`; other error
  paths not traced).
- Whether current kernels align large anonymous mmaps to 2 MiB by
  themselves (not checked; irrelevant to correctness).
- Whether a Windows commit request beyond the current limit waits for a
  system-managed page file to grow or fails immediately.
- Which C runtime Fork's MinGW toolchains link (UCRT or `msvcrt.dll`) and
  whether `msvcrt.dll` has the same text-mode rules; whether Ctrl-Z ends
  input on a pipe (inferred, not stated).
- The kernel version on TCEC's servers (relevant to section 2's pre/post
  5.2 difference); not documented in any source read here.
