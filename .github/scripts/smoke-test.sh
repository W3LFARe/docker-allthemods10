#!/usr/bin/env bash
# Smoke test for a locally built image.
#
#   smoke-test.sh IMAGE [force-fail]
#
# 1. EULA check: without EULA=true the container must refuse to start (exit 99).
# 2. Boot test:  with EULA=true the pack must install and reach "Done (" within
#                SMOKE_TIMEOUT seconds (default 1800).
# 3. Shutdown:   `docker stop` must stop the server cleanly (world saved).
#
# Logs are written to smoke.log. Exit code 0 = pass.
set -uo pipefail

IMAGE=${1:?usage: smoke-test.sh IMAGE [force-fail]}
FORCE_FAIL=${2:-}
TIMEOUT=${SMOKE_TIMEOUT:-1800}
JVM_OPTS=${SMOKE_JVM_OPTS:--Xms4G -Xmx10G}
LOG=smoke.log
NAME=smoke-$$

cleanup() { docker rm -f "$NAME" "$NAME-eula" >/dev/null 2>&1 || true; }
trap cleanup EXIT

fail() { echo "::error title=Smoke test failed::$*"; docker logs "$NAME" > "$LOG" 2>&1 || true; exit 1; }

echo "::group::EULA check (container must refuse to start without EULA=true)"
code=$(timeout 120 docker run --name "$NAME-eula" "$IMAGE" >/dev/null 2>&1; docker inspect -f '{{.State.ExitCode}}' "$NAME-eula")
docker logs "$NAME-eula" 2>&1 | tail -n 5
if [[ "$code" != "99" ]]; then
    echo "::error title=EULA check failed::container without EULA=true exited with '$code' (expected 99)"
    exit 1
fi
echo "OK: refused to start without EULA (exit 99)"
echo "::endgroup::"

if [[ "$FORCE_FAIL" == "force-fail" ]]; then
    echo "::warning::[smoke-fail] requested: starting with a 1 MB heap so the server cannot boot"
    JVM_OPTS="-Xms1M -Xmx1M"
fi

echo "::group::Boot test (timeout ${TIMEOUT}s, JVM_OPTS=$JVM_OPTS)"
docker run -d --name "$NAME" -e EULA=true -e JVM_OPTS="$JVM_OPTS" "$IMAGE" >/dev/null || fail "docker run failed"
start=$SECONDS
while true; do
    docker logs "$NAME" > "$LOG" 2>&1 || true
    if grep -aqE 'Done \([0-9]' "$LOG"; then
        echo "Server is up after $((SECONDS - start))s"
        break
    fi
    if [[ "$(docker inspect -f '{{.State.Running}}' "$NAME")" != "true" ]]; then
        tail -n 40 "$LOG"
        fail "container exited with code $(docker inspect -f '{{.State.ExitCode}}' "$NAME") before the server finished starting"
    fi
    if (( SECONDS - start > TIMEOUT )); then
        tail -n 40 "$LOG"
        fail "server did not reach 'Done (' within ${TIMEOUT}s"
    fi
    sleep 15
    echo "  ...waiting ($((SECONDS - start))s) $(tail -n 1 "$LOG" | cut -c1-150)"
done
grep -aE '\[pack\]|Done \(' "$LOG" || true
echo "::endgroup::"

echo "::group::Graceful shutdown (docker stop)"
docker stop -t 120 "$NAME" >/dev/null
docker logs "$NAME" > "$LOG" 2>&1 || true
if grep -aqiE 'Stopping (the )?server|Saving worlds|All dimensions are saved' "$LOG"; then
    echo "OK: server shut down cleanly"
else
    echo "::warning title=Shutdown::no save/stop messages seen after docker stop; check smoke.log"
fi
tail -n 10 "$LOG"
echo "::endgroup::"

echo "Smoke test passed."
