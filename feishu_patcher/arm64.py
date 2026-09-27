"""Small ARM64 helpers used to locate string references and function prologues."""

from __future__ import annotations

import struct


RET = bytes.fromhex("c0035fd6")


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def decode_adrp(instruction: int, pc: int) -> tuple[int, int] | None:
    if instruction & 0x9F000000 != 0x90000000:
        return None
    immlo = (instruction >> 29) & 0x3
    immhi = (instruction >> 5) & 0x7FFFF
    delta = sign_extend((immhi << 2) | immlo, 21) << 12
    return instruction & 0x1F, (pc & ~0xFFF) + delta


def decode_adr(instruction: int, pc: int) -> tuple[int, int] | None:
    if instruction & 0x9F000000 != 0x10000000:
        return None
    immlo = (instruction >> 29) & 0x3
    immhi = (instruction >> 5) & 0x7FFFF
    delta = sign_extend((immhi << 2) | immlo, 21)
    return instruction & 0x1F, pc + delta


def decode_add_immediate(instruction: int) -> tuple[int, int, int] | None:
    if instruction & 0x7F000000 != 0x11000000:
        return None
    destination = instruction & 0x1F
    source = (instruction >> 5) & 0x1F
    immediate = (instruction >> 10) & 0xFFF
    if (instruction >> 22) & 1:
        immediate <<= 12
    return destination, source, immediate


def is_stack_allocation_prologue(instruction: int) -> bool:
    return instruction & 0xFFC003FF == 0xD10003FF


def find_string_xrefs(
    data: bytes,
    target: int,
    text_address: int,
    text_offset: int,
    text_size: int,
) -> list[int]:
    """Return virtual addresses of ADR/ADRP+ADD references to ``target``."""
    xrefs: set[int] = set()
    end = text_offset + text_size
    for file_offset in range(text_offset, end, 4):
        instruction = struct.unpack_from("<I", data, file_offset)[0]
        pc = text_address + file_offset - text_offset
        adr = decode_adr(instruction, pc)
        if adr and adr[1] == target:
            xrefs.add(pc)
        adrp = decode_adrp(instruction, pc)
        if not adrp:
            continue
        page_register, page = adrp
        if page != target & ~0xFFF:
            continue
        for distance in range(1, 9):
            next_offset = file_offset + distance * 4
            if next_offset >= end:
                break
            decoded = decode_add_immediate(struct.unpack_from("<I", data, next_offset)[0])
            if decoded and decoded[1] == page_register and page + decoded[2] == target:
                xrefs.add(pc)
                break
    return sorted(xrefs)


def nearest_function_start(
    data: bytes,
    xref_address: int,
    text_address: int,
    text_offset: int,
    max_back: int = 0x2000,
) -> int | None:
    xref_offset = text_offset + xref_address - text_address
    lower = max(text_offset, xref_offset - max_back)
    for file_offset in range(xref_offset & ~3, lower - 1, -4):
        instruction = struct.unpack_from("<I", data, file_offset)[0]
        if is_stack_allocation_prologue(instruction):
            return text_address + file_offset - text_offset
    return None
