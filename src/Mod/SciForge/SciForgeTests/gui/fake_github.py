# SPDX-License-Identifier: LGPL-2.1-or-later
"""A fake GitHub for the update scenarios (update_check.py): a web server on this computer's own
address, in a thread, that answers like GitHub's releases API and serves the release's files.
No test may touch the real internet (update_core.blocked).

    fake = FakeGitHub()
    fake.publish("0.1.0-beta.2", core="abc", module=True)   # a release with its files
    update_core.API_BASE = fake.base
    ...
    fake.stop()                                              # now "offline": connection refused
"""

import hashlib
import http.server
import io
import json
import os
import threading
import time
import zipfile

REPO = "Luca0422git/SciForge"


def module_zip(extra_kb=0):
    """A quick-update zip like make_quick_update.sh's: install_update.ps1 and SciForge/ (the
    padding is random bytes, stored, so a download takes a few chunks)."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("install_update.ps1", "# the fake update script\n")
        archive.writestr("SciForge/InitGui.py", "# the fake new module\n")
        archive.writestr("SciForge/sciforge/__init__.py", "")
        if extra_kb:
            archive.writestr("SciForge/padding.bin", os.urandom(extra_kb * 1024))
    return out.getvalue()


class FakeGitHub:
    def __init__(self):
        self.releases = []  # what the releases list answers
        self.files = {}  # path -> bytes
        self.hits = []  # every path asked for, in order
        self.agents = []  # the User-Agent of every request
        self.delay = 0.0  # seconds before every answer (a slow GitHub)
        self.slow = False  # serve /dl/ files in small pieces with pauses
        self.base = ""
        self.server = None
        self.start()

    # -- the server ---------------------------------------------------------------------
    def start(self):
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.hits.append(self.path)
                outer.agents.append(self.headers.get("User-Agent", ""))
                if outer.delay:
                    time.sleep(outer.delay)
                if self.path.startswith("/repos/%s/releases" % REPO):
                    body, status = json.dumps(outer.releases).encode(), 200
                elif self.path in outer.files:
                    body, status = outer.files[self.path], 200
                else:
                    body, status = b"{}", 404
                try:
                    self.send_response(status)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    if outer.slow and self.path.startswith("/dl/") and not self.path.endswith(".json"):
                        for start in range(0, len(body), 32 * 1024):
                            self.wfile.write(body[start : start + 32 * 1024])
                            self.wfile.flush()
                            time.sleep(0.12)
                    else:
                        self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # (the person pressed Cancel)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        ).start()

    def stop(self):
        """Now nothing answers: connection refused, like a computer without internet."""
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    # -- what is published -----------------------------------------------------------------
    def publish(self, version, core="testcore", prerelease=True, module=True, installer=True,
                bad_module_hash=False, manifest=True, extra_kb=0, notes_url=""):  # fmt: skip
        """Add a release (newest first) with the files its sciforge-release.json describes."""
        tag = "sciforge-v" + version
        names = {
            "installer": "SciForge_v%s-Windows-x86_64-py311-installer.exe" % version,
            "module": "SciForge-quick-update-v%s.zip" % version,
        }
        data = {
            "installer": b"MZ installer of " + version.encode() + os.urandom(150 * 1024),
            "module": module_zip(extra_kb),
        }
        assets, sha, roles = {}, {}, {}
        for role in ("installer", "module"):
            if (role == "module" and not module) or (role == "installer" and not installer):
                continue
            roles[role] = names[role]
            self.files["/dl/" + names[role]] = data[role]
            assets[names[role]] = self.base + "/dl/" + names[role]
            sha[names[role]] = hashlib.sha256(data[role]).hexdigest()
        if bad_module_hash and module:
            sha[names["module"]] = "0" * 64
        if manifest:
            record = {
                "version": version, "tag": tag, "core": core, "date": "2026-10-21",
                "notes_url": notes_url or "https://github.com/%s/releases/tag/%s" % (REPO, tag),
                "assets": roles, "sha256": sha,
            }  # fmt: skip
            self.files["/dl/%s/sciforge-release.json" % version] = json.dumps(record).encode()
            assets["sciforge-release.json"] = self.base + "/dl/%s/sciforge-release.json" % version
        entry = {
            "tag_name": tag,
            "draft": False,
            "prerelease": prerelease,
            "html_url": "https://github.com/%s/releases/tag/%s" % (REPO, tag),
            "assets": [
                {"name": n, "browser_download_url": u, "size": len(self.files.get(u[len(self.base):], b""))}
                for n, u in assets.items()
            ],
        }  # fmt: skip
        self.releases.insert(0, entry)
        return names

    def clear(self):
        self.releases = []
        self.files = {}

    def count(self, prefix):
        return sum(1 for path in self.hits if path.startswith(prefix))
