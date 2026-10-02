// asterism-overlay-inspect: READ-ONLY OpenVR transform diagnostics for Asterism overlays.
// Usage: asterism-overlay-inspect json [overlay_key ...]
#include <openvr.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static const char *TransformTypeNameId(int id) {
    static const char *names[] = {
        "Absolute",
        "TrackedDeviceRelative",
        "SystemOverlay",
        "TrackedComponent",
        "Cursor",
        "DashboardTab",
        "DashboardThumb",
        "Subview",
        "Projection",
    };
    if (id >= 0 && id < (int)(sizeof(names) / sizeof(names[0]))) return names[id];
    return "Unknown";
}

int main(int argc, char **argv) {
    if (argc < 2 || std::strcmp(argv[1], "json") != 0) {
        std::fprintf(stderr, "usage: %s json [overlay_key ...]\n", argv[0]);
        return 2;
    }

    vr::EVRInitError err = vr::VRInitError_None;
    vr::VR_Init(&err, vr::VRApplication_Overlay);
    if (err != vr::VRInitError_None) {
        std::printf("[{\"error\":\"VR_Init\",\"code\":%d}]\n", int(err));
        return 1;
    }
    auto *overlay = vr::VROverlay();
    if (!overlay) {
        std::printf("[{\"error\":\"no IVROverlay\"}]\n");
        vr::VR_Shutdown();
        return 1;
    }

    std::vector<std::string> keys;
    for (int i = 2; i < argc; ++i) keys.emplace_back(argv[i]);

    std::printf("[");
    bool first = true;
    for (const auto &key : keys) {
        if (!first) std::printf(",");
        first = false;
        vr::VROverlayHandle_t h = vr::k_ulOverlayHandleInvalid;
        vr::EVROverlayError fe = overlay->FindOverlay(key.c_str(), &h);
        std::printf("{\"key\":%s", ("\"" + key + "\"").c_str());
        if (fe != vr::VROverlayError_None) {
            std::printf(",\"overlay_error\":\"%s\",\"overlay_error_code\":%d}",
                        overlay->GetOverlayErrorNameFromEnum(fe), int(fe));
            continue;
        }
        const bool visible = overlay->IsOverlayVisible(h);
        float width = 0.f;
        overlay->GetOverlayWidthInMeters(h, &width);

        vr::VROverlayTransformType ttype{};
        vr::EVROverlayError te = overlay->GetOverlayTransformType(h, &ttype);
        int tid = int(ttype);
        std::printf(",\"visible\":%s,\"width_m\":%.5f", visible ? "true" : "false", width);
        if (te != vr::VROverlayError_None) {
            std::printf(",\"transform_type\":null,\"transform_type_error\":\"%s\"",
                        overlay->GetOverlayErrorNameFromEnum(te));
        } else {
            std::printf(",\"transform_type\":{\"id\":%d,\"name\":\"%s\"}", tid, TransformTypeNameId(tid));
        }

        vr::ETrackingUniverseOrigin origin = vr::TrackingUniverseStanding;
        vr::HmdMatrix34_t mat{};
        vr::EVROverlayError ae = overlay->GetOverlayTransformAbsolute(h, &origin, &mat);
        if (ae != vr::VROverlayError_None) {
            std::printf(",\"absolute\":null,\"absolute_error\":\"%s\",\"absolute_error_code\":%d",
                        overlay->GetOverlayErrorNameFromEnum(ae), int(ae));
        } else {
            std::printf(
                ",\"absolute\":{\"origin\":%d,\"m\":[[%.6f,%.6f,%.6f,%.6f],[%.6f,%.6f,%.6f,%.6f],[%.6f,%.6f,%.6f,%.6f]]}",
                int(origin), mat.m[0][0], mat.m[0][1], mat.m[0][2], mat.m[0][3], mat.m[1][0], mat.m[1][1],
                mat.m[1][2], mat.m[1][3], mat.m[2][0], mat.m[2][1], mat.m[2][2], mat.m[2][3]);
            std::printf(",\"absolute_error\":null");
        }
        std::printf("}");
    }
    std::printf("]\n");
    vr::VR_Shutdown();
    return 0;
}
