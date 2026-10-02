#!/usr/bin/env python3
"""Probe place after float dance (OpenVR init only for place)."""
from __future__ import annotations

import ctypes
import math
import os
import subprocess
import time
from ctypes import POINTER, Structure, byref, c_bool, c_char_p, c_float, c_int, c_uint32, c_uint64, c_void_p

STEAMVR = os.environ.get("STEAMVR_ROOT", "/opt/steamvr")
LIB = f"{STEAMVR}/bin/linuxarm64/libopenvr_api.so"
VRCMD = f"{STEAMVR}/bin/linuxarm64/vrcmd"
KEYS = ("asterism.desktop.app.2", "asterism.desktop.app.3")


class HmdMatrix34(Structure):
    _fields_ = [("m", (c_float * 4) * 3)]


class FnTable(Structure):
    _fields_ = [("fns", c_void_p * 128)]


def env_vr() -> dict[str, str]:
    e = os.environ.copy()
    libdir = f"{STEAMVR}/bin/linuxarm64"
    e["LD_LIBRARY_PATH"] = libdir + ((":" + e["LD_LIBRARY_PATH"]) if e.get("LD_LIBRARY_PATH") else "")
    uid = os.getuid()
    e.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    e["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={e['XDG_RUNTIME_DIR']}/bus"
    return e


def vrcmd(*args: str) -> None:
    subprocess.run([VRCMD, *args], capture_output=True, text=True, env=env_vr(), check=False)


def mat_from_pos_face(x, y, z, yaw_deg, pitch_deg, roll_deg=0.0) -> HmdMatrix34:
    yaw, pitch, roll = map(math.radians, (yaw_deg, pitch_deg, roll_deg))
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)

    def mul(a, b):
        r = [[0.0] * 3 for _ in range(3)]
        for i in range(3):
            for j in range(3):
                r[i][j] = a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j]
        return r

    R = mul(mul([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], [[1, 0, 0], [0, cp, -sp], [0, sp, cp]]), [[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]])
    m = HmdMatrix34()
    for col in range(3):
        for row in range(3):
            m.m[row][col] = R[row][col]
    m.m[0][3] = x
    m.m[1][3] = y
    m.m[2][3] = z
    return m


def float_all() -> None:
    for key in KEYS:
        print("float", key, flush=True)
        for mode in ("theater", "dashboard", "world"):
            vrcmd("--dock-overlay", mode, key)
            time.sleep(0.5)
    vrcmd("--hidedashboard")
    time.sleep(0.5)


def place_all() -> int:
    lib = ctypes.CDLL(LIB)
    lib.VR_InitInternal2.argtypes = [POINTER(c_int), c_int, c_char_p]
    lib.VR_InitInternal2.restype = c_uint32
    lib.VR_ShutdownInternal.argtypes = []
    lib.VR_GetGenericInterface.argtypes = [c_char_p, POINTER(c_int)]
    lib.VR_GetGenericInterface.restype = c_void_p

    err = c_int(0)
    lib.VR_InitInternal2(byref(err), 8, b"asterism-place-probe")
    print("init err", err.value, flush=True)
    if err.value != 0:
        return 1

    try:
        e2 = c_int(0)
        p = None
        for ver in (b"FnTable:IVROverlay_027", b"FnTable:IVROverlay_029", b"FnTable:IVROverlay_026"):
            e2 = c_int(0)
            p = lib.VR_GetGenericInterface(ver, byref(e2))
            print(ver.decode(), hex(p or 0), e2.value, flush=True)
            if p:
                break
        if not p:
            return 1
        ft = ctypes.cast(p, POINTER(FnTable)).contents
        FindOverlay = ctypes.CFUNCTYPE(c_int, c_char_p, POINTER(c_uint64))(ft.fns[0])
        SetAbs = ctypes.CFUNCTYPE(c_int, c_uint64, c_int, POINTER(HmdMatrix34))(ft.fns[32])
        GetAbs = ctypes.CFUNCTYPE(c_int, c_uint64, POINTER(c_int), POINTER(HmdMatrix34))(ft.fns[33])
        Show = ctypes.CFUNCTYPE(c_int, c_uint64)(ft.fns[41])
        Visible = ctypes.CFUNCTYPE(c_bool, c_uint64)(ft.fns[43])

        poses = [(-0.441, 0.0, -1.538, -16.0), (0.441, 0.0, -1.538, 16.0)]
        for key, pose in zip(KEYS, poses):
            h = c_uint64(0)
            rc = FindOverlay(key.encode(), byref(h))
            print(key, "find", rc, "h", h.value, "vis", bool(Visible(h)) if rc == 0 else None, flush=True)
            if rc != 0:
                continue
            mat = mat_from_pos_face(*pose[:3], pose[3], 0.0)
            print("  set…", flush=True)
            s = SetAbs(h, 1, byref(mat))
            print("  set rc", s, flush=True)
            sh = Show(h)
            print("  show rc", sh, "vis", bool(Visible(h)), flush=True)
            origin = c_int(0)
            out = HmdMatrix34()
            g = GetAbs(h, byref(origin), byref(out))
            print("  get", g, "origin", origin.value, "pos", float(out.m[0][3]), float(out.m[1][3]), float(out.m[2][3]), flush=True)
    finally:
        lib.VR_ShutdownInternal()
        print("shutdown", flush=True)

    out = subprocess.check_output([VRCMD, "--overlays"], env=env_vr(), text=True)
    for line in out.splitlines():
        if "asterism.desktop.app." in line and "layer" not in line and "thumb" not in line:
            print("STATE", line.strip())
    return 0


def main() -> int:
    float_all()
    return place_all()


if __name__ == "__main__":
    raise SystemExit(main())
