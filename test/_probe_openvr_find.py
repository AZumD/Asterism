#!/usr/bin/env python3
"""Minimal OpenVR overlay init + FindOverlay only (no place yet)."""
from __future__ import annotations

import ctypes
import os
from ctypes import POINTER, Structure, byref, c_char_p, c_int, c_uint32, c_uint64, c_void_p

STEAMVR = os.environ.get("STEAMVR_ROOT", "/opt/steamvr")
LIB = f"{STEAMVR}/bin/linuxarm64/libopenvr_api.so"


class FnTable(Structure):
    _fields_ = [("fns", c_void_p * 128)]


def main() -> int:
    lib = ctypes.CDLL(LIB)
    lib.VR_InitInternal2.argtypes = [POINTER(c_int), c_int, c_char_p]
    lib.VR_InitInternal2.restype = c_uint32
    lib.VR_ShutdownInternal.argtypes = []
    lib.VR_GetGenericInterface.argtypes = [c_char_p, POINTER(c_int)]
    lib.VR_GetGenericInterface.restype = c_void_p
    lib.VR_IsInterfaceVersionValid.argtypes = [c_char_p]
    lib.VR_IsInterfaceVersionValid.restype = ctypes.c_bool

    for ver in (
        b"IVROverlay_029",
        b"IVROverlay_027",
        b"IVROverlay_026",
        b"IVROverlay_025",
        b"IVROverlay_024",
        b"IVROverlay_022",
        b"IVROverlay_021",
        b"IVROverlay_020",
        b"IVROverlay_019",
        b"IVROverlay_018",
    ):
        print("valid?", ver.decode(), lib.VR_IsInterfaceVersionValid(ver))

    err = c_int(0)
    print("init…", flush=True)
    token = lib.VR_InitInternal2(byref(err), 8, b"asterism-find-probe")
    print("init token", token, "err", err.value, flush=True)
    if err.value != 0:
        return 1

    try:
        for ver in (
            b"FnTable:IVROverlay_029",
            b"FnTable:IVROverlay_027",
            b"FnTable:IVROverlay_026",
            b"FnTable:IVROverlay_022",
            b"FnTable:IVROverlay_019",
        ):
            e2 = c_int(0)
            p = lib.VR_GetGenericInterface(ver, byref(e2))
            print(ver.decode(), "p", hex(p or 0), "err", e2.value, flush=True)
            if not p:
                continue
            ft = ctypes.cast(p, POINTER(FnTable)).contents
            print("  fn0", hex(ft.fns[0] or 0), "fn32", hex(ft.fns[32] or 0), "fn41", hex(ft.fns[41] or 0), flush=True)
            FindOverlay = ctypes.CFUNCTYPE(c_int, c_char_p, POINTER(c_uint64))(ft.fns[0])
            h = c_uint64(0)
            print("  calling FindOverlay…", flush=True)
            rc = FindOverlay(b"asterism.desktop.app.2", byref(h))
            print("  FindOverlay rc", rc, "handle", h.value, flush=True)
            break
    finally:
        print("shutdown", flush=True)
        lib.VR_ShutdownInternal()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
