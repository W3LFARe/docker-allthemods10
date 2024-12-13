#!/bin/bash

set -x

NEOFORGE_VERSION=21.1.89
SERVER_VERSION=2.3
cd /data

if ! [[ "$EULA" = "false" ]]; then
	echo "eula=true" > eula.txt
else
	echo "You must accept the EULA to install."
	exit 99
fi

if ! [[ -f "Server-Files-$SERVER_VERSION.zip" ]]; then
	rm -fr config defaultconfigs kubejs mods packmenu Simple.zip forge*
	curl -Lo "Server-Files-$SERVER_VERSION.zip" 'https://edge.forgecdn.net/files/5984/23/Server-Files-2.3.zip' || exit 9
	unzip -u -o "Server-Files-$SERVER_VERSION.zip" -d /data
	DIR_TEST=$(find . -type d -maxdepth 1 | tail -1 | sed 's/^.\{2\}//g')
	if [[ $(find . -type d -maxdepth 1 | wc -l) -gt 1 ]]; then
		cd "${DIR_TEST}"
		mv -f * /data
		cd /data
		rm -fr "$DIR_TEST"
	fi
	curl -Lo neoforge-${NEOFORGE_VERSION}-installer.jar http://files.neoforged.net/maven/net/neoforged/neoforge/$NEOFORGE_VERSION/neoforge-$NEOFORGE_VERSION-installer.jar
	java -jar neoforge-${NEOFORGE_VERSION}-installer.jar --installServer
fi

if [[ -n "$JVM_OPTS" ]]; then
	sed -i '/-Xm[s,x]/d' user_jvm_args.txt
	for j in ${JVM_OPTS}; do sed -i '$a\'$j'' user_jvm_args.txt; done
fi
if [[ -n "$MOTD" ]]; then
    sed -i "s/motd\s*=/ c motd=$MOTD" /data/server.properties
fi
if [[ -n "$ENABLE_WHITELIST" ]]; then
    sed -i "s/white-list=.*/white-list=$ENABLE_WHITELIST/" /data/server.properties
fi
[[ ! -f whitelist.json ]] && echo "[]" > whitelist.json
IFS=',' read -ra USERS <<< "$WHITELIST_USERS"
for raw_username in "${USERS[@]}"; do
	username=$(echo "$raw_username" | xargs)
	if [[ ! "$username" =~ ^[a-zA-Z0-9_]{3,16}$ ]]; then
		echo "Whitelist: Invalid username: '$username'. Skipping..."
		continue
	fi

	UUID=$(curl -s "https://api.mojang.com/users/profiles/minecraft/$username" | jq -r '.id')
	if [[ "$UUID" != "null" ]]; then
		if jq -e ".[] | select(.uuid == \"$UUID\")" whitelist.json > /dev/null; then
			echo "Whitelist: $username ($UUID) is already whitelisted."
		else
			echo "Whitelist: Adding $username ($UUID) to whitelist."
			jq ". += [{\"uuid\": \"$UUID\", \"name\": \"$username\"}]" whitelist.json > tmp.json && mv tmp.json whitelist.json
		fi
	else
		echo "Whitelist: Failed to fetch UUID for $username."
	fi
done
[[ ! -f ops.json ]] && echo "[]" > ops.json
IFS=',' read -ra OPS <<< "$OP_USERS"
for raw_username in "${OPS[@]}"; do
    username=$(echo "$raw_username" | xargs)
    if [[ ! "$username" =~ ^[a-zA-Z0-9_]{3,16}$ ]]; then
        echo "Ops: Invalid username: '$username'. Skipping..."
        continue
    fi

    UUID=$(curl -s "https://api.mojang.com/users/profiles/minecraft/$username" | jq -r '.id')
    if [[ "$UUID" != "null" ]]; then
        if jq -e ".[] | select(.uuid == \"$UUID\")" ops.json > /dev/null; then
            echo "Ops: $username ($UUID) is already an operator."
        else
            echo "Ops: Adding $username ($UUID) as operator."
            jq ". += [{\"uuid\": \"$UUID\", \"name\": \"$username\", \"level\": 4}]" ops.json > tmp.json && mv tmp.json ops.json
        fi
    else
        echo "Ops: Failed to fetch UUID for $username."
    fi
done

sed -i 's/server-port.*/server-port=25565/g' server.properties
chmod 755 run.sh

./run.sh
