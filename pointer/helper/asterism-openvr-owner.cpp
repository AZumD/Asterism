// asterism-openvr-owner.so — LD_PRELOAD into Gamescope for owner-process transform proof.
// Opt-in: ASTERISM_OPENVR_CTRL=1. Socket: $XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock
#define _GNU_SOURCE
#include <dlfcn.h>
#include <pthread.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <math.h>
#include <openvr.h>

static int g_listen = -1;
static char g_sock_path[512];
static bool g_started = false;
static pthread_mutex_t g_mu = PTHREAD_MUTEX_INITIALIZER;

using GetGenericInterface_fn = void *(*)(const char *, vr::EVRInitError *);
using GetErrorName_fn = const char *(*)(vr::EVROverlayError);

static void *load_sym(const char *name) {
    void *p = dlsym(RTLD_DEFAULT, name);
    if (p) return p;

    // Scan already-mapped libraries (gamescope often dlopens OpenVR with RTLD_LOCAL).
    FILE *maps = fopen("/proc/self/maps", "r");
    if (maps) {
        char line[512];
        while (fgets(line, sizeof(line), maps)) {
            char *path = strchr(line, '/');
            if (!path) continue;
            char *nl = strchr(path, '\n');
            if (nl) *nl = 0;
            if (!strstr(path, "libopenvr_api")) continue;
            void *h = dlopen(path, RTLD_NOW | RTLD_NOLOAD | RTLD_GLOBAL);
            if (!h) h = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
            if (!h) continue;
            p = dlsym(h, name);
            if (p) {
                fprintf(stderr, "[asterism-openvr-owner] resolved %s via %s\n", name, path);
                fflush(stderr);
                fclose(maps);
                return p;
            }
        }
        fclose(maps);
    }

    const char *paths[] = {
        "libopenvr_api.so",
        "/opt/steamvr/bin/linuxarm64/libopenvr_api.so",
        "/usr/lib/libopenvr_api.so",
        nullptr,
    };
    for (int i = 0; paths[i]; ++i) {
        void *h = dlopen(paths[i], RTLD_NOW | RTLD_NOLOAD | RTLD_GLOBAL);
        if (!h) h = dlopen(paths[i], RTLD_NOW | RTLD_GLOBAL);
        if (!h) continue;
        p = dlsym(h, name);
        if (p) return p;
    }
    return nullptr;
}

static vr::IVROverlay *overlay_iface() {
    static GetGenericInterface_fn get_iface = nullptr;
    if (!get_iface) get_iface = (GetGenericInterface_fn)load_sym("VR_GetGenericInterface");
    if (!get_iface) return nullptr;
    vr::EVRInitError err = vr::VRInitError_None;
    // Prefer current; fall back through a few versions.
    const char *versions[] = {
        "IVROverlay_027", "IVROverlay_026", "IVROverlay_025", "IVROverlay_024",
        "IVROverlay_022", "IVROverlay_021", "IVROverlay_020", "IVROverlay_019",
        nullptr,
    };
    for (int i = 0; versions[i]; ++i) {
        void *p = get_iface(versions[i], &err);
        if (p && err == vr::VRInitError_None) return (vr::IVROverlay *)p;
    }
    // Last resort: header helper (uses this .so's linked openvr if inited).
    return vr::VROverlay();
}

static const char *ttname(int id) {
    static const char *names[] = {
        "Absolute", "TrackedDeviceRelative", "SystemOverlay", "TrackedComponent",
        "Cursor", "DashboardTab", "DashboardThumb", "Subview", "Projection"};
    if (id >= 0 && id < (int)(sizeof(names) / sizeof(names[0]))) return names[id];
    return "Unknown";
}

static int append_inspect(char *out, int cap, const char *key, vr::IVROverlay *o, vr::VROverlayHandle_t h) {
    bool vis = o->IsOverlayVisible(h);
    float w = 0.f;
    o->GetOverlayWidthInMeters(h, &w);
    vr::VROverlayTransformType t{};
    o->GetOverlayTransformType(h, &t);
    int tid = (int)t;
    vr::ETrackingUniverseOrigin origin = vr::TrackingUniverseStanding;
    vr::HmdMatrix34_t mat{};
    vr::EVROverlayError ae = o->GetOverlayTransformAbsolute(h, &origin, &mat);
    if (ae == vr::VROverlayError_None) {
        return snprintf(out, cap,
            "{\"key\":\"%s\",\"handle\":%llu,\"visible\":%s,\"width_m\":%.5f,"
            "\"transform_type\":{\"id\":%d,\"name\":\"%s\"},"
            "\"absolute\":{\"origin\":%d,\"m\":[[%.6f,%.6f,%.6f,%.6f],[%.6f,%.6f,%.6f,%.6f],[%.6f,%.6f,%.6f,%.6f]]},"
            "\"absolute_error\":null}",
            key, (unsigned long long)h, vis ? "true" : "false", w, tid, ttname(tid),
            (int)origin,
            mat.m[0][0], mat.m[0][1], mat.m[0][2], mat.m[0][3],
            mat.m[1][0], mat.m[1][1], mat.m[1][2], mat.m[1][3],
            mat.m[2][0], mat.m[2][1], mat.m[2][2], mat.m[2][3]);
    }
    return snprintf(out, cap,
        "{\"key\":\"%s\",\"handle\":%llu,\"visible\":%s,\"width_m\":%.5f,"
        "\"transform_type\":{\"id\":%d,\"name\":\"%s\"},"
        "\"absolute\":null,\"absolute_error\":\"%s\",\"absolute_error_code\":%d}",
        key, (unsigned long long)h, vis ? "true" : "false", w, tid, ttname(tid),
        o->GetOverlayErrorNameFromEnum(ae), (int)ae);
}

static vr::HmdMatrix34_t mat_from_pose(float x, float y, float z, float yaw, float pitch, float roll) {
    float cy = cosf(yaw), sy = sinf(yaw);
    float cp = cosf(pitch), sp = sinf(pitch);
    float cr = cosf(roll), sr = sinf(roll);
    vr::HmdMatrix34_t m{};
    m.m[0][0] = cy * cr + sy * sp * sr; m.m[0][1] = sr * cp; m.m[0][2] = -sy * cr + cy * sp * sr; m.m[0][3] = x;
    m.m[1][0] = -cy * sr + sy * sp * cr; m.m[1][1] = cr * cp; m.m[1][2] = sr * sy + cy * sp * cr; m.m[1][3] = y;
    m.m[2][0] = sy * cp; m.m[2][1] = -sp; m.m[2][2] = cy * cp; m.m[2][3] = z;
    return m;
}

static void handle_client(int cfd) {
    char buf[512];
    ssize_t n = read(cfd, buf, sizeof(buf) - 1);
    char reply[16384];
    if (n <= 0) {
        const char *e = "{\"error\":\"empty\"}\n";
        (void)write(cfd, e, strlen(e));
        close(cfd);
        return;
    }
    buf[n] = 0;
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r')) buf[--n] = 0;

    vr::IVROverlay *o = overlay_iface();
    if (!o) {
        const char *e = "{\"error\":\"IVROverlay_unavailable\",\"hint\":\"gamescope OpenVR not ready in-process\"}\n";
        (void)write(cfd, e, strlen(e));
        close(cfd);
        return;
    }

    if (strncmp(buf, "inspect", 7) == 0) {
        const char *arg = buf + 7;
        while (*arg == ' ') ++arg;
        if (*arg) {
            vr::VROverlayHandle_t h = vr::k_ulOverlayHandleInvalid;
            vr::EVROverlayError fe = o->FindOverlay(arg, &h);
            if (fe != vr::VROverlayError_None) {
                snprintf(reply, sizeof(reply), "{\"error\":\"overlay_not_found\",\"key\":\"%s\",\"find_error\":\"%s\"}\n",
                         arg, o->GetOverlayErrorNameFromEnum(fe));
            } else {
                append_inspect(reply, (int)sizeof(reply) - 2, arg, o, h);
                strcat(reply, "\n");
            }
        } else {
            int pos = 0;
            pos += snprintf(reply + pos, sizeof(reply) - pos, "[");
            bool first = true;
            for (int i = 0; i < 16; ++i) {
                char key[128];
                snprintf(key, sizeof(key), "asterism.desktop.app.%d", i);
                vr::VROverlayHandle_t h = vr::k_ulOverlayHandleInvalid;
                if (o->FindOverlay(key, &h) != vr::VROverlayError_None) continue;
                if (!first) pos += snprintf(reply + pos, sizeof(reply) - pos, ",");
                first = false;
                char one[2048];
                append_inspect(one, sizeof(one), key, o, h);
                pos += snprintf(reply + pos, sizeof(reply) - pos, "%s", one);
            }
            snprintf(reply + pos, sizeof(reply) - pos, "]\n");
        }
        (void)write(cfd, reply, strlen(reply));
        close(cfd);
        return;
    }

    if (strncmp(buf, "set-test-absolute ", 18) == 0) {
        char key[128];
        float x, y, z, yaw, pitch, roll;
        if (sscanf(buf + 18, "%127s %f %f %f %f %f %f", key, &x, &y, &z, &yaw, &pitch, &roll) != 7) {
            const char *e = "{\"error\":\"usage\",\"hint\":\"set-test-absolute key x y z yaw pitch roll\"}\n";
            (void)write(cfd, e, strlen(e));
            close(cfd);
            return;
        }
        vr::VROverlayHandle_t h = vr::k_ulOverlayHandleInvalid;
        if (o->FindOverlay(key, &h) != vr::VROverlayError_None) {
            snprintf(reply, sizeof(reply), "{\"error\":\"overlay_not_found\",\"key\":\"%s\"}\n", key);
            (void)write(cfd, reply, strlen(reply));
            close(cfd);
            return;
        }
        char before[2048], after[2048];
        append_inspect(before, sizeof(before), key, o, h);
        vr::HmdMatrix34_t mat = mat_from_pose(x, y, z, yaw, pitch, roll);
        vr::EVROverlayError se = o->SetOverlayTransformAbsolute(h, vr::TrackingUniverseStanding, &mat);
        append_inspect(after, sizeof(after), key, o, h);
        snprintf(reply, sizeof(reply),
            "{\"cmd\":\"set-test-absolute\",\"key\":\"%s\",\"set_error\":\"%s\",\"set_error_code\":%d,"
            "\"before\":%s,\"after\":%s,"
            "\"note\":\"called_from_gamescope_process_via_LD_PRELOAD\"}\n",
            key, o->GetOverlayErrorNameFromEnum(se), (int)se, before, after);
        fprintf(stderr, "[asterism-openvr-owner] set-test-absolute %s -> %s (%d)\n",
                key, o->GetOverlayErrorNameFromEnum(se), (int)se);
        (void)write(cfd, reply, strlen(reply));
        close(cfd);
        return;
    }

    const char *e = "{\"error\":\"unknown_command\"}\n";
    (void)write(cfd, e, strlen(e));
    close(cfd);
}

static void *ctrl_thread(void *) {
    // Wait until this process actually owns Asterism overlays (skip short-lived forks).
    bool ready = false;
    for (int i = 0; i < 90; ++i) {
        vr::IVROverlay *o = overlay_iface();
        if (o) {
            vr::VROverlayHandle_t h = vr::k_ulOverlayHandleInvalid;
            if (o->FindOverlay("asterism.desktop", &h) == vr::VROverlayError_None ||
                o->FindOverlay("asterism.desktop.app.0", &h) == vr::VROverlayError_None ||
                o->FindOverlay("asterism.desktop.app.1", &h) == vr::VROverlayError_None ||
                o->FindOverlay("asterism.desktop.app.2", &h) == vr::VROverlayError_None ||
                o->FindOverlay("asterism.desktop.app.3", &h) == vr::VROverlayError_None) {
                ready = true;
                fprintf(stderr, "[asterism-openvr-owner] overlays visible to pid=%d after %ds\n",
                        (int)getpid(), i);
                fflush(stderr);
                break;
            }
        } else if (i % 5 == 0) {
            fprintf(stderr, "[asterism-openvr-owner] waiting iface pid=%d t=%ds\n", (int)getpid(), i);
            fflush(stderr);
        }
        sleep(1);
    }
    if (!ready) {
        fprintf(stderr, "[asterism-openvr-owner] giving up wait for overlays (pid=%d)\n", (int)getpid());
        return nullptr;
    }

    const char *runtime = getenv("XDG_RUNTIME_DIR");
    if (!runtime || !*runtime) {
        fprintf(stderr, "[asterism-openvr-owner] XDG_RUNTIME_DIR unset\n");
        return nullptr;
    }
    char dir[400];
    snprintf(dir, sizeof(dir), "%s/asterism", runtime);
    mkdir(dir, 0700);

    // Only one listener across gamescope fork/re-exec.
    char lockpath[512];
    snprintf(lockpath, sizeof(lockpath), "%s/gamescope-openvr.lock", dir);
    int lfd = open(lockpath, O_CREAT | O_RDWR, 0600);
    if (lfd < 0) {
        fprintf(stderr, "[asterism-openvr-owner] lock open: %s\n", strerror(errno));
        return nullptr;
    }
    if (flock(lfd, LOCK_EX | LOCK_NB) != 0) {
        fprintf(stderr, "[asterism-openvr-owner] another listener holds lock; exiting thread\n");
        close(lfd);
        return nullptr;
    }

    snprintf(g_sock_path, sizeof(g_sock_path), "%s/gamescope-openvr.sock", dir);
    unlink(g_sock_path);
    g_listen = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (g_listen < 0) {
        fprintf(stderr, "[asterism-openvr-owner] socket: %s\n", strerror(errno));
        return nullptr;
    }
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, g_sock_path, sizeof(addr.sun_path) - 1);
    if (bind(g_listen, (sockaddr *)&addr, sizeof(addr)) < 0) {
        fprintf(stderr, "[asterism-openvr-owner] bind %s: %s\n", g_sock_path, strerror(errno));
        close(g_listen);
        g_listen = -1;
        return nullptr;
    }
    chmod(g_sock_path, 0600);
    listen(g_listen, 4);
    fprintf(stderr, "[asterism-openvr-owner] listening on %s (pid=%d)\n", g_sock_path, (int)getpid());
    for (;;) {
        int cfd = accept(g_listen, nullptr, nullptr);
        if (cfd < 0) {
            if (errno == EINTR) continue;
            break;
        }
        pthread_mutex_lock(&g_mu);
        handle_client(cfd);
        pthread_mutex_unlock(&g_mu);
    }
    return nullptr;
}

static void maybe_start() {
    if (g_started) return;
    const char *en = getenv("ASTERISM_OPENVR_CTRL");
    if (!en || (strcmp(en, "1") != 0 && strcasecmp(en, "true") != 0)) return;
    g_started = true;
    fprintf(stderr, "[asterism-openvr-owner] starting (ASTERISM_OPENVR_CTRL=%s pid=%d)\n", en, (int)getpid());
    pthread_t th;
    if (pthread_create(&th, nullptr, ctrl_thread, nullptr) == 0)
        pthread_detach(th);
}

__attribute__((constructor)) static void on_load() {
    maybe_start();
}
