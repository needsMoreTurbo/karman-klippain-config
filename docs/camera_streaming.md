# Camera Streaming — Setup & Troubleshooting

**Machine:** Karman (Voron 2.4, Klippain) · **Camera:** Logitech C920 (USB UVC), externally mounted looking into the enclosure · **Host:** Raspberry Pi (aarch64) · **Deployed stack:** standalone **go2rtc** (hardware H.264 → WebRTC) → Mainsail. Crowsnest is installed but its `[cam 1]` is commented out (§5).

This document captures how to get low-latency, sharp, reliable video off the C920, and how to diagnose the lag/focus problems seen on Karman. It splits the problem into two independent layers — **frame *production* at the camera** and **frame *transport* to the browser** — because fixing one does nothing for the other, and both were degraded here.

---

## 1. Symptoms observed

- Video is **laggy / choppy**, but **host CPU is low** during streaming.
- The camera shows **focus hunting / breathing** (image softens then re-sharpens).
- WebRTC was tried previously but hit **browser-compatibility issues**. *(Root cause found: the camera is on `mode: ustreamer`, which serves MJPEG only and **cannot do WebRTC at all** — it was never available regardless of browser. See §5.2.)*
- During a Shake&Tune resonance test the camera went very laggy **at the same moment** `mcu` shut down with `Timer too close` — a shared host-load symptom (see §6).

---

## 2. Mental model: two independent layers

| Layer | What it controls | Symptoms when broken | Fixes |
|---|---|---|---|
| **Production** (the camera) | How many usable frames the C920 emits, and whether they're sharp | Low framerate, choppiness, soft/hunting focus — *with low CPU* | Lock focus, pin a compressed format, light the scene (§3) |
| **Transport** (the pipeline) | How those frames reach the browser and at what latency | High latency, per-browser failures, CPU multiplication across viewers | Hardware H.264 + WebRTC via camera-streamer / go2rtc (§4, §5) |

**Key diagnostic:** "laggy **but low CPU**" rules out software encoding as the cause. The C920 has hardware MJPEG *and* H.264 encoders, so an idle CPU means frames are being produced cheaply — the problem is either that too **few** frames are produced (production) or that they're delivered over a **slow transport**. Both applied here.

---

## 3. Camera-level fixes (frame production)

A common root cause of both the lag *and* the focus hunting is **"auto" everything on a camera pointed at a fixed scene**. The bed is always the same distance, so autofocus is pure downside — **lock it**. Exposure is a judgement call: on Karman it's left on **auto** and the fix is to light the scene (see §3.1), rather than pinning a value that goes wrong when room light changes.

### 3.1 Auto-exposure is silently dropping framerate (primary lag cause)
In dim light the C920 lengthens exposure by **cutting frame rate** — 30fps can collapse to ~5–7fps. Fewer frames = choppy video **and** low CPU, which matches the symptom exactly. An external mount often sees less light than expected.

Quick test: brighten the scene; if it smooths out, this is it. It *can* be locked:
```
v4l2-ctl -d /dev/video0 --set-ctrl=auto_exposure=1            # 1 = manual (name varies; some firmwares use exposure_auto=1)
v4l2-ctl -d /dev/video0 --set-ctrl=exposure_time_absolute=250
v4l2-ctl -d /dev/video0 -p 30                                 # force 30 fps
```

> **Karman's choice:** exposure is left on **auto** (not locked in `crowsnest.conf`). Locking exposure to a fixed value in a room with changing light makes the image too dark/bright as conditions shift; auto-exposure keeps brightness usable at the cost of framerate in dim light. The preferred fix here is **more light on the scene** (so auto-exposure keeps a high framerate) rather than a hard exposure lock. Revisit only if low framerate persists under good lighting.

### 3.2 Autofocus hunting (image quality, *not* lag)
Autofocus does **not** add stream latency and barely touches CPU — so fixing it will not smooth the choppiness. But on a fixed-distance printer cam it's pure downside (hunting/breathing), so set focus once, manually, and lock it forever:
```
v4l2-ctl -d /dev/video0 --set-ctrl=focus_automatic_continuous=0   # older kernels: focus_auto=0
v4l2-ctl -d /dev/video0 --set-ctrl=focus_absolute=30              # ~0–250, higher = closer; tune for a sharp bed
```

### 3.3 USB path (external mount)
An external mount usually means a **long cable or extension**, and the C920 is bandwidth-hungry. A marginal cable/hub causes retransmits and dropped frames — lag with low CPU. Checks:
- Use a single quality cable; avoid cheap extensions.
- Give the camera **its own USB port**, not a hub shared with the Beacon + Nitehawk.
- `dmesg | grep -i usb` — look for reset/`disconnect` spam.

### 3.4 Format & resolution — confirmed C920 capabilities
`v4l2-ctl --list-formats-ext` on Karman's C920 (index0) reports:

| Format | 1280×720 | 1920×1080 | Notes |
|---|---|---|---|
| **H264** (hardware) | 30 fps | **30 fps** | compressed, low CPU — use this for go2rtc passthrough (§5) |
| **MJPG** (hardware) | 30 fps | 30 fps | compressed, higher bandwidth than H264 |
| **YUYV** (raw) | 10 fps *max* | **5 fps** *max* | uncompressed — saturates USB2, hard fps cap |

Consequences:
- **Hardware H.264 is available at 1080p30** → full-res, full-framerate go2rtc passthrough is viable; no need to compromise resolution for smoothness.
- **Never let capture negotiate YUYV.** Raw is bandwidth-starved on USB2 and caps at **5fps @1080p / 10fps @720p** *regardless of lighting* — an independent "laggy, low CPU" cause. Moving to `camera-streamer`/go2rtc with H264 avoids raw entirely; `ustreamer` should be pinned to MJPG.
- A `max_fps:` lower than 30 (Karman was at 15) is a **self-imposed** cap — the hardware does 30 in both compressed formats.

### 3.5 Where the settings live (device path, focus lock)
The stable device path and the focus lock are the two camera-level settings that persist. **On Karman these now live in the go2rtc systemd unit (§5.4), not crowsnest** — `crowsnest.conf`'s `[cam 1]` is commented out so go2rtc can own the camera.

- **Device:** `/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_E98816AF-video-index0` — the stable `by-id` path (find via `ls /dev/v4l/by-id/`), not `/dev/video0`, which can shuffle across reboots. `index0` is the video node; `index1` is UVC metadata (not streamable).
- **Focus lock:** `focus_automatic_continuous=0,focus_absolute=30`. `v4l2-ctl` from a shell resets on replug/reboot, and go2rtc/ffmpeg can't set focus, so it's applied via the unit's `ExecStartPre` (§5.4). `focus_absolute=30` is a **starting value** — tune against the actual scene (~0–250, higher = closer). Control **names vary by kernel/firmware**; run `v4l2-ctl -d <device> --list-ctrls` first.
- **Historical (crowsnest route):** when crowsnest owned the camera, these went in the `[cam 1]` `v4l2ctl:` line and were applied with `sudo systemctl restart crowsnest`. That block is preserved commented-out in `crowsnest.conf` if you ever revert.

---

## 4. Transport: MJPEG vs. WebRTC vs. hardware H.264

MJPEG is simple but high-latency and bandwidth-heavy. The goal is **sub-second latency at near-zero CPU**, which means using the C920's **onboard hardware H.264** encoder and passing it through untranscoded (`-c copy`) to a WebRTC transport. No re-encode = the Pi stays idle (the same "low CPU" property already observed) but with low latency instead of lag.

Only **camera-streamer** and **go2rtc** can do H.264→WebRTC passthrough; legacy `ustreamer`/`mjpg-streamer` cannot.

---

## 5. Deployed transport: standalone go2rtc

**This is what Karman runs.** `camera-streamer`'s built-in WebRTC would not play in Chromium, so the camera moved to a **standalone go2rtc** service. Crowsnest is left installed but its `[cam 1]` is commented out (only one process can open `/dev/video0`), so go2rtc owns the camera. Crowsnest 4.2 *bundles* go2rtc, but its native wiring is version-specific; a standalone service is deterministic and drops cleanly into Mainsail.

### 5.1 Why go2rtc
1. **Solves browser compatibility by design.** Instead of betting on one transport, go2rtc negotiates a **fallback chain per browser**: WebRTC → WebRTC-over-TCP → MSE → MJPEG/HLS. Chrome/Edge get true WebRTC (~200ms); Firefox/Safari that choke on WebRTC quietly fall back to MSE (~0.5–1s) — still far better than laggy MJPEG. This is the direct fix for "Chromium won't play camera-streamer."
2. **Hardware H.264 passthrough** (`#video=copy`) → low CPU + low latency (§4).
3. **One read, many viewers.** go2rtc opens the camera once and restreams to all clients, killing the "every open browser tab spawns its own stream" CPU/USB multiplication — relevant to the resonance-test shutdown (§6).

### 5.2 The config (git-tracked)
[`go2rtc.yaml`](../go2rtc.yaml) lives in the repo root (= `~/printer_data/config/`), so it deploys via `GIT_PULL` and is editable from Mainsail's file manager. Karman's actual config:
```yaml
streams:
  # #video=copy passes the C920's HARDWARE H.264 straight through: no transcode,
  # near-zero CPU, and H.264 is exactly what browsers play over WebRTC.
  printer:
    - ffmpeg:device?video=/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_E98816AF-video-index0&input_format=h264&video_size=1280x720&framerate=30#video=copy

api:
  listen: ":1984"        # go2rtc dashboard + Mainsail WebRTC endpoint
  origin: "*"            # allow cross-origin: Mainsail (:80) embeds go2rtc (:1984).
                         # Without this the dashboard works but Mainsail hangs on "connecting".

webrtc:
  listen: ":8555"        # WebRTC media (TCP/UDP)
  candidates:
    - 192.168.1.240:8555 # LAN address so the browser knows where to connect
```
Field-by-field, the three things that make this work:
- **`ffmpeg:device?...#video=copy`** — reads the C920's H.264 directly and passes it through with no transcode (the §3.4 hardware format; never YUYV).
- **`api.origin: "*"`** — required because Mainsail and go2rtc are different origins (§5.6 gotcha).
- **`webrtc.candidates`** — advertises the Pi's LAN I:port so the browser's WebRTC can reach the media stream.

Stream name is **`printer`** — this is the `src=printer` you reference from Mainsail and the snapshot URL.

### 5.3 Install (Pi, arm64)
go2rtc uses system `ffmpeg` for V4L2 capture:
```bash
sudo apt update && sudo apt install -y ffmpeg
mkdir -p ~/go2rtc && cd ~/go2rtc
wget -O go2rtc https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_arm64
chmod +x go2rtc
```
> `uname -m` reports `aarch64` = `arm64` (same thing) → use the `arm64` binary.

### 5.4 systemd service — with the focus lock
Moving off crowsnest **loses the `v4l2ctl` focus lock** (go2rtc/ffmpeg can't set V4L2 focus controls). It's re-applied here as `ExecStartPre`, which runs `v4l2-ctl` before go2rtc opens the device:
```ini
# /etc/systemd/system/go2rtc.service
[Unit]
Description=go2rtc
After=network.target

[Service]
User=ernst
ExecStartPre=/usr/bin/v4l2-ctl -d /dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_E98816AF-video-index0 --set-ctrl=focus_automatic_continuous=0 --set-ctrl=focus_absolute=30
ExecStart=/home/ernst/go2rtc/go2rtc -config /home/ernst/printer_data/config/go2rtc.yaml
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now go2rtc
```

### 5.5 Deploy order (device-contention matters)
Only one process can open `/dev/video0`, so the sequence is strict:
1. `GIT_PULL` — pulls the commented `crowsnest.conf` + `go2rtc.yaml`.
2. `sudo systemctl restart crowsnest` — **releases** the camera.
3. `sudo systemctl enable --now go2rtc` — now it can grab the device.

If go2rtc logs `device or resource busy` (`journalctl -u go2rtc -e`), crowsnest never let go — recheck step 1/2.

### 5.6 Verify, then add to Mainsail
- Open **`http://192.168.1.240:1984`** (go2rtc dashboard) → `printer` stream → WebRTC link. If it plays in Chromium here, the pipeline works.
- Mainsail → Settings → **Webcams** → Add:
  - **Service** = `WebRTC (go2rtc)`
  - **URL Stream** = `http://192.168.1.240:1984/?src=printer` — the go2rtc **base** URL, *not* `.../api/ws?...`. Mainsail resolves `api/ws` relative to what you enter; if you include `/api/ws` it doubles to `/api/api/ws` and the socket fails. `src` must match the stream name in `go2rtc.yaml`.
  - **URL Snapshot** = `http://192.168.1.240:1984/api/frame.jpeg?src=printer` (the default `/webcam/?action=snapshot` is crowsnest and is now dead)
- moonraker-timelapse (if used): point its snapshot URL at `http://localhost:1984/api/frame.jpeg?src=printer`.

> **Gotcha — Mainsail hangs on "connecting" but the go2rtc dashboard works:** this is **cross-origin**. The dashboard (`:1984`) is same-origin with the API; Mainsail (`:80`) is not, and the browser blocks the cross-origin WebSocket unless go2rtc sends CORS headers. Fix: `api.origin: "*"` in `go2rtc.yaml` (already set), then restart go2rtc.

### 5.7 The caveat that ties the layers together
go2rtc is a **transport layer, not a camera driver** — it faithfully streams whatever the C920 hands it. If a §3.1 auto-exposure framerate drop is active (dim scene), go2rtc will dutifully deliver a smooth **5fps** and it will still feel laggy. **Fix production (§3) *and* transport (§5).** They address different halves.

---

## 6. Interaction with resonance testing (`Timer too close`)

Worth recording because it bit Karman: a Shake&Tune run shut `mcu` down with `Timer too close` while the camera simultaneously went laggy. Both are symptoms of one cause — **host CPU/USB saturation**:

- Resonance test start = ADXL sample firehose + heavy step generation.
- The C920 stream (plus the Beacon streaming over USB) competes for the same CPU/USB.
- The Pi can't feed step data to `mcu` on schedule → `Timer too close`; the camera starves at the same instant → visible lag.

**Before any resonance test, stop the camera** with `sudo systemctl stop go2rtc` (restart it after). Note go2rtc's ffmpeg capture runs while any client is connected and stops shortly after the last one disconnects — so closing browser tabs *helps*, but stopping the service is the reliable way to fully release the CPU/USB during a test. Restart with `sudo systemctl start go2rtc`.

---

## 7. Verification commands (read-only)

Run on the Pi (`ernst@192.168.1.240`) when the printer is idle:
```
v4l2-ctl -d /dev/video0 --list-formats-ext   # does the C920 expose H.264? at what fps?
v4l2-ctl -d /dev/video0 --list-ctrls         # exact control names + ranges for exposure/focus
dmesg | grep -i usb                          # USB resets / disconnects
crowsnest --version                          # Crowsnest 4.x? (go2rtc bundled)
```

---

## 8. Checklist

Done — go2rtc streaming is live and playing in Chromium via Mainsail (WebRTC):
- [x] Comment out `crowsnest.conf` `[cam 1]` so go2rtc can own the camera.
- [x] Add git-tracked **`go2rtc.yaml`** (720p30, hardware H.264 `#video=copy`, `api.origin "*"`).
- [x] Pin the stable **`/dev/v4l/by-id/...index0`** device path.
- [x] Leave **exposure on auto** (see §3.1).
- [x] Install ffmpeg + **go2rtc arm64** binary (§5.3).
- [x] Create **`go2rtc.service`** with the focus-lock `ExecStartPre` (§5.4).
- [x] Deploy: `GIT_PULL` → `restart crowsnest` → `enable --now go2rtc` (§5.5).
- [x] Add **WebRTC (go2rtc)** webcam in Mainsail — URL Stream `http://192.168.1.240:1984/?src=printer`, snapshot `.../api/frame.jpeg?src=printer` (§5.6).

Remaining / ongoing:
- [ ] Tune **`focus_absolute`** in the `go2rtc.service` `ExecStartPre` for a sharp bed; verify **30fps** under good lighting.
- [ ] Give the camera its **own USB port**; check `dmesg` for resets.
- [ ] **`sudo systemctl stop go2rtc` before resonance tests** (§6).
- [ ] moonraker-timelapse (if used): snapshot URL → `http://localhost:1984/api/frame.jpeg?src=printer`.
