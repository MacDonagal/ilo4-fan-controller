#!/usr/bin/env python3
"""
Sync a folder of Markdown files to a Docmost space.

- Every sub-folder of DOCS_DIR becomes a parent page (named after the folder).
- Every .md file becomes a child page. Its title is the first "# " heading
  (removed from the body), or the file name.
- Existing pages (same title under the same parent) are updated in place
  (content replaced), new ones are created. Pages are never deleted.
- Unchanged files are skipped (hash kept in a state file), so the page
  history only grows when the content really changes.

Requires a Docmost version whose API accepts Markdown content
(pages/create and pages/update with "format": "markdown").
Standard library only.

Environment:
  DOCMOST_URL            ex. https://docmost.example.lan
  DOCMOST_EMAIL          account used for the sync (without MFA)
  DOCMOST_PASSWORD_FILE  file containing the password (or DOCMOST_PASSWORD)
  DOCMOST_SPACE          space name, slug or id
  DOCS_DIR               folder with the Markdown files (default: ./docs)
  STATE_FILE             default: <DOCS_DIR>/.docmost-sync.json
  DRY_RUN=1              show what would be done, change nothing
"""
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"Missing environment variable: {name}")
    return value


BASE = env("DOCMOST_URL", required=True).rstrip("/")
DRY_RUN = env("DRY_RUN", "0") == "1"
DOCS_DIR = Path(env("DOCS_DIR", "docs")).resolve()
STATE_FILE = Path(env("STATE_FILE", str(DOCS_DIR / ".docmost-sync.json")))
TOKEN = None


def api(path, payload):
    """POST JSON to the Docmost API, return the unwrapped "data"."""
    req = urllib.request.Request(
        f"{BASE}/api/{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode() or "{}"
            cookies = resp.headers.get_all("Set-Cookie") or []
    except urllib.error.HTTPError as err:
        sys.exit(f"API {path} -> HTTP {err.code}: {err.read().decode()[:300]}")
    data = json.loads(body)
    return (data.get("data") if isinstance(data, dict) and "data" in data else data), cookies


def login():
    global TOKEN
    password = env("DOCMOST_PASSWORD")
    if not password:
        password = Path(env("DOCMOST_PASSWORD_FILE", required=True)).read_text().strip()
    data, cookies = api("auth/login", {"email": env("DOCMOST_EMAIL", required=True), "password": password})
    if isinstance(data, dict) and (data.get("userHasMfa") or data.get("requiresMfaSetup")):
        sys.exit("This account requires MFA: use a dedicated account without MFA for the sync.")
    for cookie in cookies:
        match = re.match(r"authToken=([^;]+)", cookie)
        if match:
            TOKEN = match.group(1)
            return
    sys.exit("Login failed: no authToken cookie returned.")


def paginate(path, payload):
    items, cursor = [], None
    while True:
        body = dict(payload, limit=100)
        if cursor:
            body["cursor"] = cursor
        data, _ = api(path, body)
        items += data.get("items", [])
        meta = data.get("meta", {})
        if not meta.get("hasNextPage"):
            return items
        cursor = meta.get("nextCursor")


def find_space(wanted):
    for space in paginate("spaces", {}):
        if wanted in (space.get("id"), space.get("slug"), space.get("name")):
            return space["id"]
    sys.exit(f"Space not found (or no access): {wanted}")


def children(space_id, parent_id=None):
    payload = {"pageId": parent_id} if parent_id else {"spaceId": space_id}
    return {p.get("title"): p["id"] for p in paginate("pages/sidebar-pages", payload)}


def split_title(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip(), "\n".join(lines[1:]).lstrip("\n")
    return path.stem, text


def upsert(space_id, parent_id, existing, title, content):
    if title in existing:
        if not DRY_RUN:
            api("pages/update", {"pageId": existing[title], "content": content,
                                 "format": "markdown", "operation": "replace"})
        return "updated", existing[title]
    if DRY_RUN:
        return "created", None
    payload = {"spaceId": space_id, "title": title, "content": content, "format": "markdown"}
    if parent_id:
        payload["parentPageId"] = parent_id
    data, _ = api("pages/create", payload)
    return "created", data.get("id")


def main():
    if not DOCS_DIR.is_dir():
        sys.exit(f"Docs folder not found: {DOCS_DIR}")
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    login()
    space_id = find_space(env("DOCMOST_SPACE", required=True))

    groups = {}
    for md in sorted(DOCS_DIR.rglob("*.md")):
        rel = md.relative_to(DOCS_DIR)
        groups.setdefault(rel.parts[0] if len(rel.parts) > 1 else "", []).append(md)

    root_pages = children(space_id)
    stats = {"created": 0, "updated": 0, "unchanged": 0}
    for folder, files in groups.items():
        parent_id = None
        if folder:
            parent_id = root_pages.get(folder)
            if not parent_id:
                print(f"+ parent page: {folder}")
                _, parent_id = upsert(space_id, None, root_pages, folder, "")
                root_pages[folder] = parent_id
        existing = children(space_id, parent_id) if parent_id else root_pages
        for md in files:
            title, content = split_title(md)
            key = str(md.relative_to(DOCS_DIR))
            digest = hashlib.sha256(content.encode()).hexdigest()
            if state.get(key) == digest and title in existing:
                stats["unchanged"] += 1
                continue
            action, _ = upsert(space_id, parent_id, existing, title, content)
            stats[action] += 1
            state[key] = digest
            print(f"{'~' if action == 'updated' else '+'} {key} -> {title}")

    if not DRY_RUN:
        STATE_FILE.write_text(json.dumps(state, indent=2))
    print(("[dry run] " if DRY_RUN else "") + ", ".join(f"{k}: {v}" for k, v in stats.items()))


if __name__ == "__main__":
    main()
