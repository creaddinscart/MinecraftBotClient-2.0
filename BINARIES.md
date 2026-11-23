# MBC-2.0 — Standalone binaries (no Python, no source needed)

PyInstaller **cannot cross-compile**: a binary can only be produced on the OS it
runs on. So here is the honest split.

## Prebuilt in this folder (built and run-tested on macOS arm64)

```
releases/2.0.0/macos/
├── en/     MinecraftBotClient-en   (Mach-O arm64, ~9.7 MB) + config.en.json + README.en.md
├── zh/     MinecraftBotClient-zh   (Mach-O arm64) + config.zh.json + README.zh.md
├── collab/ mbc-collab              (Mach-O arm64 joiner — operators run this, no Python)
├── en.zip  zh.zip
```

Run the client (Apple Silicon Mac):
```bash
cd releases/2.0.0/macos/en
chmod +x MinecraftBotClient-en
xattr -d com.apple.quarantine MinecraftBotClient-en   # if Gatekeeper blocks it
./MinecraftBotClient-en
```

Join a running shared console from a second machine/terminal (no Python needed):
```bash
cd releases/2.0.0/macos/collab
chmod +x mbc-collab
./mbc-collab --host <HOST_IP> --port 25599 --name Alice --token <secret>
```

Verified here: the frozen host binary opened the collab console on a port, and the
frozen `mbc-collab` binary joined and live-scaled the swarm (`add 6` -> 9 bots,
`kick all`, broadcast) — all mirrored back to the host. **No source, no Python.**

## Linux and Windows binaries

I cannot fabricate working Linux/Windows binaries on this Mac, and I will not ship
you fake files. Two real ways to get them:

**A. GitHub Actions (recommended — one push, all platforms).**
This repo already contains `.github/workflows/build.yml`. Push these files to a
GitHub repository and the workflow builds `windows`, `linux`, `macos-arm64` and
`macos-intel` on native runners and uploads them as downloadable artifacts
(named `MBC-2.0.0-<platform>`). Each artifact contains the client + `mbc-collab`
joiner + config + README, exactly like the macOS folder above.

**B. Build locally on each OS** (needs Python 3.8+ once, only on the build machine):
```bash
pip install -r requirements.txt
python build.py
# -> releases/2.0.0/windows/  (MinecraftBotClient-en.exe, mbc-collab.exe, ...)
# -> releases/2.0.0/linux/    (MinecraftBotClient-en, mbc-collab, ...)
```

## Which binary runs where
| Platform | File | Notes |
|---|---|---|
| macOS Apple Silicon | `MinecraftBotClient-en` / `-zh` | prebuilt here |
| macOS Intel | build via CI (`macos-intel`) | PyInstaller target = the build machine's CPU |
| Windows | `MinecraftBotClient-en.exe` | via CI or local `build.py` on Windows |
| Linux | `MinecraftBotClient-en` | via CI or local `build.py` on Linux |

Made with [CREADDINSCART STUDIO](https://www.shit.pub/studio/).
