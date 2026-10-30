# [All the Mods 10-8.4](https://www.curseforge.com/minecraft/modpacks/all-the-mods-10) on Curseforge
<!-- toc -->

- [Description](#description)
- [Requirements](#requirements)
- [Options](#options)
- [Automatic Updates & Rollback](#automatic-updates--rollback)
- [Troubleshooting](#troubleshooting)
  * [Accept the EULA](#accept-the-eula)
  * [Permissions of Files](#permissions-of-files)
  * [Resetting](#resetting)
- [Source](#source-original-atm9-repo)

<!-- tocstop -->

## Description

This container is built to run on an [Unraid](https://unraid.net) server, outside of that your mileage will vary.

On the first run the container downloads `All the Mods 10-8.4` and installs it. This can take a while as the NeoForge installer takes some time to complete. Watch the logs and it will eventually finish.

After the first run, it will simply start the server. When a newer image is pulled, the container automatically upgrades the modpack files while preserving your world, `server.properties`, `whitelist.json`, and `ops.json`.

Note: There are no modded Minecraft files shipped in the container; they are all downloaded at runtime.

## Requirements

* `/data` mounted to a persistent disk
* Port `25565/tcp` mapped
* **Environment variable `EULA` explicitly set to `"true"`**

> **Important:** As the end user, you are responsible for accepting the [Minecraft EULA](https://aka.ms/MinecraftEULA) from Mojang to run their server. By default in the container it is not accepted — the container will exit with code `99` unless you pass `-e EULA=true`.

### Recommended Server RAM (`JVM_OPTS`)

* **Minimum (1–2 players):** 8–10 GB (`-Xms8192m -Xmx10240m`)
* **Recommended (2–5 players):** 10–12 GB (`-Xms8192m -Xmx12288m`)
* **Heavy / 5+ players:** 14–16 GB (`-Xms12288m -Xmx16384m`)

## Options

These environment variables can be set to override their defaults:

* `EULA` `"true"` (**required** — server will not start without this)
* `JVM_OPTS` `"-Xms8192m -Xmx12288m"` (allocate at least 8–10 GB for 1–2 players, 10–12 GB for 2–5 players, or 14–16 GB for 5+ players)
* `MOTD` `"All the Mods 10 Server Powered by Docker"`
* `ALLOW_FLIGHT` `"true"` or `"false"`
* `MAX_PLAYERS` `"5"`
* `ONLINE_MODE` `"true"` or `"false"`
* `ENABLE_WHITELIST` `"true"` or `"false"`
* `WHITELIST_USERS` `"TestUserName1, TestUserName2"`
* `OP_USERS` `"TestUserName1, TestUserName2"`
* `SERVER_PORT` `"25565"` (optional — overrides `server-port` and `query.port` in `server.properties`)

## Persistent Custom Mods & Configs

When a new modpack release is installed, the `/data/mods` and `/data/config` directories are replaced with the clean upstream modpack files. To persist extra server-side mods (such as Discord Integration) or custom configuration overrides across automatic modpack updates:

* **`/data/custom_mods/`**: Any `.jar` files placed in `/data/custom_mods/` are automatically copied into `/data/mods/` on every server boot.
* **`/data/custom_config/`**: Any files or folders placed in `/data/custom_config/` (for example, `Discord-Integration.toml`) are automatically copied into `/data/config/` on every server boot.

## Pelican & Pterodactyl Panel Eggs

Looking to run this server inside **Pelican Panel** or **Pterodactyl Panel** with automatic updates? Grab the official auto-updating Egg from [`W3LFARe/pelican-eggs`](https://github.com/W3LFARe/pelican-eggs).

## Automatic Updates & Rollback

This repository checks CurseForge every 6 hours (via [`.github/workflows/update-pack.yml`](.github/workflows/update-pack.yml)) for a new server pack of the modpack configured in [`pack.env`](pack.env):

1. When a new release is found, [`cf_update.py`](.github/scripts/cf_update.py) resolves the server pack download URL, extracts `NEOFORGE_VERSION` from `startserver.sh`, and updates [`pack.env`](pack.env), `README.md`, and [`CHANGELOG.md`](CHANGELOG.md).
2. CI builds the image and runs a full boot smoke test ([`.github/scripts/smoke-test.sh`](.github/scripts/smoke-test.sh)) until the server logs `Done (...)`.
3. Only if the smoke test passes does CI push `:<version>` and `:latest` to Docker Hub, tag `v<version>`, and create a GitHub Release with the CurseForge changelog.
4. If the smoke test fails, `:latest` is untouched, the CurseForge file ID is added to `SKIP_FILE_IDS` in `pack.env`, and a GitHub Issue is opened with the server log.
5. To roll `:latest` back to a previous version at any time, run the **Rollback release** workflow in GitHub Actions with the target version.

## Troubleshooting

### Accept the EULA
Did you pass in the environment variable `EULA` set to `true`? The server refuses to start (exit code `99`) when `EULA` is unset or set to any value other than `true`.

### Permissions of Files
This container is designed for [Unraid](https://unraid.net) so the user in the container runs on uid 99 and gid 100. This may cause permission errors on the `/data` mount on other systems.

### Resetting
If an installation needs to be forced from scratch, delete `/data/.installed-<version>` and restart the container.

## Source (Original ATM9 repo)
Github: https://github.com/Goobaroo/docker-allthemods9

Docker: https://hub.docker.com/repository/docker/goobaroo/allthemods9

## Source (W3LFARe repo)
Github: https://github.com/W3LFARe/docker-allthemods10

Docker: https://registry.hub.docker.com/r/w3lfare/allthemods10
