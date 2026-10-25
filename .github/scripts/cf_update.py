#!/usr/bin/env python3
"""CurseForge modpack updater for the docker-allthemods10* images.

Reads pack identity + current version from ``pack.env``, asks the CurseForge
API for the newest server pack of ``CF_PROJECT_ID`` and, if it is new, rewrites
``pack.env``, the README version markers and ``CHANGELOG.md``.

Standard library only so it runs on a bare GitHub runner.

Commands
--------
  check [--dry-run] [--ignore-skip]   look for an update (writes files unless --dry-run)
  skip FILE_ID                        add a CurseForge file id to SKIP_FILE_IDS
  restore OLD_PACK_ENV                copy managed version keys from another pack.env (rollback)
  notes VERSION                       print the CHANGELOG.md section for VERSION
  neoforge URL                        print NEOFORGE_VERSION found inside a remote server zip

Environment: CURSEFORGE_API_KEY (required for ``check``), GITHUB_OUTPUT and
GITHUB_STEP_SUMMARY (optional, set automatically on GitHub Actions).
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path

API = "https://api.curseforge.com/v1"
CDN = "https://mediafilez.forgecdn.net/files"
MAVEN = "https://maven.neoforged.net/releases/net/neoforged/neoforge"
UA = "docker-allthemods10-updater (+https://github.com/W3LFARe)"

ROOT = Path(os.environ.get("REPO_ROOT", Path(__file__).resolve().parents[2]))
PACK_ENV = ROOT / "pack.env"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"

# Keys the bot owns. Everything else in pack.env is left untouched.
MANAGED = ["SERVER_VERSION", "NEOFORGE_VERSION", "SERVER_FILE_ID", "SERVER_FILE_NAME", "SERVER_URL"]
MARKER_RE = re.compile(r"(<!-- pack-version -->).*?(<!-- /pack-version -->)", re.S)
VERSION_RE = re.compile(r"\d+(?:\.\d+)+")


class UpdateError(Exception):
    """Fatal problem: nothing is written and the workflow run goes red."""


# --------------------------------------------------------------------------- pack.env
def read_env(path: Path = PACK_ENV) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=(.*)$", line)
        if m:
            val = m.group(2).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            env[m.group(1)] = val
    return env


def write_env(updates: dict[str, str], path: Path = PACK_ENV) -> None:
    """Replace KEY=... lines in place (keeps comments/order); append unknown keys."""
    lines = path.read_text().splitlines()
    seen = set()
    for i, line in enumerate(lines):
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=", line)
        if m and m.group(1) in updates:
            lines[i] = f'{m.group(1)}="{updates[m.group(1)]}"'
            seen.add(m.group(1))
    lines += [f'{k}="{v}"' for k, v in updates.items() if k not in seen]
    path.write_text("\n".join(lines) + "\n")


def skip_ids(env: dict[str, str]) -> set[int]:
    return {int(x) for x in re.findall(r"\d+", env.get("SKIP_FILE_IDS", ""))}


# --------------------------------------------------------------------------- HTTP
def http(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    data: bytes | None = None,
    retries: int = 3,
) -> urllib.request.addinfourl:
    hdrs = {"User-Agent": UA, **(headers or {})}
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
            return urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                raise
            err = e
        except (urllib.error.URLError, TimeoutError) as e:
            err = e
        time.sleep(2 * attempt)
    raise UpdateError(f"{method} {url} failed after {retries} attempts: {err}")


def api(path: str, *, body: dict | None = None) -> dict:
    key = os.environ.get("CURSEFORGE_API_KEY", "").strip()
    if not key:
        raise UpdateError("CURSEFORGE_API_KEY is not set")
    headers = {"x-api-key": key, "Accept": "application/json"}
    payload = None
    method = "GET"
    if body is not None:
        method = "POST"
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode("utf-8")
    try:
        with http(API + path, method=method, headers=headers, data=payload) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise UpdateError(f"CurseForge API {method} {path} -> HTTP {e.code}") from e


def url_ok(url: str) -> bool:
    try:
        with http(url, method="HEAD") as r:
            return r.status == 200
    except urllib.error.HTTPError:
        return False


# --------------------------------------------------------------------------- remote zip
class HttpRangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP Range requests (lets zipfile read the
    central directory + one member without downloading a 1 GB archive)."""

    def __init__(self, url: str):
        self.url, self.pos = url, 0
        with http(url, method="HEAD") as r:
            self.url = r.url  # follow redirects once
            self.size = int(r.headers["Content-Length"])

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=io.SEEK_SET):
        self.pos = {io.SEEK_SET: off, io.SEEK_CUR: self.pos + off, io.SEEK_END: self.size + off}[whence]
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size or not len(b):
            return 0
        end = min(self.pos + len(b), self.size) - 1
        with http(self.url, headers={"Range": f"bytes={self.pos}-{end}"}) as r:
            data = r.read()
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)


def neoforge_version(url: str) -> str:
    with zipfile.ZipFile(io.BufferedReader(HttpRangeFile(url), 1 << 16)) as z:
        # flat zip ("startserver.sh") or single top-level folder ("x/startserver.sh")
        members = [n for n in z.namelist() if re.fullmatch(r"(?:[^/]+/)?startserver\.sh", n)]
        if not members:
            raise UpdateError(f"startserver.sh not found in {url}")
        text = z.read(min(members, key=len)).decode("utf-8", "replace")
    m = re.search(r"^\s*NEOFORGE_VERSION=[\"']?([0-9][\w.\-]*)", text, re.M)
    if not m:
        raise UpdateError("NEOFORGE_VERSION not found in startserver.sh")
    return m.group(1)


# --------------------------------------------------------------------------- pure helpers
def cdn_url(file_id: int, file_name: str) -> str:
    """9262010 -> .../files/9262/10/<name>  (second part is NOT zero-padded)."""
    return f"{CDN}/{file_id // 1000}/{file_id % 1000}/{urllib.parse.quote(file_name)}"


def parse_version(*candidates: str) -> str:
    for s in candidates:
        if s and (m := VERSION_RE.search(s)):
            return m.group(0)
    raise UpdateError(f"could not parse a version number from {candidates!r}")


class _HtmlToMd(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.lists: list[str] = []  # stack of "ul"/"ol"
        self.counters: list[int] = []
        self.href: str | None = None

    def _nl(self, n=1):
        text = "".join(self.out)
        have = len(text) - len(text.rstrip("\n"))
        if text and have < n:
            self.out.append("\n" * (n - have))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("p", "div"):
            self._nl(2)
        elif tag == "br":
            self.out.append("\n")
        elif re.fullmatch(r"h[1-6]", tag):
            self._nl(2)
            self.out.append("#" * min(int(tag[1]) + 2, 6) + " ")
        elif tag in ("ul", "ol"):
            self._nl(1 if self.lists else 2)
            self.lists.append(tag)
            self.counters.append(0)
        elif tag == "li":
            self._nl(1)
            indent = "  " * (len(self.lists) - 1)
            if self.lists and self.lists[-1] == "ol":
                self.counters[-1] += 1
                self.out.append(f"{indent}{self.counters[-1]}. ")
            else:
                self.out.append(f"{indent}- ")
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag == "code":
            self.out.append("`")
        elif tag == "a":
            self.href = a.get("href")
            self.out.append("[")

    def handle_endtag(self, tag):
        if tag in ("p", "div") or re.fullmatch(r"h[1-6]", tag):
            self._nl(2)
        elif tag in ("ul", "ol") and self.lists:
            self.lists.pop()
            self.counters.pop()
            self._nl(1 if self.lists else 2)
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag == "code":
            self.out.append("`")
        elif tag == "a":
            self.out.append(f"]({self.href})" if self.href else "]")
            self.href = None

    def handle_data(self, data):
        data = re.sub(r"\s+", " ", data)
        if data.strip() or (self.out and not self.out[-1].endswith((" ", "\n"))):
            if not self.out or self.out[-1].endswith("\n"):
                data = data.lstrip()
            self.out.append(data)


def html_to_markdown(src: str) -> str:
    p = _HtmlToMd()
    p.feed(src or "")
    p.close()
    text = "".join(p.out)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def changelog_section(version: str, neoforge: str, file_page: str, body: str, today: str) -> str:
    body = body.strip() or "_No changelog provided on CurseForge._"
    return f"## {version} — {today}\n\nNeoForge `{neoforge}` · [CurseForge file]({file_page})\n\n{body}\n"


def prepend_changelog(text: str, section: str) -> str:
    """Insert *section* above the newest release. Content of a manual
    ``## Unreleased`` section is moved into the new release as "Container changes"."""
    unreleased = ""
    m = re.search(r"^## Unreleased[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if m:
        unreleased = m.group(1).strip()
        text = text[: m.start()] + "## Unreleased\n\n" + text[m.end():]
    if unreleased:
        section = section.rstrip("\n") + "\n\n### Container changes\n\n" + unreleased + "\n"
    m = re.search(r"^## (?!Unreleased)", text, re.M)
    if m:
        return text[: m.start()] + section + "\n" + text[m.start():]
    return text.rstrip("\n") + "\n\n" + section


def extract_notes(text: str, version: str) -> str:
    m = re.search(rf"^## {re.escape(version)}\b[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        raise UpdateError(f"no CHANGELOG.md section for {version}")
    return m.group(1).strip() + "\n"


def set_readme_version(text: str, version: str, pack_name: str = "") -> str:
    text = MARKER_RE.sub(lambda m: f"{m.group(1)}{version}{m.group(2)}", text)
    if pack_name:
        text = re.sub(rf"({re.escape(pack_name)}[- ])\d+(?:\.\d+)+", rf"\g<1>{version}", text)
    return text


# --------------------------------------------------------------------------- GitHub glue
def gh_output(**kv: object) -> None:
    for k, v in kv.items():
        print(f"  {k}={v}")
    if path := os.environ.get("GITHUB_OUTPUT"):
        with open(path, "a") as f:
            for k, v in kv.items():
                f.write(f"{k}={str(v).lower() if isinstance(v, bool) else v}\n")


def gh_summary(md: str) -> None:
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a") as f:
            f.write(md + "\n")


# --------------------------------------------------------------------------- commands
def _is_server_candidate(f: dict, main_id: int, pid: int) -> bool:
    if int(f.get("modId") or 0) != pid or int(f.get("id") or 0) == main_id:
        return False
    if int(f.get("parentProjectFileId") or 0) == main_id:
        return True
    name = (f.get("fileName") or "").lower()
    return bool(f.get("isServerPack") or "server" in name)


def latest_release(env: dict[str, str]) -> tuple[dict, dict]:
    pid = int(env["CF_PROJECT_ID"])
    mod = api(f"/mods/{pid}")["data"]
    main = api(f"/mods/{pid}/files/{mod['mainFileId']}")["data"]
    if main.get("releaseType") != 1 and env.get("ALLOW_BETA", "false").lower() != "true":
        releases = [f for f in mod.get("latestFiles", []) if f.get("releaseType") == 1 and not f.get("isServerPack")]
        if not releases:
            raise UpdateError("newest main file is not a release and no release found in latestFiles")
        main = max(releases, key=lambda f: f["fileDate"])

    main_id = int(main["id"])
    print(
        f"Main file: id={main_id} name={main.get('fileName')} "
        f"serverPackFileId={main.get('serverPackFileId')} alternateFileId={main.get('alternateFileId')}"
    )

    # Tier 1 & 2: direct link fields on the main File object
    sp_id = main.get("serverPackFileId") or main.get("alternateFileId")
    if sp_id:
        return main, api(f"/mods/{pid}/files/{sp_id}")["data"]

    # Tier 3: check /v1/mods/{pid}/files for a linked child or server pack
    files = api(f"/mods/{pid}/files?pageSize=50").get("data", [])
    linked = [f for f in files if int(f.get("parentProjectFileId") or 0) == main_id]
    if not linked:
        linked = [f for f in files if _is_server_candidate(f, main_id, pid)]
    if linked:
        return main, max(linked, key=lambda f: f["fileDate"])

    # Tier 4: when an author uploads a server pack as an Additional File without
    # flagging isServerPack, CurseForge assigns it a sequential fileId near
    # main_id with parentProjectFileId == main_id. Query POST /v1/mods/files
    # in batches (-250..+10000) to locate it via the official API.
    probe_ranges = [range(main_id - 250, main_id)] + [
        range(main_id + offset, main_id + offset + 500) for offset in range(1, 10001, 500)
    ]
    for r in probe_ranges:
        batch_ids = [i for i in r if i > 0 and i != main_id]
        batch = api("/mods/files", body={"fileIds": batch_ids}).get("data", [])
        matches = [f for f in batch if _is_server_candidate(f, main_id, pid)]
        if matches:
            found = max(matches, key=lambda f: f["fileDate"])
            print(f"Found server pack via POST /v1/mods/files batch: id={found['id']} name={found.get('fileName')}")
            return main, found

    raise UpdateError(f"release {main.get('displayName')} ({main_id}) has no server pack yet")


def cmd_check(args) -> int:
    env = read_env()
    current = int(env.get("SERVER_FILE_ID") or 0)
    main, server = latest_release(env)
    sid = int(server["id"])
    version = parse_version(server["fileName"], server.get("displayName", ""), main.get("displayName", ""))
    print(f"CurseForge: {main.get('displayName')} -> server pack {server['fileName']} ({sid}), version {version}")
    print(f"pack.env:   {env.get('SERVER_VERSION')} ({current})")

    if sid == current:
        print("Already up to date.")
        gh_output(changed=False, version=env.get("SERVER_VERSION", ""))
        gh_summary(f"✅ **{env.get('PACK_NAME')}** is up to date at `{env.get('SERVER_VERSION')}`.")
        return 0
    if sid in skip_ids(env) and not args.ignore_skip:
        print(f"File {sid} is on SKIP_FILE_IDS (failed smoke test earlier). Waiting for a newer release.")
        gh_output(changed=False, version=env.get("SERVER_VERSION", ""))
        gh_summary(f"⏭️ `{version}` (file {sid}) is on the skip list. Run with *ignore_skip* to retry.")
        return 0

    candidates = [cdn_url(sid, server["fileName"])]
    if server.get("downloadUrl"):
        candidates.append(server["downloadUrl"])
    url = next((u for u in candidates if url_ok(u)), None)
    if not url:
        raise UpdateError(f"server pack is not downloadable: {candidates}")
    neo = neoforge_version(url)
    installer = f"{MAVEN}/{neo}/neoforge-{neo}-installer.jar"
    if not url_ok(installer):
        raise UpdateError(f"NeoForge installer missing on maven: {installer}")

    try:
        notes_html = api(f"/mods/{env['CF_PROJECT_ID']}/files/{main['id']}/changelog").get("data", "")
    except UpdateError as e:
        print(f"warning: changelog unavailable: {e}")
        notes_html = ""
    page = f"https://www.curseforge.com/minecraft/modpacks/{env.get('CF_SLUG', '')}/files/{main['id']}"
    section = changelog_section(version, neo, page, html_to_markdown(notes_html), dt.date.today().isoformat())

    updates = {"SERVER_VERSION": version, "NEOFORGE_VERSION": neo, "SERVER_FILE_ID": str(sid),
               "SERVER_FILE_NAME": server["fileName"], "SERVER_URL": url}
    print("\nUpdate:", json.dumps(updates, indent=2))
    print("\n" + section)
    gh_summary(
        f"### 🆕 {env.get('PACK_NAME')} `{env.get('SERVER_VERSION')}` → `{version}`\n\n"
        f"| | old | new |\n|---|---|---|\n"
        + "".join(f"| {k} | `{env.get(k, '')}` | `{v}` |\n" for k, v in updates.items())
        + ("\n_Dry run: nothing written._\n" if args.dry_run else "")
        + f"\n<details><summary>Changelog</summary>\n\n{section}\n</details>"
    )
    if not args.dry_run:
        write_env(updates)
        if README.exists():
            README.write_text(set_readme_version(README.read_text(), version, env.get("PACK_NAME", "")))
        base = CHANGELOG.read_text() if CHANGELOG.exists() else "# Changelog\n"
        CHANGELOG.write_text(prepend_changelog(base, section))
    gh_output(changed=True, version=version, neoforge=neo, file_id=sid, previous=env.get("SERVER_VERSION", ""))
    return 0


def cmd_skip(args) -> int:
    env = read_env()
    ids = skip_ids(env) | {int(args.file_id)}
    write_env({"SKIP_FILE_IDS": " ".join(str(i) for i in sorted(ids))})
    print(f"SKIP_FILE_IDS={' '.join(map(str, sorted(ids)))}")
    return 0


def cmd_restore(args) -> int:
    old = read_env(Path(args.old_env))
    missing = [k for k in MANAGED if k not in old]
    if missing:
        raise UpdateError(f"{args.old_env} lacks {missing}")
    write_env({k: old[k] for k in MANAGED})
    if README.exists():
        README.write_text(set_readme_version(README.read_text(), old["SERVER_VERSION"], old.get("PACK_NAME", "")))
    print(f"Restored pack.env to {old['SERVER_VERSION']} ({old['SERVER_FILE_ID']})")
    return 0


def cmd_notes(args) -> int:
    sys.stdout.write(extract_notes(CHANGELOG.read_text(), args.version))
    return 0


def cmd_neoforge(args) -> int:
    print(neoforge_version(args.url))
    return 0


def cmd_dockerhub(_args) -> int:
    user = os.environ.get("DOCKERHUB_USERNAME", "").strip()
    secret = os.environ.get("DOCKERHUB_TOKEN", "").strip()
    if not user or not secret:
        raise UpdateError("DOCKERHUB_USERNAME and DOCKERHUB_TOKEN must be set")
    env = read_env()
    repo = f"{user.lower()}/{env['IMAGE_NAME']}"
    short = f"A Modded Java Minecraft server container for Unraid that runs {env['PACK_NAME']}-{env['SERVER_VERSION']}"[:100]
    full = README.read_text() if README.exists() else short
    payload = json.dumps({"description": short, "full_description": full}).encode("utf-8")

    auth_headers: list[tuple[str, str]] = []
    for label, url, body, key, schemes in [
        ("users/login", "https://hub.docker.com/v2/users/login", {"username": user, "password": secret}, "token", ["JWT", "Bearer"]),
        ("auth/token", "https://hub.docker.com/v2/auth/token", {"identifier": user, "secret": secret}, "access_token", ["Bearer"]),
    ]:
        try:
            with http(
                url,
                method="POST",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                data=json.dumps(body).encode("utf-8"),
            ) as r:
                tok = json.load(r).get(key)
                if tok:
                    for s in schemes:
                        auth_headers.append((f"{label}:{s}", f"{s} {tok}"))
        except urllib.error.HTTPError as e:
            print(f"Docker Hub {label} -> HTTP {e.code}")

    if not auth_headers:
        raise UpdateError("Docker Hub login failed")

    last_detail = ""
    for label, auth_header in auth_headers:
        for suffix in ("", "/"):
            target = f"https://hub.docker.com/v2/repositories/{repo}{suffix}"
            try:
                with http(
                    target,
                    method="PATCH",
                    headers={"Authorization": auth_header, "Content-Type": "application/json", "Accept": "application/json"},
                    data=payload,
                ) as r:
                    print(f"Updated Docker Hub {repo} via {label}{suffix} (HTTP {r.status}): {short}")
                    return 0
            except urllib.error.HTTPError as e:
                last_detail = f"{label}{suffix} -> HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
                print(last_detail)

    print(
        f"::warning title=Docker Hub description not updated::{last_detail}"
    )
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--ignore-skip", action="store_true")
    c.set_defaults(fn=cmd_check)
    s = sub.add_parser("skip"); s.add_argument("file_id", type=int); s.set_defaults(fn=cmd_skip)
    r = sub.add_parser("restore"); r.add_argument("old_env"); r.set_defaults(fn=cmd_restore)
    n = sub.add_parser("notes"); n.add_argument("version"); n.set_defaults(fn=cmd_notes)
    f = sub.add_parser("neoforge"); f.add_argument("url"); f.set_defaults(fn=cmd_neoforge)
    d = sub.add_parser("dockerhub"); d.set_defaults(fn=cmd_dockerhub)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except UpdateError as e:
        print(f"::error::{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
