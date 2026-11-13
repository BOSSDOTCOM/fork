// SPDX-License-Identifier: GPL-3.0-or-later

#include "datagen/game_fibers.hpp"

#include <sys/mman.h>
#include <unistd.h>

#include <cstdint>

#if !defined(__x86_64__) || defined(_WIN32)
#error "game_fibers is written for x86-64 System V (Linux) only"
#endif

// forkeng_fiber_switch(save = rdi, next = rsi): pushes the registers a call
// preserves, stores the stack pointer, loads the other one and pops that
// context's registers; its `ret` resumes the other context where it last
// called this switch. forkeng_fiber_start is where a prepared stack first
// "returns" to: it calls entry (r13) with arg (r12) and traps if entry ever
// returns. Source of the register and alignment rules: the System V x86-64
// psABI, x86-64-ABI/low-level-sys-info.tex (gitlab.com/x86-psABIs/x86-64-ABI,
// master, read 2026-11-13): rbx, rbp, rsp and r12-r15 callee-saved, as are
// MXCSR's control bits and the x87 control word; at a function's entry
// rsp + 8 is a multiple of 16.
asm(R"(
  .text
  .globl forkeng_fiber_switch
  .type forkeng_fiber_switch, @function
  .p2align 4
forkeng_fiber_switch:
  pushq %rbp
  pushq %rbx
  pushq %r12
  pushq %r13
  pushq %r14
  pushq %r15
  movq %rsp, (%rdi)
  movq %rsi, %rsp
  popq %r15
  popq %r14
  popq %r13
  popq %r12
  popq %rbx
  popq %rbp
  ret
  .size forkeng_fiber_switch, .-forkeng_fiber_switch

  .globl forkeng_fiber_start
  .type forkeng_fiber_start, @function
  .p2align 4
forkeng_fiber_start:
  movq %r12, %rdi
  callq *%r13
  ud2
  .size forkeng_fiber_start, .-forkeng_fiber_start
)");

extern "C" void forkeng_fiber_start();

namespace forkeng {

FiberStack::~FiberStack() {
  if (base_) munmap(base_, bytes_);
}

bool FiberStack::map(std::size_t bytes) {
  const auto page = static_cast<std::size_t>(sysconf(_SC_PAGESIZE));
  const std::size_t total = (bytes + page - 1) / page * page + page;
  void* p = mmap(nullptr, total, PROT_READ | PROT_WRITE,
                 MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_STACK, -1, 0);
  if (p == MAP_FAILED) return false;
  if (mprotect(p, page, PROT_NONE) != 0) {  // the guard page, below the stack
    munmap(p, total);
    return false;
  }
  base_ = p;
  bytes_ = total;
  return true;
}

void* FiberStack::prepare(void (*entry)(void*), void* arg) {
  // The frame forkeng_fiber_switch pops: r15, r14, r13 = entry, r12 = arg,
  // rbx, rbp = 0 (the end of the frame chain), then the return address
  // forkeng_fiber_start. After its `ret` the stack pointer is 16-aligned, so
  // the stub's call enters `entry` aligned as the ABI requires.
  const std::uintptr_t top = (reinterpret_cast<std::uintptr_t>(base_) + bytes_) & ~std::uintptr_t{15};
  auto* frame = reinterpret_cast<std::uintptr_t*>(top - 9 * sizeof(std::uintptr_t));
  frame[0] = 0;
  frame[1] = 0;
  frame[2] = reinterpret_cast<std::uintptr_t>(entry);
  frame[3] = reinterpret_cast<std::uintptr_t>(arg);
  frame[4] = 0;
  frame[5] = 0;
  frame[6] = reinterpret_cast<std::uintptr_t>(&forkeng_fiber_start);
  frame[7] = 0;
  frame[8] = 0;
  return frame;
}

}  // namespace forkeng
