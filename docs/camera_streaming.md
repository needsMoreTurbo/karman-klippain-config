# Camera Streaming — Setup & Troubleshooting

**Machine:** Karman (Voron 2.4, Klippain) · **Camera:** Logitech C920 (USB UVC), externally mounted looking into the enclosure · **Host:** Raspberry Pi · **Stack:** Crowsnest → camera-streamer / go2rtc → Mainsail/Fluidd.

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
| **Production** (the camera) | How many usable frames the C920 emits, and whether they're sharp | Low framerate, choppiness, soft/hunting focus — *with low CPU* | Lock exposure, framerate, focus (§3) |
| **Transport** (the pipeline) | How those frames reach the browser and at what latency | High latency, per-browser failures, CPU multiplication across viewers | Hardware H.264 + WebRTC via go2rtc (§4, §5) |

**Key diagnostic:** "laggy **but low CPU**" rules out software encoding as the cause. The C920 has hardware MJPEG *and* H.264 encoders, so an idle CPU means frames are being produced cheaply — the problem is either that too **few** frames are produced (production) or that they're delivered over a **slow transport**. Both applied here.

---

## 3. Camera-level fixes (frame production)

The root cause of both the lag *and* the focus hunting is **"auto" everything on a camera pointed at a fixed scene**. The bed is always the same distance and the lighting is roughly constant, so autofocus and auto-exposure only add instability. Lock them.

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

### 3.5 Persisting the settings — *where they go*
`v4l2-ctl` run from a shell resets on replug/reboot. The permanent home for these is the **`v4l2ctl:` parameter inside the camera's section of `crowsnest.conf`** (repo root, tracked). Karman's camera is the `[cam 1]` section; a commented `#v4l2ctl:` placeholder already exists there — uncomment it and append the settings comma-separated:
```ini
[cam 1]
mode: camera-streamer                   # ustreamer cannot do WebRTC — see §5.2
device: /dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_...-index0   # stable path; NOT /dev/video0
resolution: 1280x720
max_fps: 30
v4l2ctl: focus_automatic_continuous=0,focus_absolute=30   # focus locked; exposure left on auto (see §3.1)
```
Notes:
- **`device:`** — use the `/dev/v4l/by-id/...` path (find via `ls /dev/v4l/by-id/`), not `/dev/video0`, which can shuffle across reboots.
- Control **names vary by kernel/firmware**. Run `v4l2-ctl -d /dev/video0 --list-ctrls` first and use the exact names and value ranges it reports.
- **Applying it:** edit here → commit/push → `GIT_PULL` on the Pi, then **`sudo systemctl restart crowsnest`**. Crowsnest is a separate service — `FIRMWARE_RESTART` / `GIT_PULL` alone will **not** reload camera config.

---

## 4. Transport: MJPEG vs. WebRTC vs. hardware H.264

MJPEG is simple but high-latency and bandwidth-heavy. The goal is **sub-second latency at near-zero CPU**, which means using the C920's **onboard hardware H.264** encoder and passing it through untranscoded (`-c copy`) to a WebRTC transport. No re-encode = the Pi stays idle (the same "low CPU" property already observed) but with low latency instead of lag.

Only **camera-streamer** and **go2rtc** can do H.264→WebRTC passthrough; legacy `ustreamer`/`mjpg-streamer` cannot.

---

## 5. Recommended target: go2rtc

`go2rtc` is the most robust path for Karman, and directly addresses the earlier WebRTC browser trouble.

### 5.1 Why it fits
1. **Solves browser compatibility by design.** Instead of betting on one transport, go2rtc negotiates a **fallback chain per browser**: WebRTC → WebRTC-over-TCP → MSE → MJPEG/HLS. Chrome/Edge get true WebRTC (~200ms); Firefox/Safari that choke on WebRTC quietly fall back to MSE (~0.5–1s) — still far better than laggy MJPEG. You stop chasing per-browser quirks.
2. **Hardware H.264 passthrough** → low CPU + low latency (§4).
3. **One read, many viewers.** go2rtc opens the camera once and restreams to all clients, killing the "every open browser tab spawns its own stream" CPU/USB multiplication — relevant to the resonance-test shutdown (§6).

### 5.2 Integration
No need to rip anything out: **Crowsnest 4.x bundles go2rtc**, and Mainsail/Fluidd both support a go2rtc/WebRTC camera service type. Enable go2rtc in Crowsnest (or run it standalone), define the C920 stream, then set the camera's service to WebRTC in the UI.

Rough standalone `go2rtc.yaml`, passing through hardware H.264 with no transcode:
```yaml
streams:
  c920:
    - exec:ffmpeg -hide_banner -f v4l2 -input_format h264 -video_size 1280x720 -framerate 30 -i /dev/video0 -c:v copy -f rtsp {output}
```

### 5.3 The caveat that ties the layers together
go2rtc is a **transport layer, not a camera driver** — it faithfully streams whatever the C920 hands it. If the §3.1 auto-exposure framerate drop is still active, go2rtc will dutifully deliver a smooth **5fps** and it will still feel laggy. **Fix production (§3) *and* transport (§5).** They address different halves.

---

## 6. Interaction with resonance testing (`Timer too close`)

Worth recording because it bit Karman: a Shake&Tune run shut `mcu` down with `Timer too close` while the camera simultaneously went laggy. Both are symptoms of one cause — **host CPU/USB saturation**:

- Resonance test start = ADXL sample firehose + heavy step generation.
- The C920 stream (plus the Beacon streaming over USB) competes for the same CPU/USB.
- The Pi can't feed step data to `mcu` on schedule → `Timer too close`; the camera starves at the same instant → visible lag.

**Before any resonance test, stop the camera stream** (close all webcam browser tabs, or `sudo systemctl stop crowsnest`) to free the host. This is the main reason to prefer a **single-read restreamer (go2rtc)** over per-tab MJPEG streams generally.

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

- [ ] Lock **focus** (`focus_automatic_continuous=0`, fixed `focus_absolute`).
- [ ] Leave **exposure on auto**; add light to the scene if framerate drops (lock only as a last resort — see §3.1).
- [ ] Verify the camera actually produces **30fps** under good lighting.
- [ ] Give the camera its **own USB port**; check `dmesg` for resets.
- [ ] Consider dropping to **720p** if 1080p is flaky.
- [ ] Persist v4l2 settings in Crowsnest's **`v4l2ctl:`** line.
- [ ] Move transport to **go2rtc** with hardware **H.264 passthrough** (`-c copy`).
- [ ] Test WebRTC in **Chrome**; rely on go2rtc fallback for Firefox/Safari.
- [ ] **Stop the camera stream before resonance tests.**
