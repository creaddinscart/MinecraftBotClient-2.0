# Changelog

All notable changes to MinecraftBotClient (MBC) are documented here.
Versions edited in CREADDINSCART STUDIO carry the four conditions of use.

## [2.0.0] — MBC-2.0

Built on the MBC 1.0 protocol core. Jointly developed and published by
CREADDINSCART STUDIO, Mater Work, Loder Hankex, jake, jenmnmer and yig.

### Added — Collaborative Multi-Operator Terminal (headline feature)
- **Shared swarm console** (`src/features/operator_hub.py`): a TCP hub that lets several
  operators join ONE running swarm console from separate terminals and co-manage the bots.
- **Operator joiner client** (`src/ui/collab_client.py`): `python -m src.ui.collab_client
  --host <IP> --port <port> --name <name> [--token <secret>]`.
- **Live swarm scaling**: `add <n>` and `kick <index|name|all>` while the swarm is running
  (no restart); per-bot `list`, targeted `msg <selector> <text>`, presence `who`, `nick`.
- **Mirrored event feed**: every bot join/leave, broadcast and operator presence event is
  shown to all operators and mirrored to the host terminal.
- **Optional token auth** (`collab_token`) and bind control (`collab_bind`, `collab_port`).
- Host-console equivalents: `.collab <status|users|list|say|add|kick>`, plus `.list`,
  `.add`, `.kick` on the swarm prompt.
- New config keys: `collab_enabled`, `collab_bind`, `collab_port`, `collab_token`.
- Independent avatars for all five authors under `assets/avatars/`.

### Changed
- `src/features/bot_swarm.py` refactored to support live add/kick/list/targeting and
  per-bot liveness while keeping the 1.0 connection + auto-auth behaviour.
- Client `run_swarm()` integrates the hub and routes all swarm events through it.
- Version bumped to `2.0.0`; banner updated.

### Carried over from 1.x
- All-version protocol auto-detect (1.8 → 26.2), SRV resolution, bilingual UI, vanilla
  autocomplete, human-like actions, auto-walk / auto-eat / proximity alerts / auto-spam /
  session logging / fast & offline start, cross-platform builds.

## [1.x]
- Pure-protocol single/multi-bot Minecraft client by CREADDINSCART STUDIO.
- Upstream: https://github.com/creaddinscart/MinecraftBotClient
