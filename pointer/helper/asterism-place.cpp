// asterism-place: place gamescope PerWindow overlays in world space via the
// asterism_pointer virtual controller (FrameTop ft-pointer place pattern).
//
// Usage:
//   asterism-place head
//   asterism-place measure <overlay_key>
//   asterism-place place <overlay_key> <x> <y> <z> <yaw> <pitch> [roll]
//
// Coordinates are standing-universe metres relative to the current head position
// for (x,y,z) when --relative is passed; absolute standing metres otherwise.
// yaw/pitch/roll are degrees (FrameTop PanelBasis).
#include <openvr.h>

#include "../common/vrmath.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

using namespace md;

namespace {

constexpr const char *kDriverSock = "asterism_pointer";
constexpr double kPlaceDegPerSec = 60.0;
constexpr double kSlideSpeed = 0.5;
constexpr double kGrabBelow = 0.075;

void SleepMs(int ms) { std::this_thread::sleep_for(std::chrono::milliseconds(ms)); }

int DriverFd() {
    return socket(AF_UNIX, SOCK_DGRAM | SOCK_CLOEXEC, 0);
}

void SendDriver(int fd, const std::string &msg) {
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    std::memcpy(addr.sun_path + 1, kDriverSock, std::strlen(kDriverSock));
    const socklen_t len = offsetof(sockaddr_un, sun_path) + 1 + std::strlen(kDriverSock);
    sendto(fd, msg.data(), msg.size(), 0, reinterpret_cast<sockaddr *>(&addr), len);
}

Vec3 HeadStanding(vr::IVRSystem *sys, bool *ok) {
    for (int i = 0; i < 30; ++i) {
        vr::TrackedDevicePose_t s{};
        sys->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseStanding, 0, &s, 1);
        if (s.bPoseIsValid) {
            *ok = true;
            return Position(s.mDeviceToAbsoluteTracking);
        }
        SleepMs(50);
    }
    *ok = false;
    return {};
}

double HeadYaw(vr::IVRSystem *sys) {
    vr::TrackedDevicePose_t s{};
    sys->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseStanding, 0, &s, 1);
    if (!s.bPoseIsValid) return 0;
    // Forward is -Z column of rotation.
    const auto &m = s.mDeviceToAbsoluteTracking;
    const double fx = -m.m[0][2], fz = -m.m[2][2];
    return std::atan2(fx, fz) * 180.0 / M_PI;
}

void SendPose(int fd, vr::IVRSystem *sys, Vec3 originStanding, const Basis &b) {
    vr::TrackedDevicePose_t s{}, r{};
    sys->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseStanding, 0, &s, 1);
    sys->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseRawAndUncalibrated, 0, &r, 1);
    if (!s.bPoseIsValid || !r.bPoseIsValid) {
        std::fprintf(stderr, "place: warn SendPose missing HMD standing/raw pose\n");
        return;
    }
    const auto &S = s.mDeviceToAbsoluteTracking, &R = r.mDeviceToAbsoluteTracking;
    auto toRaw = [&](Vec3 v) { return Rotate(R, RotateInverse(S, v)); };
    const Vec3 o = Position(R) + toRaw(originStanding - Position(S));
    double q[4];
    BasisQuat({toRaw(b.x), toRaw(b.y), toRaw(b.z)}, q);
    char msg[200];
    std::snprintf(msg, sizeof msg, "posq %.5f %.5f %.5f %.6f %.6f %.6f %.6f", o.x, o.y, o.z, q[0], q[1], q[2],
                  q[3]);
    SendDriver(fd, msg);
}

void ReleaseDriver(int fd, vr::IVROverlay *overlay, vr::VROverlayHandle_t laser) {
    SendDriver(fd, "btn trigger 0");
    SendDriver(fd, "btn a 0");
    SendDriver(fd, "hide");
    if (overlay && laser != vr::k_ulOverlayHandleInvalid) {
        overlay->HideOverlay(laser);
    }
}

std::string Place(vr::IVRSystem *sys, vr::IVROverlay *overlay, int fd, vr::VROverlayHandle_t laser,
                  const char *key, Vec3 target, const Basis &bt) {
    struct Guard {
        int fd;
        vr::IVROverlay *overlay;
        vr::VROverlayHandle_t laser;
        ~Guard() { ReleaseDriver(fd, overlay, laser); }
    } guard{fd, overlay, laser};

    vr::VROverlayHandle_t h = vr::k_ulOverlayHandleInvalid;
    if (overlay->FindOverlay(key, &h) != vr::VROverlayError_None) return std::string("error no overlay ") + key;

    bool valid = false;
    Vec3 eye = HeadStanding(sys, &valid);
    if (!valid) return "error no head pose (headset off?)";

    Panel p = ScanPanel(h, eye, 0.5);
    if (!p.found) {
        return std::string("error panel not measurable: ") + key;
    }

    auto offBy = [&](const Panel &q, double &cm, double &deg) {
        cm = Length(q.center - target) * 100;
        const double c = (Dot(q.basis.x, bt.x) + Dot(q.basis.y, bt.y) + Dot(q.basis.z, bt.z) - 1) / 2;
        deg = std::acos(std::clamp(c, -1.0, 1.0)) * 180 / M_PI;
    };

    // Quiet any prior borrow before claiming again.
    ReleaseDriver(fd, overlay, laser);
    SleepMs(100);

    SendDriver(fd, "show");
    overlay->ShowOverlay(laser);
    SleepMs(600);
    SendDriver(fd, "btn a 1");
    SleepMs(80);
    SendDriver(fd, "btn a 0");
    std::fprintf(stderr, "place: borrowed laser for %s\n", key);

    double cm = 0, deg = 0;
    int moves = 0;
    std::string err;
    for (int attempt = 0; attempt < 3; ++attempt) {
        offBy(p, cm, deg);
        if (cm < 1.5 && deg < 1.0) break;
        auto turn = [&](Vec3 v) { return FromBasis(bt, ToBasis(p.basis, v)); };
        double q[4];
        BasisQuat({turn({1, 0, 0}), turn({0, 1, 0}), turn({0, 0, 1})}, q);
        const double angle = 2 * std::acos(std::clamp(q[0], -1.0, 1.0));
        const Vec3 axis = std::sin(angle / 2) > 1e-6 ? Normalize({q[1], q[2], q[3]}) : Vec3{0, 1, 0};
        const Vec3 grab = p.center - p.basis.y * (p.height / 2 + kGrabBelow);
        const Basis d0 = AimBasis(grab - eye);
        const Vec3 o1 = target + turn(eye - p.center);
        ++moves;
        std::fprintf(stderr, "place: move %d grab->target (%.2f cm, %.1f deg)\n", moves, cm, deg);
        SendPose(fd, sys, eye, d0);
        SleepMs(150);
        SendDriver(fd, "btn trigger 1");
        SleepMs(150);
        const int rsteps = std::max(4, int(angle * 180 / M_PI / kPlaceDegPerSec * 60));
        for (int i = 1; i <= rsteps; ++i) {
            const double a = angle * i / rsteps;
            auto rot = [&](Vec3 v) { return RotateAbout(v, axis, a); };
            SendPose(fd, sys, eye, {rot(d0.x), rot(d0.y), rot(d0.z)});
            SleepMs(16);
        }
        const Basis d1{turn(d0.x), turn(d0.y), turn(d0.z)};
        const int tsteps = std::max(4, int(Length(o1 - eye) / kSlideSpeed * 60));
        for (int i = 1; i <= tsteps; ++i) {
            SendPose(fd, sys, eye + (o1 - eye) * (double(i) / tsteps), d1);
            SleepMs(16);
        }
        SleepMs(100);
        SendDriver(fd, "btn trigger 0");
        SleepMs(600);
        eye = HeadStanding(sys, &valid);
        if (!valid) {
            err = "no head pose after move";
            break;
        }
        p = ScanPanel(h, eye, 0.5);
        if (!p.found) {
            p = ScanPanel(h, eye, 1.0);
        }
        if (!p.found) {
            char detail[128];
            std::snprintf(detail, sizeof detail, "panel lost after move (last off %.1f cm)", cm);
            err = detail;
            break;
        }
    }

    if (!err.empty()) return "error " + err;
    offBy(p, cm, deg);
    char msg[160];
    std::snprintf(msg, sizeof msg, "ok %s off by %.1f cm, %.1f deg after %d move%s", key, cm, deg, moves,
                  moves == 1 ? "" : "s");
    if (cm > 30.0 || deg > 25.0) {
        return std::string("error ") + msg;
    }
    return msg;
}

}  // namespace

int main(int argc, char **argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: %s head|measure <key>|place <key> x y z yaw pitch [roll]|release\n",
                     argv[0]);
        return 2;
    }

    const std::string cmd = argv[1];
    // release only needs the driver socket — no OpenVR init (avoids stealing overlay slot).
    if (cmd == "release") {
        const int fd = DriverFd();
        SendDriver(fd, "btn trigger 0");
        SendDriver(fd, "btn a 0");
        SendDriver(fd, "hide");
        close(fd);
        std::printf("ok released\n");
        return 0;
    }

    vr::EVRInitError err = vr::VRInitError_None;
    vr::VR_Init(&err, vr::VRApplication_Overlay);
    if (err != vr::VRInitError_None) {
        std::fprintf(stderr, "VR_Init failed: %d\n", int(err));
        return 1;
    }
    auto *sys = vr::VRSystem();
    auto *overlay = vr::VROverlay();
    if (!sys || !overlay) {
        std::fprintf(stderr, "missing IVRSystem/IVROverlay\n");
        vr::VR_Shutdown();
        return 1;
    }

    // Invisible interactive overlay so SteamVR's laser can grab dashboard panels.
    vr::VROverlayHandle_t laser = vr::k_ulOverlayHandleInvalid;
    overlay->CreateOverlay("asterism.pointer.lasermode", "Asterism place laser", &laser);
    std::vector<uint8_t> clear(4 * 4 * 4, 0);
    overlay->SetOverlayRaw(laser, clear.data(), 4, 4, 4);
    overlay->SetOverlayWidthInMeters(laser, 0.001f);
    overlay->SetOverlayInputMethod(laser, vr::VROverlayInputMethod_Mouse);
    overlay->SetOverlayFlag(laser, vr::VROverlayFlags_MakeOverlaysInteractiveIfVisible, true);
    vr::HmdMatrix34_t below{};
    below.m[0][0] = below.m[1][1] = below.m[2][2] = 1;
    below.m[1][3] = -50;
    overlay->SetOverlayTransformTrackedDeviceRelative(laser, vr::k_unTrackedDeviceIndex_Hmd, &below);

    const int fd = DriverFd();
    // Always start clean — a crashed place can leave the virtual controller owning the laser.
    ReleaseDriver(fd, overlay, laser);
    int rc = 0;

    if (cmd == "head") {
        bool ok = false;
        Vec3 e = HeadStanding(sys, &ok);
        if (!ok) {
            std::printf("error no head pose\n");
            rc = 1;
        } else {
            std::printf("ok %.5f %.5f %.5f %.4f\n", e.x, e.y, e.z, HeadYaw(sys));
        }
    } else if (cmd == "measure" && argc >= 3) {
        bool ok = false;
        Vec3 eye = HeadStanding(sys, &ok);
        if (!ok) {
            std::printf("error no head pose\n");
            rc = 1;
        } else {
            vr::VROverlayHandle_t h = vr::k_ulOverlayHandleInvalid;
            if (overlay->FindOverlay(argv[2], &h) != vr::VROverlayError_None) {
                std::printf("error no overlay %s\n", argv[2]);
                rc = 1;
            } else {
                Panel p = ScanPanel(h, eye, 0.5);
                if (!p.found) {
                    std::printf("error panel not measurable: %s (hits=%d)\n", argv[2], p.hits);
                    rc = 1;
                } else {
                    std::printf("ok %.5f %.5f %.5f %.5f %.5f %.5f %.5f %.5f %.5f %.5f %.5f %.5f %.5f %.5f\n",
                                p.center.x, p.center.y, p.center.z, p.width, p.height, p.basis.x.x, p.basis.x.y,
                                p.basis.x.z, p.basis.y.x, p.basis.y.y, p.basis.y.z, p.basis.z.x, p.basis.z.y,
                                p.basis.z.z);
                }
            }
        }
    } else if (cmd == "place" && argc >= 8) {
        const char *key = argv[2];
        const double x = std::atof(argv[3]), y = std::atof(argv[4]), z = std::atof(argv[5]);
        const double yaw = std::atof(argv[6]), pitch = std::atof(argv[7]);
        const double roll = argc >= 9 ? std::atof(argv[8]) : 0.0;
        bool ok = false;
        Vec3 eye = HeadStanding(sys, &ok);
        if (!ok) {
            std::printf("error no head pose\n");
            rc = 1;
        } else {
            const double heading = HeadYaw(sys);
            // Layout stores head-relative pos/face; convert to standing absolute.
            const double hy = heading * M_PI / 180.0;
            const double c = std::cos(hy), s = std::sin(hy);
            Vec3 world{x * c + z * s, y, -x * s + z * c};
            Vec3 center = eye + world;
            Basis bt = PanelBasis(yaw + heading, pitch, roll);
            const std::string reply = Place(sys, overlay, fd, laser, key, center, bt);
            std::printf("%s\n", reply.c_str());
            if (reply.rfind("error", 0) == 0) rc = 1;
        }
    } else {
        std::fprintf(stderr, "bad args\n");
        rc = 2;
    }

    ReleaseDriver(fd, overlay, laser);
    close(fd);
    overlay->DestroyOverlay(laser);
    vr::VR_Shutdown();
    return rc;
}
