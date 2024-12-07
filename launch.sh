#!/bin/bash

set -x

NEOFORGE_VERSION=21.1.83
cd /data

if ! [[ "$EULA" = "false" ]]; then
	echo "eula=true" > eula.txt
else
	echo "You must accept the EULA to install."
	exit 99
fi

if ! [[ -f 'Server-Files-2.0.zip' ]]; then
	rm -fr config defaultconfigs kubejs mods packmenu Simple.zip forge*
	curl -Lo 'Server-Files-2.0.zip' 'https://edge.forgecdn.net/files/5969/798/Server-Files-2.0.zip' || exit 9
	unzip -u -o 'Server-Files-2.0.zip' -d /data
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
if [[ -n "$OPS" ]]; then
    echo $OPS | awk -v RS=, '{print}' > ops.txt
fi
if [[ -n "$ALLOWLIST" ]]; then
    echo $ALLOWLIST | awk -v RS=, '{print}' > white-list.txt
fi

sed -i 's/server-port.*/server-port=25565/g' server.properties
chmod 755 run.sh

./run.sh
