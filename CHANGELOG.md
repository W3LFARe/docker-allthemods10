# Changelog

All notable modpack and container updates for **All the Mods 10** are recorded here.
New entries are added automatically by [`.github/workflows/update-pack.yml`](.github/workflows/update-pack.yml) from the CurseForge release changelog.

## Unreleased

- Require explicit `EULA=true` before the server will start (previously accepted by default when `EULA` was unset).
- Automate CurseForge version detection, in-CI server boot smoke test, Docker Hub publishing, git tagging, and changelog generation.
- Use atomic `.installed-<version>` marker and `exec` into the Java process for clean `docker stop` world saves.

## 8.2 — 2026-09-28

NeoForge `21.1.251` · [CurseForge](https://www.curseforge.com/minecraft/modpacks/all-the-mods-10)

- Baseline version prior to automated updates.
