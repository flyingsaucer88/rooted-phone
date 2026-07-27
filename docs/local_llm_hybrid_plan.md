# Local LLM Hybrid Plan — Moto G4 Plus + Mac

## Goal
Use the Moto G4 Plus as a local client/controller for a Mac-hosted LLM.

## Why Hybrid
- Android 7.0 (SDK 24)
- 32-bit `armeabi-v7a` — `ro.product.cpu.abilist64` is **empty** (no 64-bit ABI at all)
- ~2.95 GB RAM (device); app-usable free RAM ~200 MB at rest
- unrooted, bootloader locked, no NNAPI (API 24 < 27), no Vulkan (Adreno 405)
- Incompatible with modern Android LLM apps: their inference runtimes (LiteRT-LM /
  MediaPipe) ship **arm64-v8a only**, and even the lightest projects require **≥4 GB RAM**.
  See Phase 9 in `rooted_android_phone_playbook.md` for the full feasibility evidence.

## Architecture
```
Moto (browser or Termux curl)
   → USB reverse tunnel (adb reverse) [preferred]  OR  LAN (same non-guest subnet)
      → Mac local LLM HTTP server (127.0.0.1)
         → local model on Mac
            → response streamed back to Moto
```
No cloud. No model downloaded to the phone. The phone is a pure I/O terminal.

## Candidate Mac Servers
| Server | Installed? | Pros | Cons | Next Action |
|---|---:|---|---|---|
| Ollama | ❌ No | Simplest; one-command models; OpenAI-compatible `/v1` + `/api`; serves on 127.0.0.1:11434 | Needs install (brew or pkg); model pull is a large download | Propose `brew install ollama` (approval needed) |
| llama.cpp server | ❌ No | Lightweight; GGUF; full control; `llama-server` HTTP | Build/install + fetch a GGUF (large) | Propose `brew install llama.cpp` (approval) |
| LM Studio local server | ❌ No | GUI + OpenAI-compatible server toggle | GUI app install; heavier | Optional |
| Open WebUI | ❌ No | Nice web UI the phone browser can use directly | Python/docker; needs a backend (Ollama) | After a backend exists |
| Python/FastAPI wrapper | ⚠️ python3 3.14.5 present | No new server engine; thin proxy/mock | Still needs a real model backend to be useful | Usable now for a **mock** endpoint to prove the tunnel |

_Currently installed on Mac: `python3` (3.14.5), `node`; Homebrew `onnx` formula. **No LLM server engine.**_

## Connection Options
| Option | Method | Works with guest Wi-Fi? | Security | Notes |
|---|---|---:|---|---|
| USB reverse | `adb reverse tcp:PORT tcp:PORT` | Yes (USB, no Wi-Fi needed) | Local only | **Preferred first.** Phone's `127.0.0.1:PORT` → Mac's `127.0.0.1:PORT` |
| USB forward | `adb forward tcp:PORT tcp:PORT` | Yes | Local only | Opposite direction (Mac→phone); already used for SSH (8022) |
| LAN | same Wi-Fi subnet | ❌ No (guest isolation, and Mac/phone on different /24) | Local network | Later, on a non-guest network |
| Tailscale/VPN | VPN overlay | Possibly | Requires setup + accounts | Later; adds internet dependency |

### Tunnel direction (important)
- **`adb reverse tcp:8090 tcp:8090`** = a listener on the **phone** at `127.0.0.1:8090` that
  tunnels to the **Mac** at `127.0.0.1:8090`. This is the correct direction for **phone → Mac**.
- `adb forward` is the reverse (Mac → phone) and is what the SSH bridge already uses (8022).
- Current state: `adb forward` has `tcp:8022→8022`; `adb reverse` list is empty.

## Prototype 1 (documentation only — not yet run)
- Mac exposes a local HTTP endpoint on `127.0.0.1` (mock first, real model later).
- `adb reverse tcp:8090 tcp:8090`.
- On the Moto (Termux): `curl http://127.0.0.1:8090/...` → confirm round-trip.
- Then point it at a real server (`/api/generate` or `/v1/chat/completions`).
- Phone browser alternative: open `http://127.0.0.1:8090` (works once reverse tunnel is up).
- No cloud, no phone-side model.

## Risks
- Mac server accidentally binding to `0.0.0.0` (public) instead of `127.0.0.1` — keep it loopback-only.
- CORS if using the phone **browser** (Termux `curl` avoids this) — set permissive CORS only on loopback.
- Old phone browser (Chrome on Android 7) compatibility with streaming/SSE — Termux `curl` is the safe fallback.
- Model size/performance is now a **Mac** concern, not the phone's — pick a small model first.
- Accidental internet dependency — verify everything works with Wi-Fi off (USB only).
- Leftover test servers — always record PID and stop them.

## Next Commands Proposed (require explicit approval; none run yet)
```bash
# 1) Install a Mac server engine (choose one) — APPROVAL NEEDED (install):
brew install ollama            # simplest
#   or
brew install llama.cpp         # lightweight GGUF

# 2) Fetch ONE small model — APPROVAL NEEDED (large download):
ollama pull qwen2.5:0.5b       # ~400 MB   (or llama3.2:1b ~1.3 GB)

# 3) Serve loopback-only + open the USB reverse tunnel (safe, local):
#   (Ollama serves 127.0.0.1:11434 by default)
adb reverse tcp:11434 tcp:11434

# 4) From the phone (Termux), test tunnel with a NON-LLM check first:
#   scripts/moto-ssh.sh 'curl -s http://127.0.0.1:11434/api/tags'
#   then a tiny generate call.
```
_Zero-download alternative to prove the tunnel today: a Python mock endpoint on the Mac
(`127.0.0.1:8090`) + `adb reverse` + Termux `curl` — no model, no install. Ask to run it._
