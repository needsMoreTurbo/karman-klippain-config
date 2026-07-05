# Camera Streaming — Karman

This document captures how to get low-latency, sharp, reliable video off the C920, and how to diagnose the lag/focus problems seen on Karman. It splits the problem into two independent layers — **frame *production* at the camera** and **frame *transport* to the browser** — because fixing one does nothing for the other, and both were degraded here.

**At a glance:** Logitech C920 (USB UVC, serial `E98816AF`), externally mounted looking into the enclosure, on a Raspberry Pi (`aarch64`). It streams via a **standalone go2rtc** service (hardware H.264 → WebRTC) into Mainsail. Crowsnest is still installed but its camera is disabled so go2rtc can own the device.

---

## 1. Overview of the config

| Thing | Value |
|---|---|
| Camera | Logitech C920, `/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_E98816AF-video-index0` |
| Host | Raspberry Pi, `aarch64`, user `ernst`, LAN `192.168.1.240` |
| Transport | standalone **go2rtc** (systemd service), hardware H.264 passthrough → WebRTC |
| Config | [`go2rtc.yaml`](../go2rtc.yaml) in repo root (= `~/printer_data/config/`), git-tracked |
| Resolution / fps | 720p30 (H.264 also supports 1080p30 — see §5.3) |
| Focus | locked (fixed scene); applied by the go2rtc systemd unit `ExecStartPre` |
| Exposure | left on **auto** (deliberate — see §5.2) |
| Crowsnest | v4.2.0, installed but `[cam 1]` commented out in [`crowsnest.conf`](../crowsnest.conf) |
| Mainsail webcam | Service `WebRTC (go2rtc)`, stream `printer` |

**Two-layer mental model** (used throughout): *production* = how many usable/sharp frames the C920 emits; *transport* = how those frames reach the browser and at what latency. Key diagnostic: **"laggy but low host CPU"** rules out software encoding — the C920 has hardware H.264/MJPEG, so idle CPU means frames are produced cheaply; the fault is either too few frames (production) or a slow transport.

---

## 2. The default setup: Crowsnest + camera-streamer/ustreamer

This is what MainsailOS ships and what Karman *used* to run — documented here as the baseline and fallback.

- **Crowsnest** is the standard webcam manager. It's configured in [`crowsnest.conf`](../crowsnest.conf) via `[cam N]` sections and runs a capture backend per camera, exposing the stream through Mainsail's `/webcam/` nginx proxy. It's UI-adjacent, survives updates, and handles snapshots automatically.
- **Backends:**
  - `ustreamer` — MJPEG + snapshots only. Simple, works on any device, but **no WebRTC** → high latency, bandwidth-heavy.
  - `camera-streamer` — MJPEG *plus* WebRTC + hardware H.264 (RPi/RPi-OS only). Lower latency in theory.
- **Camera tuning** lives in the cam's `v4l2ctl:` line (focus, exposure, etc.), applied on `sudo systemctl restart crowsnest`.
- **Mainsail** picks a matching service type per webcam (`MJPEG-Streamer`, `WebRTC (camera-streamer)`, …) pointed at the `/webcam/` path.

**Why Karman left it:** on `ustreamer` there's no WebRTC at all; switching to `camera-streamer` gave WebRTC that **would not play in Chromium** (connection just never established). Rather than debug camera-streamer's WebRTC, the camera moved to go2rtc (§3). The old `[cam 1]` block is preserved commented-out in `crowsnest.conf` for easy revert.

---

## 3. Karman's current setup: standalone go2rtc

The C920 is streamed by a **standalone go2rtc systemd service**, not Crowsnest. go2rtc opens the camera's **hardware H.264** and passes it through untranscoded (`#video=copy`) to a WebRTC transport with a per-browser fallback chain. Only one process can open `/dev/video0`, so Crowsnest's `[cam 1]` is commented out and go2rtc owns the device.

```
C920 (hardware H.264)
   │  ffmpeg:device … #video=copy   (no transcode, ~0% CPU)
   ▼
go2rtc  ──api :1984──►  Mainsail webcam  (WebRTC (go2rtc))
        └─webrtc :8555►  browser media
```

### Pros / cons vs. the Crowsnest default

**Pros**
- **Actually plays in Chromium.** go2rtc negotiates a per-browser fallback: WebRTC → WebRTC/TCP → MSE → MJPEG/HLS. Chrome/Edge get true WebRTC (~200 ms); Firefox/Safari fall back to MSE (~0.5–1 s) — still far better than laggy MJPEG.
- **Near-zero CPU + low latency.** `#video=copy` passes hardware H.264 straight through — no re-encode.
- **Single read, many viewers.** go2rtc opens the camera once and restreams to every client, so extra browser tabs don't multiply CPU/USB load (relevant to the resonance-test shutdown, §5.6).
- **Future-proof outputs.** Same stream is available as RTSP/WebRTC/MSE/HLS for other tools (recording, HA, a second UI) with no extra camera reads.

**Cons**
- **Not managed by Crowsnest/Mainsail UI.** It's a hand-rolled systemd service + YAML; Crowsnest updates won't touch it, and the go2rtc binary is updated manually.
- **Device contention is manual.** Crowsnest's cam must stay disabled or the two fight over `/dev/video0` (`device or resource busy`).
- **Focus lock is displaced.** go2rtc/ffmpeg can't set V4L2 controls, so the focus lock had to move into the systemd unit's `ExecStartPre` (§4.4) instead of a tidy `v4l2ctl:` line.
- **Snapshots/timelapse need manual wiring.** The `/webcam/?action=snapshot` proxy is gone; snapshot URLs point at go2rtc's `frame.jpeg` endpoint instead.
- **Cross-origin footgun.** Mainsail (:80) embedding go2rtc (:1984) needs `api.origin: "*"` or it silently hangs on "connecting" (§4.6).

**Net:** more moving parts and manual upkeep, bought in exchange for a WebRTC stream that actually works, at low latency and low CPU.

---

## 4. Replicating the setup

### 4.1 Prerequisites
- Raspberry Pi (`aarch64` here — `uname -m` reports `aarch64`, which is the same as `arm64`).
- The camera's stable device path: `ls /dev/v4l/by-id/` → use the `...-video-index0` node (`index1` is UVC metadata, not streamable).

### 4.2 Release the camera from Crowsnest
Comment out the `[cam 1]` section in [`crowsnest.conf`](../crowsnest.conf) (keep `[crowsnest]` itself), then deploy and restart so Crowsnest lets go of `/dev/video0`:
```bash
GIT_PULL                          # brings the commented [cam 1]
sudo systemctl restart crowsnest  # releases the camera
```

### 4.3 Install go2rtc + ffmpeg
go2rtc uses system `ffmpeg` for V4L2 capture:
```bash
sudo apt update && sudo apt install -y ffmpeg
mkdir -p ~/go2rtc && cd ~/go2rtc
wget -O go2rtc https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_arm64
chmod +x go2rtc
./go2rtc -version   # sanity check
```

### 4.4 Config: `go2rtc.yaml`
Lives in the repo root (= `~/printer_data/config/`), so it deploys via `GIT_PULL` and is editable from Mainsail's file manager. Karman's actual config:
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
The three load-bearing bits: **`#video=copy`** (H.264 passthrough, never YUYV — see §5.3), **`api.origin: "*"`** (cross-origin, §4.6), and **`webrtc.candidates`** (advertises the Pi's LAN address so the browser can reach the media). Stream name is **`printer`** — that's the `src=printer` referenced from Mainsail and the snapshot URL.

### 4.5 systemd service (carries the focus lock)
Because go2rtc/ffmpeg can't set V4L2 focus, the focus lock is re-applied as `ExecStartPre`, which runs `v4l2-ctl` before go2rtc opens the device:
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

### 4.6 Deploy order (device contention matters)
Only one process can open `/dev/video0`, so the order is strict:
```bash
sudo systemctl daemon-reload
GIT_PULL                              # commented crowsnest.conf + go2rtc.yaml
sudo systemctl restart crowsnest      # RELEASES the camera
sudo systemctl enable --now go2rtc    # now it can grab the device
```
If go2rtc logs `device or resource busy` (`journalctl -u go2rtc -e`), Crowsnest never let go — recheck the pull actually commented `[cam 1]`.

### 4.7 Verify, then wire into Mainsail
1. Open **`http://192.168.1.240:1984`** (go2rtc dashboard) → `printer` → WebRTC link. If it plays in Chromium here, the pipeline works.
2. Mainsail → Settings → **Webcams** → Add:
   - **Service** = `WebRTC (go2rtc)`
   - **URL Stream** = `http://192.168.1.240:1984/?src=printer` — the go2rtc **base** URL, *not* `.../api/ws?...`. Mainsail resolves `api/ws` relative to what you enter; if you include `/api/ws` it doubles to `/api/api/ws` and the socket fails.
   - **URL Snapshot** = `http://192.168.1.240:1984/api/frame.jpeg?src=printer` (plain HTTP GET — takes the full path, no doubling).

> **Gotcha — Mainsail hangs on "connecting" but the dashboard works:** cross-origin. The dashboard (:1984) is same-origin with the API; Mainsail (:80) is not, so the browser blocks the WebSocket unless go2rtc sends CORS headers → `api.origin: "*"`, then restart go2rtc.

---

## 5. Adjusting the setup

### 5.1 Focus
Fixed scene → lock focus (autofocus only adds hunting/breathing; it does **not** affect latency). It's set in the systemd `ExecStartPre` (§4.5):
```
--set-ctrl=focus_automatic_continuous=0 --set-ctrl=focus_absolute=30
```
`focus_absolute` runs ~0–250 (higher = closer). Tune it: `sudo v4l2-ctl -d <device> --set-ctrl=focus_absolute=NN` live, eyeball the bed, then bake the winning value into the unit and `sudo systemctl restart go2rtc`. Confirm control names first with `v4l2-ctl -d <device> --list-ctrls` (they vary by kernel/firmware — older kernels use `focus_auto`).

### 5.2 Light / exposure
Exposure is deliberately **auto** on Karman. In dim light the C920 raises exposure by **cutting frame rate** (30fps → ~5–7fps) — choppy video with low CPU. The fix here is **more light on the scene**, not a hard exposure lock (a fixed exposure goes wrong when room light changes). If you ever want to lock it anyway:
```
sudo v4l2-ctl -d <device> --set-ctrl=auto_exposure=1 --set-ctrl=exposure_time_absolute=250
```
Add those as extra `--set-ctrl` args on the `ExecStartPre` line to persist. Revisit only if framerate stays low under good lighting.

### 5.3 Resolution / framerate / format
Confirmed C920 capabilities (`v4l2-ctl --list-formats-ext`, index0):

| Format | 1280×720 | 1920×1080 | Notes |
|---|---|---|---|
| **H264** (hardware) | 30 fps | **30 fps** | what we use (`#video=copy`), low CPU |
| **MJPG** (hardware) | 30 fps | 30 fps | compressed, higher bandwidth |
| **YUYV** (raw) | 10 fps *max* | **5 fps** *max* | uncompressed — saturates USB2, hard fps cap |

- To go **1080p30**, change `video_size=1920x1080` in `go2rtc.yaml` and restart go2rtc — H.264 supports it. 720p just keeps USB/bandwidth light.
- **Never let capture fall to YUYV** — raw is USB2-starved and caps at 5fps regardless of lighting. `input_format=h264` in the config pins it, so this only bites if you edit the source line.

### 5.4 USB path
External mount = likely a long cable. The C920 is bandwidth-hungry; a marginal cable/hub causes retransmits and dropped frames (lag, low CPU). Give it its **own USB port** (not a hub shared with the Beacon + Nitehawk) and check `dmesg | grep -i usb` for reset/`disconnect` spam.

### 5.5 Snapshots / timelapse
- Mainsail snapshot: `http://192.168.1.240:1984/api/frame.jpeg?src=printer`.
- moonraker-timelapse (if enabled): point its snapshot URL at `http://localhost:1984/api/frame.jpeg?src=printer` (localhost, runs on the Pi).

### 5.6 Stopping the camera for resonance tests
A Shake&Tune run once shut `mcu` down with `Timer too close` while the camera went laggy — both symptoms of **host CPU/USB saturation** (ADXL firehose + step generation + camera stream competing). Before any resonance test:
```bash
sudo systemctl stop go2rtc     # restart with `start` afterwards
```
go2rtc's ffmpeg capture runs while any client is connected and stops shortly after the last disconnect, so closing tabs helps — but stopping the service reliably frees the host.

---

## 6. Potential future improvements

- **Proxy go2rtc under Mainsail's `/webcam/` path** (nginx reverse proxy) so it's same-origin — removes the `origin: "*"` requirement, cleans up the URLs, and makes remote access (via a VPN/tunnel to Mainsail) work without exposing :1984.
- **Automate stop/start around resonance tests** — a `gcode_shell_command` + macro hook that runs `systemctl stop/start go2rtc` around `TEST_RESONANCES`/Shake&Tune, so it's not a manual step.
- **udev rule for the focus lock** instead of the systemd `ExecStartPre` — persists the control for *any* consumer and decouples it from go2rtc's lifecycle.
- **Bump to 1080p30** now that we know H.264 supports it — try it and watch USB stability.
- **Track/auto-update the go2rtc binary** — pin a version and a refresh procedure, since it's hand-installed and outside Crowsnest's update path.
- **Second camera** (e.g. a toolhead cam) — add another `streams:` entry; go2rtc handles multiple with one service.
- **Improve enclosure lighting** — the cheapest fix for the auto-exposure framerate drop (§5.2); would let us keep exposure on auto *and* hold 30fps.
- **Explore go2rtc recording/motion** features for print-failure capture.

---

## 7. Task list

**Done**
- [x] Diagnose lag as two-layer (production vs transport); confirm "laggy but low CPU".
- [x] Confirm C920 exposes hardware H.264 at 720p30/1080p30 (§5.3).
- [x] Comment out `crowsnest.conf` `[cam 1]` so go2rtc can own the camera.
- [x] Add git-tracked `go2rtc.yaml` (720p30, H.264 `#video=copy`, `api.origin "*"`, webrtc candidates).
- [x] Install ffmpeg + go2rtc `arm64` binary.
- [x] Create `go2rtc.service` with the focus-lock `ExecStartPre`.
- [x] Deploy in order (`GIT_PULL` → restart crowsnest → enable go2rtc); confirm H.264 (not YUYV).
- [x] Add `WebRTC (go2rtc)` webcam in Mainsail (base URL + go2rtc snapshot URL); WebRTC plays in Chromium.
- [x] Leave exposure on auto (deliberate).

**Not done / ongoing**
- [ ] Tune `focus_absolute` in the `go2rtc.service` `ExecStartPre` for a sharp bed; verify 30fps under good lighting.
- [ ] Give the camera its own USB port; check `dmesg` for resets.
- [ ] `sudo systemctl stop go2rtc` before resonance tests (until automated — §6).
- [ ] Point moonraker-timelapse snapshot at go2rtc (if/when timelapse is used).
- [ ] Consider the §6 improvements (reverse-proxy, automation, 1080p, better lighting).
