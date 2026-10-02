#!/usr/bin/env python3
"""Probe ComputeOverlayIntersection on Asterism gamescope overlays."""
from __future__ import annotations

import ctypes
import math
import os
from ctypes import POINTER, Structure, byref, c_bool, c_char_p, c_float, c_int, c_uint32, c_uint64, c_void_p

STEAMVR = "/opt/steamvr"
LIB = f"{STEAMVR}/bin/linuxarm64/libopenvr_api.so"


class HmdVector3(Structure):
    _fields_ = [("v", c_float * 3)]


class HmdVector2(Structure):
    _fields_ = [("v", c_float * 2)]


class IntersectionParams(Structure):
    _fields_ = [
        ("vSource", HmdVector3),
        ("vDirection", HmdVector3),
        ("eOrigin", c_int),
    ]


class IntersectionResults(Structure):
    _fields_ = [
        ("vPoint", HmdVector3),
        ("vNormal", HmdVector3),
        ("vUVs", HmdVector2),
        ("fDistance", c_float),
    ]


class TrackedDevicePose(Structure):
    _fields_ = [
        ("mDeviceToAbsoluteTracking", (c_float * 4) * 3),
        ("vVelocity", c_float * 3),
        ("vAngularVelocity", c_float * 3),
        ("eTrackingResult", c_int),
        ("bPoseIsValid", c_bool),
        ("bDeviceIsConnected", c_bool),
    ]


class FnTable(Structure):
    _fields_ = [("fns", c_void_p * 128)]


def main() -> int:
    lib = ctypes.CDLL(LIB)
    lib.VR_InitInternal2.argtypes = [POINTER(c_int), c_int, c_char_p]
    lib.VR_InitInternal2.restype = c_uint32
    lib.VR_ShutdownInternal.argtypes = []
    lib.VR_GetGenericInterface.argtypes = [c_char_p, POINTER(c_int)]
    lib.VR_GetGenericInterface.restype = c_void_p

    err = c_int(0)
    lib.VR_InitInternal2(byref(err), 8, b"asterism-hit-probe")
    print("init", err.value, flush=True)
    if err.value:
        return 1

    try:
        e2 = c_int(0)
        ov = lib.VR_GetGenericInterface(b"FnTable:IVROverlay_027", byref(e2))
        sy = lib.VR_GetGenericInterface(b"FnTable:IVRSystem_022", byref(e2))
        print("overlay", hex(ov or 0), "system", hex(sy or 0), flush=True)
        oft = ctypes.cast(ov, POINTER(FnTable)).contents
        sft = ctypes.cast(sy, POINTER(FnTable)).contents

        # Find indices for ComputeOverlayIntersection
        # From header: after IsOverlayVisible(43)... let's get from json
        import json
        from pathlib import Path

        methods = json.loads(
            Path("/opt/steamvr/tools/hellovr_vulkan_linux/src/openvr/headers/openvr_api.json").read_text()
        )["methods"]
        ov_methods = [m["methodname"] for m in methods if m["classname"] == "vr::IVROverlay"]
        sys_methods = [m["methodname"] for m in methods if m["classname"] == "vr::IVRSystem"]
        ci = ov_methods.index("ComputeOverlayIntersection")
        gd = sys_methods.index("GetDeviceToAbsoluteTrackingPose")
        print("ComputeOverlayIntersection idx", ci, "GetDeviceToAbsoluteTrackingPose", gd, flush=True)

        FindOverlay = ctypes.CFUNCTYPE(c_int, c_char_p, POINTER(c_uint64))(oft.fns[0])
        Compute = ctypes.CFUNCTYPE(c_bool, c_uint64, POINTER(IntersectionParams), POINTER(IntersectionResults))(
            oft.fns[ci]
        )
        IsVisible = ctypes.CFUNCTYPE(c_bool, c_uint64)(oft.fns[ov_methods.index("IsOverlayVisible")])
        GetPose = ctypes.CFUNCTYPE(None, c_int, c_float, POINTER(TrackedDevicePose), c_uint32)(sft.fns[gd])

        pose = TrackedDevicePose()
        GetPose(1, 0.0, byref(pose), 1)  # Standing
        print(
            "head valid",
            bool(pose.bPoseIsValid),
            "pos",
            float(pose.mDeviceToAbsoluteTracking[0][3]),
            float(pose.mDeviceToAbsoluteTracking[1][3]),
            float(pose.mDeviceToAbsoluteTracking[2][3]),
            flush=True,
        )
        eye = (
            float(pose.mDeviceToAbsoluteTracking[0][3]),
            float(pose.mDeviceToAbsoluteTracking[1][3]),
            float(pose.mDeviceToAbsoluteTracking[2][3]),
        )

        for key in (b"asterism.desktop.app.2", b"asterism.desktop.app.3", b"asterism.desktop.app.0"):
            h = c_uint64(0)
            rc = FindOverlay(key, byref(h))
            print(key.decode(), "find", rc, "vis", bool(IsVisible(h)) if rc == 0 else None, flush=True)
            if rc != 0:
                continue
            hits = 0
            for pitch in range(-40, 41, 5):
                for yaw in range(-60, 61, 5):
                    y = math.radians(yaw)
                    p = math.radians(pitch)
                    d = (-math.sin(y) * math.cos(p), math.sin(p), -math.cos(y) * math.cos(p))
                    params = IntersectionParams()
                    params.vSource.v[0], params.vSource.v[1], params.vSource.v[2] = eye
                    params.vDirection.v[0], params.vDirection.v[1], params.vDirection.v[2] = d
                    params.eOrigin = 1
                    hit = IntersectionResults()
                    if Compute(h, byref(params), byref(hit)):
                        hits += 1
            print("  hits", hits, flush=True)
    finally:
        lib.VR_ShutdownInternal()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
