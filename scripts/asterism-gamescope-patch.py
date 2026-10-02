#!/usr/bin/env python3
"""Apply Asterism owner-transform control hooks to a Gamescope source tree.

Idempotent string-anchor patcher (avoids brittle unified diffs against SteamOS forks).
Never touches /usr or /opt — only the clone under gamescope-asterism/src.
"""
from __future__ import annotations

import sys
from pathlib import Path

MARKER = "ASTERISM_OPENVR_CTRL"

CTRL_METHODS = r'''
    // --- BEGIN ASTERISM_OPENVR_CTRL ---
    // Opt-in Unix-socket control so Asterism can prove whether the Gamescope
    // process that called CreateDashboardOverlay can SetOverlayTransformAbsolute
    // after SteamVR undocks the panel to World. Disabled unless ASTERISM_OPENVR_CTRL=1.
    void AsterismCtrlInit()
    {
        const char *en = getenv( "ASTERISM_OPENVR_CTRL" );
        if ( !en || ( strcmp( en, "1" ) != 0 && strcasecmp( en, "true" ) != 0 ) )
            return;

        const char *runtime = getenv( "XDG_RUNTIME_DIR" );
        if ( !runtime || !*runtime )
        {
            openvr_log.errorf( "ASTERISM_OPENVR_CTRL: XDG_RUNTIME_DIR unset" );
            return;
        }
        std::string dir = std::string( runtime ) + "/asterism";
        mkdir( dir.c_str(), 0700 );
        m_sAsterismCtrlPath = dir + "/gamescope-openvr.sock";
        unlink( m_sAsterismCtrlPath.c_str() );

        m_nAsterismCtrlListen = socket( AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0 );
        if ( m_nAsterismCtrlListen < 0 )
        {
            openvr_log.errorf( "ASTERISM_OPENVR_CTRL: socket failed: %s", strerror( errno ) );
            return;
        }
        sockaddr_un addr{};
        addr.sun_family = AF_UNIX;
        strncpy( addr.sun_path, m_sAsterismCtrlPath.c_str(), sizeof( addr.sun_path ) - 1 );
        if ( bind( m_nAsterismCtrlListen, reinterpret_cast<sockaddr*>( &addr ), sizeof( addr ) ) < 0 )
        {
            openvr_log.errorf( "ASTERISM_OPENVR_CTRL: bind %s failed: %s", m_sAsterismCtrlPath.c_str(), strerror( errno ) );
            close( m_nAsterismCtrlListen );
            m_nAsterismCtrlListen = -1;
            return;
        }
        chmod( m_sAsterismCtrlPath.c_str(), 0600 );
        if ( listen( m_nAsterismCtrlListen, 2 ) < 0 )
        {
            openvr_log.errorf( "ASTERISM_OPENVR_CTRL: listen failed: %s", strerror( errno ) );
            close( m_nAsterismCtrlListen );
            m_nAsterismCtrlListen = -1;
            return;
        }
        openvr_log.infof( "ASTERISM_OPENVR_CTRL listening on %s", m_sAsterismCtrlPath.c_str() );
    }

    static const char *AsterismTransformTypeName( int id )
    {
        static const char *names[] = {
            "Absolute", "TrackedDeviceRelative", "SystemOverlay", "TrackedComponent",
            "Cursor", "DashboardTab", "DashboardThumb", "Subview", "Projection",
        };
        if ( id >= 0 && id < (int)( sizeof( names ) / sizeof( names[0] ) ) )
            return names[id];
        return "Unknown";
    }

    std::string AsterismInspectOne( COpenVRPlane &plane )
    {
        vr::VROverlayHandle_t h = plane.GetOverlay();
        if ( h == vr::k_ulOverlayHandleInvalid )
            return "{\"error\":\"invalid_handle\"}";

        const std::string &key = plane.GetDashboardOverlayKey();
        bool visible = vr::VROverlay()->IsOverlayVisible( h );
        float width = 0.f;
        vr::VROverlay()->GetOverlayWidthInMeters( h, &width );

        vr::VROverlayTransformType ttype{};
        vr::EVROverlayError te = vr::VROverlay()->GetOverlayTransformType( h, &ttype );
        int tid = int( ttype );

        vr::ETrackingUniverseOrigin origin = vr::TrackingUniverseStanding;
        vr::HmdMatrix34_t mat{};
        vr::EVROverlayError ae = vr::VROverlay()->GetOverlayTransformAbsolute( h, &origin, &mat );

        char buf[2048];
        const char *tt_err = ( te == vr::VROverlayError_None )
            ? nullptr
            : vr::VROverlay()->GetOverlayErrorNameFromEnum( te );
        if ( ae == vr::VROverlayError_None )
        {
            snprintf( buf, sizeof( buf ),
                "{\"key\":\"%s\",\"handle\":%llu,\"visible\":%s,\"width_m\":%.5f,"
                "\"transform_type\":{\"id\":%d,\"name\":\"%s\",\"type_error\":%s%s%s},"
                "\"absolute\":{\"origin\":%d,\"m\":[[%.6f,%.6f,%.6f,%.6f],[%.6f,%.6f,%.6f,%.6f],[%.6f,%.6f,%.6f,%.6f]]},"
                "\"absolute_error\":null}",
                key.c_str(),
                (unsigned long long)h,
                visible ? "true" : "false",
                width,
                tid,
                AsterismTransformTypeName( tid ),
                tt_err ? "\"" : "null",
                tt_err ? tt_err : "",
                tt_err ? "\"" : "",
                int( origin ),
                mat.m[0][0], mat.m[0][1], mat.m[0][2], mat.m[0][3],
                mat.m[1][0], mat.m[1][1], mat.m[1][2], mat.m[1][3],
                mat.m[2][0], mat.m[2][1], mat.m[2][2], mat.m[2][3] );
        }
        else
        {
            snprintf( buf, sizeof( buf ),
                "{\"key\":\"%s\",\"handle\":%llu,\"visible\":%s,\"width_m\":%.5f,"
                "\"transform_type\":{\"id\":%d,\"name\":\"%s\"},"
                "\"absolute\":null,\"absolute_error\":\"%s\",\"absolute_error_code\":%d}",
                key.c_str(),
                (unsigned long long)h,
                visible ? "true" : "false",
                width,
                tid,
                AsterismTransformTypeName( tid ),
                vr::VROverlay()->GetOverlayErrorNameFromEnum( ae ),
                int( ae ) );
        }
        return std::string( buf );
    }

    std::string AsterismInspectAll()
    {
        std::string out = "[";
        bool first = true;
        std::scoped_lock lock{ m_mutActiveConnectors };
        for ( COpenVRConnector *pConnector : m_pActiveConnectors )
        {
            for ( COpenVRPlane &plane : pConnector->GetPlanes() )
            {
                if ( plane.IsSubview() )
                    continue;
                if ( !first )
                    out += ",";
                first = false;
                out += AsterismInspectOne( plane );
            }
        }
        out += "]";
        return out;
    }

    COpenVRPlane *AsterismFindPlaneByKey( const std::string &key )
    {
        for ( COpenVRConnector *pConnector : m_pActiveConnectors )
        {
            for ( COpenVRPlane &plane : pConnector->GetPlanes() )
            {
                if ( plane.IsSubview() )
                    continue;
                if ( plane.GetDashboardOverlayKey() == key )
                    return &plane;
            }
        }
        return nullptr;
    }

    static vr::HmdMatrix34_t AsterismMatrixFromPose( float x, float y, float z, float yaw, float pitch, float roll )
    {
        // Yaw/pitch/roll in radians → HmdMatrix34 (OpenVR column-ish layout).
        float cy = cosf( yaw ), sy = sinf( yaw );
        float cp = cosf( pitch ), sp = sinf( pitch );
        float cr = cosf( roll ), sr = sinf( roll );
        vr::HmdMatrix34_t m{};
        m.m[0][0] = cy * cr + sy * sp * sr;
        m.m[0][1] = sr * cp;
        m.m[0][2] = -sy * cr + cy * sp * sr;
        m.m[0][3] = x;
        m.m[1][0] = -cy * sr + sy * sp * cr;
        m.m[1][1] = cr * cp;
        m.m[1][2] = sr * sy + cy * sp * cr;
        m.m[1][3] = y;
        m.m[2][0] = sy * cp;
        m.m[2][1] = -sp;
        m.m[2][2] = cy * cp;
        m.m[2][3] = z;
        return m;
    }

    std::string AsterismHandleCommand( const std::string &line )
    {
        // Commands:
        //   inspect
        //   inspect <overlay-key>
        //   set-test-absolute <overlay-key> <x> <y> <z> <yaw> <pitch> <roll>
        // One explicit set-test-absolute = ONE SetOverlayTransformAbsolute call.
        std::istringstream iss( line );
        std::string cmd;
        iss >> cmd;
        if ( cmd == "inspect" )
        {
            std::string key;
            if ( iss >> key )
            {
                std::scoped_lock lock{ m_mutActiveConnectors };
                COpenVRPlane *p = AsterismFindPlaneByKey( key );
                if ( !p )
                    return std::string( "{\"error\":\"overlay_not_found\",\"key\":\"" ) + key + "\"}\n";
                return AsterismInspectOne( *p ) + "\n";
            }
            return AsterismInspectAll() + "\n";
        }
        if ( cmd == "set-test-absolute" )
        {
            std::string key;
            float x, y, z, yaw, pitch, roll;
            if ( !( iss >> key >> x >> y >> z >> yaw >> pitch >> roll ) )
                return "{\"error\":\"usage\",\"hint\":\"set-test-absolute <key> x y z yaw pitch roll\"}\n";

            std::scoped_lock lock{ m_mutActiveConnectors };
            COpenVRPlane *p = AsterismFindPlaneByKey( key );
            if ( !p )
                return std::string( "{\"error\":\"overlay_not_found\",\"key\":\"" ) + key + "\"}\n";

            vr::VROverlayHandle_t h = p->GetOverlay();
            std::string before = AsterismInspectOne( *p );

            vr::HmdMatrix34_t mat = AsterismMatrixFromPose( x, y, z, yaw, pitch, roll );
            vr::EVROverlayError se = vr::VROverlay()->SetOverlayTransformAbsolute(
                h, vr::TrackingUniverseStanding, &mat );

            // Immediate readback — do not loop/fight SteamVR.
            std::string after = AsterismInspectOne( *p );

            char buf[4096];
            snprintf( buf, sizeof( buf ),
                "{\"cmd\":\"set-test-absolute\",\"key\":\"%s\","
                "\"set_error\":\"%s\",\"set_error_code\":%d,"
                "\"before\":%s,\"after\":%s}\n",
                key.c_str(),
                vr::VROverlay()->GetOverlayErrorNameFromEnum( se ),
                int( se ),
                before.c_str(),
                after.c_str() );
            openvr_log.infof( "ASTERISM set-test-absolute %s -> %s (%d)",
                key.c_str(), vr::VROverlay()->GetOverlayErrorNameFromEnum( se ), int( se ) );
            return std::string( buf );
        }
        return "{\"error\":\"unknown_command\"}\n";
    }

    void AsterismCtrlPoll()
    {
        if ( m_nAsterismCtrlListen < 0 )
            return;
        for ( ;; )
        {
            int cfd = accept4( m_nAsterismCtrlListen, nullptr, nullptr, SOCK_CLOEXEC | SOCK_NONBLOCK );
            if ( cfd < 0 )
                break;
            char buf[512];
            ssize_t n = read( cfd, buf, sizeof( buf ) - 1 );
            std::string reply = "{\"error\":\"empty\"}\n";
            if ( n > 0 )
            {
                buf[n] = 0;
                // Trim trailing newline
                while ( n > 0 && ( buf[n - 1] == '\n' || buf[n - 1] == '\r' ) )
                    buf[--n] = 0;
                reply = AsterismHandleCommand( std::string( buf ) );
            }
            (void)write( cfd, reply.data(), reply.size() );
            close( cfd );
        }
    }
    // --- END ASTERISM_OPENVR_CTRL ---
'''

CTRL_MEMBERS = r'''
    // ASTERISM_OPENVR_CTRL
    int m_nAsterismCtrlListen = -1;
    std::string m_sAsterismCtrlPath;
'''

INCLUDES = r'''
// ASTERISM_OPENVR_CTRL
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <sstream>
'''


def once(hay: str, needle: str, insert: str, *, after: bool = True) -> str:
    if MARKER in hay and insert.strip()[:40] in hay:
        return hay  # already present-ish
    idx = hay.find(needle)
    if idx < 0:
        raise SystemExit(f"anchor not found: {needle[:80]!r}")
    if after:
        at = idx + len(needle)
        return hay[:at] + insert + hay[at:]
    return hay[:idx] + insert + hay[idx:]


def patch_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if "AsterismCtrlInit" in text:
        print(f"already patched: {path}")
        return

    # Includes near top after openvr include if present, else after first #include block.
    if '#include "openvr.h"' in text or "#include <openvr.h>" in text:
        for needle in ('#include "openvr.h"\n', "#include <openvr.h>\n"):
            if needle in text:
                text = once(text, needle, INCLUDES + "\n")
                break
    else:
        # Fallback: after first include
        first = text.find("#include")
        end = text.find("\n", first)
        text = text[: end + 1] + INCLUDES + "\n" + text[end + 1 :]

    # Public accessor on COpenVRPlane
    if "GetDashboardOverlayKey" not in text:
        text = once(
            text,
            "vr::VROverlayHandle_t GetOverlay() const { return m_hOverlay; }",
            "\n\t\tconst std::string &GetDashboardOverlayKey() const { return m_sDashboardOverlayKey; }",
        )

    # Insert methods before ProcessVRInput or before private members — put before FlipHandlerThread join area.
    # Hook: call AsterismCtrlInit at end of Init() success path / PostInit.
    if "AsterismCtrlInit();" not in text:
        # PostInit return true before closing
        if "virtual bool PostInit() override" in text:
            # Find first "return true;" after PostInit — fragile; use unique black texture abort block end
            anchor = "m_pBlackTexture = vulkan_create_flat_texture( g_nOutputWidth, g_nOutputHeight, 0, 0, 0, cv_vr_transparent_backing ? 0 : 255 );"
            idx = text.find(anchor)
            if idx < 0:
                raise SystemExit("PostInit texture anchor not found")
            # Insert before the final return true of PostInit
            ret = text.find("return true;", idx)
            text = text[:ret] + "\t\tAsterismCtrlInit();\n\n\t\t" + text[ret:]

    # Poll in FlipHandlerThread after ProcessVRInput();
    if "AsterismCtrlPoll();" not in text:
        text = once(text, "ProcessVRInput();", "\n\t\t\tAsterismCtrlPoll();")

    # Methods: insert before private: section of COpenVRBackend — hard.
    # Insert just before "void ProcessVRInput()"
    if "void AsterismCtrlInit()" not in text:
        text = once(text, "void ProcessVRInput()", CTRL_METHODS + "\n\t", after=False)

    # Members before m_FlipHandlerThread
    if "m_nAsterismCtrlListen" not in text:
        text = once(
            text,
            "std::thread m_FlipHandlerThread;",
            CTRL_MEMBERS + "\n\t",
            after=False,
        )

    # Destructor cleanup
    if "m_nAsterismCtrlListen" in text and "unlink( m_sAsterismCtrlPath" not in text.split("virtual ~COpenVRBackend()")[1][:800]:
        text = once(
            text,
            "m_bRunning = false;",
            """
\t\tif ( m_nAsterismCtrlListen >= 0 )
\t\t{
\t\t\tclose( m_nAsterismCtrlListen );
\t\t\tm_nAsterismCtrlListen = -1;
\t\t}
\t\tif ( !m_sAsterismCtrlPath.empty() )
\t\t\tunlink( m_sAsterismCtrlPath.c_str() );
""",
        )

    path.write_text(text, encoding="utf-8")
    print(f"patched {path}")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "gamescope-asterism" / "src")
    target = root / "src" / "Backends" / "OpenVRBackend.cpp"
    if not target.is_file():
        # Some trees use different layout
        candidates = list(root.rglob("OpenVRBackend.cpp"))
        if not candidates:
            print(f"OpenVRBackend.cpp not found under {root}", file=sys.stderr)
            return 1
        target = candidates[0]
    patch_file(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
