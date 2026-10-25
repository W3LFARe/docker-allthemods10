# Changelog

All notable modpack and container updates for **All the Mods 10** are recorded here.
New entries are added automatically by [`.github/workflows/update-pack.yml`](.github/workflows/update-pack.yml) from the CurseForge release changelog.

## Unreleased

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
