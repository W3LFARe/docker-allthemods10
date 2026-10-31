#!/bin/bash

# Pack name, versions and download URL. Kept up to date automatically by
# .github/workflows/update-pack.yml — see pack.env in the repository.
# shellcheck source=pack.env
source "${PACK_ENV:-/pack.env}"

log() { echo "[pack] $*"; }

cd /data || { log "ERROR: /data is not available"; exit 1; }

# The Minecraft EULA must be accepted by the person running the server.
# It is never accepted on anyone's behalf: EULA=true has to be set explicitly.
if [[ "${EULA,,}" != "true" ]]; then
    log "You must accept the Minecraft EULA to run this server: https://aka.ms/MinecraftEULA"
    log "Read it, then set the environment variable EULA=true in your container template."
    exit 99
fi
echo "eula=true" > eula.txt

MARKER=".installed-${SERVER_VERSION}"

# Containers installed before automated updates used the downloaded zip as the
# "installed" marker. Adopt it so existing servers don't reinstall needlessly.
for legacy in "server-${SERVER_VERSION}.zip" "Server-Files-${SERVER_VERSION}.zip"; do
    if [[ -f "$legacy" && ! -f "$MARKER" ]]; then
        log "Found legacy install marker $legacy; adopting it."
        touch "$MARKER" && rm -f "$legacy"
    fi
done

if [[ ! -f "$MARKER" ]]; then
    log "Installing ${PACK_NAME} ${SERVER_VERSION} (NeoForge ${NEOFORGE_VERSION})"
    staging=/data/.install-tmp
    rm -rf "$staging" && mkdir -p "$staging"

    if ! curl -fsSL --retry 3 --retry-delay 5 -o "$staging/server.zip" "$SERVER_URL"; then
        log "ERROR: failed to download $SERVER_URL"
        rm -rf "$staging"
        exit 9
    fi
    if ! unzip -q "$staging/server.zip" -d "$staging/files"; then
        log "ERROR: downloaded server pack is not a valid zip"
        rm -rf "$staging"
        exit 9
    fi

    # Server packs are usually flat, but some wrap everything in one folder.
    src="$staging/files"
    shopt -s nullglob dotglob
    top=("$src"/*)
    shopt -u nullglob dotglob
    if [[ ${#top[@]} -eq 1 && -d "${top[0]}" ]]; then
        src="${top[0]}"
    fi

    # Replace pack-owned folders; worlds, server.properties, whitelist etc. are kept.
    rm -rf config defaultconfigs kubejs mods packmenu .installed-* \
           server-*.zip Server-Files-*.zip neoforge-*-installer.jar*
    cp -a "$src"/. /data/
    rm -rf "$staging"

    installer="neoforge-${NEOFORGE_VERSION}-installer.jar"
    if ! curl -fsSL --retry 3 --retry-delay 5 -o "$installer" \
        "https://maven.neoforged.net/releases/net/neoforged/neoforge/${NEOFORGE_VERSION}/${installer}"; then
        log "ERROR: failed to download NeoForge ${NEOFORGE_VERSION}"
        exit 9
    fi
    if ! java -jar "$installer" --installServer; then
        log "ERROR: NeoForge installer failed"
        exit 9
    fi
    rm -f "$installer" "$installer.log"

    touch "$MARKER"   # only after everything above succeeded
    log "Install of ${SERVER_VERSION} complete."
fi

if [[ -n "$JVM_OPTS" ]]; then
    sed -i '/^-Xm[sx]/d; /^# --- launch\.sh JVM_OPTS ---$/,$d' user_jvm_args.txt
    printf '\n# --- launch.sh JVM_OPTS ---\n' >> user_jvm_args.txt
    for j in ${JVM_OPTS}; do
        printf '%s\n' "${j/#--Xm/-Xm}" >> user_jvm_args.txt
    done
fi
# Set KEY=VALUE in server.properties. Creates the file / the key when missing
# (first boot of a pack without server.properties) and passes the value through
# the environment so characters like / & \ in a MOTD can't break the edit.
set_prop() {
    local key="$1" value="$2" file="server.properties"
    [[ -f "$file" ]] || : > "$file"
    KEY="$key" VALUE="$value" awk '
        BEGIN { k = ENVIRON["KEY"]; v = ENVIRON["VALUE"]; done = 0 }
        index($0, k "=") == 1 { if (!done) print k "=" v; done = 1; next }
        { print }
        END { if (!done) print k "=" v }
    ' "$file" > "$file.tmp" && mv "$file.tmp" "$file"
}

if [[ -n "$MOTD" ]]; then
    set_prop motd "$MOTD"
fi
if [[ -n "$ENABLE_WHITELIST" ]]; then
    set_prop white-list "$ENABLE_WHITELIST"
fi
if [[ -n "$ALLOW_FLIGHT" ]]; then
    set_prop allow-flight "$ALLOW_FLIGHT"
fi
if [[ -n "$MAX_PLAYERS" ]]; then
    set_prop max-players "$MAX_PLAYERS"
fi
if [[ -n "$ONLINE_MODE" ]]; then
    set_prop online-mode "$ONLINE_MODE"
fi

# Initialize whitelist.json if not present
if [[ ! -f whitelist.json ]]; then
    echo "[]" > whitelist.json
fi

IFS=',' read -ra USERS <<< "$WHITELIST_USERS"
for raw_username in "${USERS[@]}"; do
    username=$(echo "$raw_username" | xargs)

    if [[ -z "$username" ]] || ! [[ "$username" =~ ^[a-zA-Z0-9_]{3,16}$ ]]; then
        echo "Whitelist: Invalid or empty username: '$username'. Skipping..."
        continue
    fi

    UUID=$(curl -s "https://playerdb.co/api/player/minecraft/$username" | jq -r '.data.player.id')
    if [[ -n "$UUID" && "$UUID" != "null" ]]; then
        if jq -e ".[] | select(.uuid == \"$UUID\" and .name == \"$username\")" whitelist.json > /dev/null; then
            echo "Whitelist: $username ($UUID) is already whitelisted. Skipping..."
        else
            echo "Whitelist: Adding $username ($UUID) to whitelist."
            jq ". += [{\"uuid\": \"$UUID\", \"name\": \"$username\"}]" whitelist.json > tmp.json && mv tmp.json whitelist.json
        fi
    else
        echo "Whitelist: Failed to fetch UUID for $username."
    fi
done

# Initialize ops.json if not present
if [[ ! -f ops.json ]]; then
    echo "[]" > ops.json
fi

IFS=',' read -ra OPS <<< "$OP_USERS"
for raw_username in "${OPS[@]}"; do
    username=$(echo "$raw_username" | xargs)

    if [[ -z "$username" ]] || ! [[ "$username" =~ ^[a-zA-Z0-9_]{3,16}$ ]]; then
        echo "Ops: Invalid or empty username: '$username'. Skipping..."
        continue
    fi

    UUID=$(curl -s "https://playerdb.co/api/player/minecraft/$username" | jq -r '.data.player.id')
    if [[ -n "$UUID" && "$UUID" != "null" ]]; then
        if jq -e ".[] | select(.uuid == \"$UUID\" and .name == \"$username\")" ops.json > /dev/null; then
            echo "Ops: $username ($UUID) is already an operator. Skipping..."
        else
            echo "Ops: Adding $username ($UUID) as operator."
            jq ". += [{\"uuid\": \"$UUID\", \"name\": \"$username\", \"level\": 4, \"bypassesPlayerLimit\": false}]" ops.json > tmp.json && mv tmp.json ops.json
        fi
    else
        echo "Ops: Failed to fetch UUID for $username."
    fi
done

# Port: SERVER_PORT is set by Pelican/Pterodactyl; Docker/Unraid keep 25565.
set_prop server-port "${SERVER_PORT:-25565}"
if [[ -n "${SERVER_PORT:-}" ]]; then
    set_prop query.port "${SERVER_PORT}"
fi

# Persistent custom mods: copy /data/custom_mods/*.jar into /data/mods on every
# boot. The names copied last time are remembered in a manifest so a removed or
# renamed jar in custom_mods doesn't linger in mods/ (duplicate-mod crashes).
mkdir -p /data/custom_mods /data/mods
CUSTOM_MODS_MANIFEST="/data/.custom_mods.manifest"
if [[ -f "$CUSTOM_MODS_MANIFEST" ]]; then
    while IFS= read -r old_jar; do
        [[ -n "$old_jar" ]] && rm -f "/data/mods/$old_jar"
    done < "$CUSTOM_MODS_MANIFEST"
    rm -f "$CUSTOM_MODS_MANIFEST"
fi
shopt -s nullglob
custom_jars=(/data/custom_mods/*.jar)
shopt -u nullglob
if (( ${#custom_jars[@]} > 0 )); then
    log "Copying ${#custom_jars[@]} persistent custom mod(s) from /data/custom_mods to /data/mods..."
    for jar in "${custom_jars[@]}"; do
        name="${jar##*/}"
        # Only track jars that don't replace a pack-owned file of the same name,
        # otherwise removing the custom jar later would delete the pack's mod.
        [[ -e "/data/mods/$name" ]] || echo "$name" >> "$CUSTOM_MODS_MANIFEST"
        cp -vf "$jar" "/data/mods/$name"
    done
fi

# Persistent custom configs: copy /data/custom_config/* into /data/config on every boot.
mkdir -p /data/custom_config
if [[ -n "$(ls -A /data/custom_config 2>/dev/null)" ]]; then
    log "Copying persistent custom configs from /data/custom_config to /data/config..."
    mkdir -p /data/config
    cp -rvf /data/custom_config/. /data/config/
fi

# Start the server as PID 1 (exec) so `docker stop` delivers SIGTERM straight to
# Java, which then saves the world and shuts down cleanly. This is the same
# command NeoForge's run.sh uses.
log "Starting ${PACK_NAME} ${SERVER_VERSION}"
exec java @user_jvm_args.txt "@libraries/net/neoforged/neoforge/${NEOFORGE_VERSION}/unix_args.txt" nogui
