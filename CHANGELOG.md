# Changelog

All notable modpack and container updates for **All the Mods 10** are recorded here.
New entries are added automatically by [`.github/workflows/update-pack.yml`](.github/workflows/update-pack.yml) from the CurseForge release changelog.

## Unreleased

- Add persistent `/data/custom_mods` (`*.jar` → `mods/`) and `/data/custom_config` (→ `config/`), restored on every boot. Jars removed or renamed in `custom_mods` are cleaned out of `mods/` via a manifest.
- Add optional `SERVER_PORT` (sets `server-port` and `query.port`; defaults to `25565`).
- `server.properties` settings are now created when missing and written without `sed`, so a MOTD containing `/`, `&` or `\` no longer breaks startup and settings apply on the very first boot.
- Whitelist/ops: an empty UUID lookup result (PlayerDB down, `jq` missing) is now treated as a failure instead of writing a bad entry.

## 8.4 — 2026-10-30

NeoForge `21.1.265` · [CurseForge file](https://www.curseforge.com/minecraft/modpacks/all-the-mods-10/files/9366926)

[Detailed changelog](https://github.com/AllTheMods/ATM-10/blob/main/CHANGELOG.md)

**Added:**

- Neovitae: Bloodborn (resourcepack)

**Others:**

- fix structure generation on AS and TF (Uncandango)
- Eliminate recipe conflicts (item4)
- Add a tag so cheese from the Moon can be used in cooking (item4)
- Add complete French (fr_fr) quest translation (aubault83)
- Fix arrow textures in Industrial Foregoing quests (peterphann)
- Update in-game announcements to reflect recent ATM10 changes (item4)
- Updated PT_BR Localizations + Neovitae quest rework (PrincessStellar)
- Fix missing silver processing recipes (item4)
- Update Turkish quest translations (KorayWalker)
- fix: clear obsolete dirt text from Teleposer quest translations (AmmarYasser455)

Neoforge Version is ***21.1.265***

**Known Issue**

- If Draconic Evolution items are invisible, enable the builtin resourcepack "Draconic 2D", or disable "hud_batching" on ImmediatlyFast config files
- If you crash when interacting with Ars Lectern, break it and place again to fix.

**ALWAYS REMEMBER TO BACKUP BEFORE UPDATING**

## 8.3 — 2026-10-25

NeoForge `21.1.259` · [CurseForge file](https://www.curseforge.com/minecraft/modpacks/all-the-mods-10/files/9190157)

[Detailed changelog](https://github.com/AllTheMods/ATM-10/blob/main/CHANGELOG.md)

**Ad Astra was added without any changes, we will add quests and do some changes later**

**Removed:**

- Rainbows

**Added:**

- Astral Sorcery
- ATM: Compat
- Refined Fluid Substitution
- Refined Wireless Upgrades

**Others:** TBD

Neoforge Version is ***21.1.259***

**Known Issue**

- If Draconic Evolution items are invisible, enable the builtin resourcepack "Draconic 2D", or disable "hud_batching" on ImmediatlyFast config files
- If you crash when interacting with Ars Lectern, break it and place again to fix.

**ALWAYS REMEMBER TO BACKUP BEFORE UPDATING**

### Container changes

- Require explicit `EULA=true` before the server will start (previously accepted by default when `EULA` was unset).
- Automate CurseForge version detection, in-CI server boot smoke test, Docker Hub publishing, git tagging, and changelog generation.
- Use atomic `.installed-<version>` marker and `exec` into the Java process for clean `docker stop` world saves.

## 8.2 — 2026-09-28

NeoForge `21.1.251` · [CurseForge](https://www.curseforge.com/minecraft/modpacks/all-the-mods-10)

- Baseline version prior to automated updates.
