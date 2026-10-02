#include <openvr.h>
#include <cstdio>

int main() {
    vr::EVRInitError e = vr::VRInitError_None;
    vr::VR_Init(&e, vr::VRApplication_Overlay);
    std::printf("init %d\n", int(e));
    if (e) return 1;
    vr::TrackedDevicePose_t s{};
    vr::VRSystem()->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseStanding, 0, &s, 1);
    std::printf("valid=%d connected=%d result=%d pos=%.3f %.3f %.3f\n", s.bPoseIsValid,
                s.bDeviceIsConnected, int(s.eTrackingResult), s.mDeviceToAbsoluteTracking.m[0][3],
                s.mDeviceToAbsoluteTracking.m[1][3], s.mDeviceToAbsoluteTracking.m[2][3]);
    // Also dump device 0 props briefly via poll of first few devices
    for (uint32_t i = 0; i < 8; ++i) {
        vr::TrackedDevicePose_t p{};
        vr::VRSystem()->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseStanding, 0, &p, i + 1);
        // only look at index i by calling with count i+1 and reading last — better: array
    }
    vr::TrackedDevicePose_t arr[16]{};
    vr::VRSystem()->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseStanding, 0, arr, 16);
    for (int i = 0; i < 16; ++i) {
        if (!arr[i].bDeviceIsConnected) continue;
        std::printf("dev %d class=? valid=%d res=%d pos=%.3f %.3f %.3f\n", i, arr[i].bPoseIsValid,
                    int(arr[i].eTrackingResult), arr[i].mDeviceToAbsoluteTracking.m[0][3],
                    arr[i].mDeviceToAbsoluteTracking.m[1][3], arr[i].mDeviceToAbsoluteTracking.m[2][3]);
    }
    vr::VR_Shutdown();
    return 0;
}
