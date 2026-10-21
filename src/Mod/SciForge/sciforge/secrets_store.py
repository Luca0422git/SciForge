# SPDX-License-Identifier: LGPL-2.1-or-later
"""Keeps secrets (AI API keys now, cloud sign-in tokens later) on this computer, each
under a name such as "ai.anthropic" (docs/sciforge/dev/briefs/home-cloud-ai.md, 3.5).

Where they go, by system, so that another account on the computer cannot read them:
  * Windows: encrypted with DPAPI for the current Windows user (CryptProtectData through
    ctypes); the encrypted blobs live in secrets.dpapi.json in the folder the GUI passes
    (<user data>/SciForge/secrets). Copying that file to another account or computer is
    useless: only this Windows user can decrypt it.
  * macOS: the login Keychain, through the `security` command (generic passwords, service
    "SciForge"). The value is passed on that command's command line for a moment.
  * Linux: the desktop's Secret Service (GNOME Keyring, KWallet) when the `keyring` or
    `secretstorage` Python module is installed; otherwise secrets.json in that folder,
    readable only by this account (permissions 0600) but NOT encrypted. warning() then
    returns the sentence the settings should show.
Values are never logged. Nothing here raises: store() and delete() answer True / False,
read() answers the value or None.

Pure Python standard library; no FreeCAD, no Qt.
"""

import base64
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys

SERVICE = "SciForge"
FILE_NAME = "secrets.json"
DPAPI_FILE_NAME = "secrets.dpapi.json"
FILE_WARNING = (
    "Your key is kept in a file only your account can read; it is not encrypted on this "
    "computer."
)
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_ENTROPY = b"SciForge secrets v1"


def _default_log(line):
    print(line, file=sys.stderr)


def valid_name(name):
    return isinstance(name, str) and bool(_NAME.match(name))


# -- owner-only JSON files ------------------------------------------------------------
def _read_json(path, log):
    """{name: value} from a JSON secrets file; {} when it is missing or unreadable."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        secrets = data.get("secrets") if isinstance(data, dict) else None
        if not isinstance(secrets, dict):
            raise ValueError("no secrets table")
        return {k: v for k, v in secrets.items() if isinstance(k, str) and isinstance(v, str)}
    except Exception as exc:
        log("[SciForge] secrets: %s could not be read (%s); it is treated as empty" % (path, exc))
        return {}


def _write_json(path, kind, secrets, log):
    """Write the table atomically with owner-only permissions. True when it worked."""
    folder = os.path.dirname(path)
    try:
        os.makedirs(folder, mode=0o700, exist_ok=True)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    json.load(handle)
            except Exception:  # keep an unreadable file instead of losing it silently
                shutil.copyfile(path, path + ".unreadable")
        temp = path + ".tmp"
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "kind": kind, "secrets": secrets}, handle, indent=1)
        if os.name != "nt":
            os.chmod(temp, 0o600)
        os.replace(temp, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
        return True
    except Exception as exc:
        log("[SciForge] secrets: could not write %s (%s)" % (path, exc))
        return False


class FileBackend:
    """Plain owner-only file: the last resort."""

    name = "file"
    encrypted = False

    def __init__(self, folder, log=_default_log):
        self.path = os.path.join(folder, FILE_NAME)
        self.log = log

    def store(self, name, value):
        secrets = _read_json(self.path, self.log)
        secrets[name] = value
        return _write_json(self.path, "plain", secrets, self.log)

    def read(self, name):
        return _read_json(self.path, self.log).get(name)

    def delete(self, name):
        secrets = _read_json(self.path, self.log)
        if name not in secrets:
            return True
        del secrets[name]
        return _write_json(self.path, "plain", secrets, self.log)


# -- Windows DPAPI --------------------------------------------------------------------
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


CRYPTPROTECT_UI_FORBIDDEN = 0x01


class Dpapi:
    """CryptProtectData / CryptUnprotectData for the current user. crypt32 and kernel32
    are the DLLs (ctypes.windll.crypt32 / kernel32); tests pass stand-ins."""

    def __init__(self, crypt32=None, kernel32=None):
        if crypt32 is None or kernel32 is None:
            windll = ctypes.windll  # only exists on Windows
            crypt32, kernel32 = windll.crypt32, windll.kernel32
            blob_p = ctypes.POINTER(DATA_BLOB)
            args = [blob_p, ctypes.c_wchar_p, blob_p, ctypes.c_void_p, ctypes.c_void_p]
            crypt32.CryptProtectData.argtypes = args + [ctypes.c_uint32, blob_p]
            crypt32.CryptUnprotectData.argtypes = [
                blob_p,
                ctypes.c_void_p,
                blob_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_uint32,
                blob_p,
            ]
            kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self.crypt32, self.kernel32 = crypt32, kernel32

    @staticmethod
    def _blob(data):
        buffer = ctypes.create_string_buffer(data, len(data))
        return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer

    def _take(self, blob):
        try:
            return ctypes.string_at(blob.pbData, blob.cbData)
        finally:
            self.kernel32.LocalFree(ctypes.cast(blob.pbData, ctypes.c_void_p))

    def protect(self, data):
        data_in, _keep = self._blob(data)
        entropy, _keep2 = self._blob(_ENTROPY)
        out = DATA_BLOB()
        ok = self.crypt32.CryptProtectData(
            ctypes.byref(data_in),
            SERVICE,
            ctypes.byref(entropy),
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out),
        )
        if not ok:
            raise OSError("CryptProtectData failed")
        return self._take(out)

    def unprotect(self, blob):
        data_in, _keep = self._blob(blob)
        entropy, _keep2 = self._blob(_ENTROPY)
        out = DATA_BLOB()
        ok = self.crypt32.CryptUnprotectData(
            ctypes.byref(data_in),
            None,
            ctypes.byref(entropy),
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out),
        )
        if not ok:
            raise OSError("CryptUnprotectData failed (another Windows user's file?)")
        return self._take(out)


class DpapiBackend:
    name = "dpapi"
    encrypted = True

    def __init__(self, folder, log=_default_log, dpapi=None):
        self.path = os.path.join(folder, DPAPI_FILE_NAME)
        self.log = log
        self.dpapi = dpapi or Dpapi()

    def store(self, name, value):
        try:
            blob = self.dpapi.protect(value.encode("utf-8"))
        except Exception as exc:
            self.log("[SciForge] secrets: could not encrypt %s (%s)" % (name, exc))
            return False
        secrets = _read_json(self.path, self.log)
        secrets[name] = base64.b64encode(blob).decode("ascii")
        return _write_json(self.path, "dpapi", secrets, self.log)

    def read(self, name):
        encoded = _read_json(self.path, self.log).get(name)
        if encoded is None:
            return None
        try:
            return self.dpapi.unprotect(base64.b64decode(encoded, validate=True)).decode("utf-8")
        except Exception as exc:
            self.log("[SciForge] secrets: could not decrypt %s (%s)" % (name, exc))
            return None

    def delete(self, name):
        secrets = _read_json(self.path, self.log)
        if name not in secrets:
            return True
        del secrets[name]
        return _write_json(self.path, "dpapi", secrets, self.log)


# -- macOS Keychain -------------------------------------------------------------------
class KeychainBackend:
    name = "keychain"
    encrypted = True

    def __init__(self, folder=None, log=_default_log, run=subprocess.run):
        self.log = log
        self.run = run

    def _security(self, *args):
        try:
            return self.run(["security"] + list(args), capture_output=True, text=True, timeout=20)
        except Exception as exc:
            self.log("[SciForge] secrets: the security command failed (%s)" % type(exc).__name__)
            return None

    def store(self, name, value):
        done = self._security("add-generic-password", "-U", "-s", SERVICE, "-a", name, "-w", value)
        if done is None or done.returncode != 0:
            self.log("[SciForge] secrets: the Keychain did not store %s" % name)
            return False
        return True

    def read(self, name):
        done = self._security("find-generic-password", "-s", SERVICE, "-a", name, "-w")
        if done is None or done.returncode != 0:
            return None
        return done.stdout.rstrip("\n")

    def delete(self, name):
        done = self._security("delete-generic-password", "-s", SERVICE, "-a", name)
        return done is not None and done.returncode in (0, 44)  # 44: there was none


# -- Linux Secret Service -------------------------------------------------------------
class KeyringBackend:
    name = "keyring"
    encrypted = True

    def __init__(self, module, log=_default_log):
        self.keyring = module
        self.log = log

    def store(self, name, value):
        try:
            self.keyring.set_password(SERVICE, name, value)
            return True
        except Exception as exc:
            self.log(
                "[SciForge] secrets: the keyring did not store %s (%s)" % (name, type(exc).__name__)
            )
            return False

    def read(self, name):
        try:
            return self.keyring.get_password(SERVICE, name)
        except Exception:
            return None

    def delete(self, name):
        try:
            self.keyring.delete_password(SERVICE, name)
        except Exception:
            pass  # there was none, or the keyring is locked
        return True


class SecretStorageBackend:
    name = "secretstorage"
    encrypted = True

    def __init__(self, module, log=_default_log):
        self.ss = module
        self.log = log

    def _collection(self):
        connection = self.ss.dbus_init()
        collection = self.ss.get_default_collection(connection)
        if collection.is_locked():
            collection.unlock()
        return collection

    def _attributes(self, name):
        return {"application": SERVICE, "name": name}

    def store(self, name, value):
        try:
            self._collection().create_item(
                "%s: %s" % (SERVICE, name), self._attributes(name), value.encode("utf-8"), True
            )
            return True
        except Exception as exc:
            self.log(
                "[SciForge] secrets: the Secret Service did not store %s (%s)"
                % (name, type(exc).__name__)
            )
            return False

    def read(self, name):
        try:
            for item in self._collection().search_items(self._attributes(name)):
                return item.get_secret().decode("utf-8")
        except Exception:
            pass
        return None

    def delete(self, name):
        try:
            for item in self._collection().search_items(self._attributes(name)):
                item.delete()
        except Exception:
            pass
        return True


def _keyring_module():
    try:
        import keyring  # optional, not part of SciForge
    except Exception:
        return None
    try:
        backend = keyring.get_keyring()
        label = (type(backend).__module__ + "." + type(backend).__name__).lower()
        if "fail" in label or "null" in label or getattr(backend, "priority", 1) <= 0:
            return None
    except Exception:
        return None
    return keyring


def _secretstorage_module():
    try:
        import secretstorage  # optional, not part of SciForge

        secretstorage.get_default_collection(secretstorage.dbus_init())
        return secretstorage
    except Exception:
        return None


# -- choosing the store ---------------------------------------------------------------
class Store:
    """The secrets of one folder. backend: "auto" (by system), "file", or a backend object.
    A secret that only the file fallback holds is still found (it may have been stored
    while the system store was unavailable)."""

    def __init__(self, folder, log=None, backend="auto"):
        self.folder = folder
        self.log = log or _default_log
        self.fallback = FileBackend(folder, self.log)
        self.primary = self._choose(backend)
        self.fell_back = False  # a key went to the file because the system store refused it

    def _choose(self, backend):
        if not isinstance(backend, str):
            return backend
        if backend == "file":
            return self.fallback
        try:
            if sys.platform == "win32":
                return DpapiBackend(self.folder, self.log)
            if sys.platform == "darwin" and shutil.which("security"):
                return KeychainBackend(self.folder, self.log)
            if sys.platform.startswith("linux"):
                module = _keyring_module()
                if module is not None:
                    return KeyringBackend(module, self.log)
                module = _secretstorage_module()
                if module is not None:
                    return SecretStorageBackend(module, self.log)
        except Exception as exc:
            self.log("[SciForge] secrets: no system store (%s); using a private file" % exc)
        return self.fallback

    @property
    def backend_name(self):
        return self.primary.name

    def warning(self):
        """The sentence to show when keys are not encrypted, else ""."""
        if self.fell_back:
            return FILE_WARNING
        return "" if getattr(self.primary, "encrypted", False) else FILE_WARNING

    def store(self, name, value):
        if not valid_name(name) or not isinstance(value, str) or not value:
            self.log("[SciForge] secrets: refused to store a secret with a bad name or value")
            return False
        try:
            if self.primary.store(name, value):
                if self.primary is not self.fallback:
                    self.fallback.delete(name)  # an older plain copy must not linger
                self.log("[SciForge] secrets: stored %s (%s)" % (name, self.primary.name))
                return True
        except Exception as exc:
            self.log("[SciForge] secrets: could not store %s (%s)" % (name, type(exc).__name__))
        # Linux only: a keyring module is installed but no keyring service is running (a bare
        # desktop, a container), so the system store cannot take the key. Linux has always kept
        # keys in the private file when there is no keyring, so it goes there and the warning
        # says it is not encrypted. Windows and macOS never quietly downgrade to a plain file.
        if getattr(self.primary, "name", "") in ("keyring", "secretstorage"):
            try:
                if self.fallback.store(name, value):
                    self.fell_back = True
                    self.log("[SciForge] secrets: stored %s (file: the system store was unavailable)" % name)
                    return True
            except Exception as exc:
                self.log("[SciForge] secrets: could not store %s (%s)" % (name, type(exc).__name__))
        return False

    def read(self, name):
        if not valid_name(name):
            return None
        try:
            value = self.primary.read(name)
            if value is None and self.primary is not self.fallback:
                value = self.fallback.read(name)
            return value
        except Exception as exc:
            self.log("[SciForge] secrets: could not read %s (%s)" % (name, type(exc).__name__))
            return None

    def delete(self, name):
        if not valid_name(name):
            return False
        try:
            ok = self.primary.delete(name)
            if self.primary is not self.fallback:
                ok = self.fallback.delete(name) and ok
            self.log("[SciForge] secrets: deleted %s" % name)
            return bool(ok)
        except Exception as exc:
            self.log("[SciForge] secrets: could not delete %s (%s)" % (name, type(exc).__name__))
            return False


_STORES = {}


def _store(folder, log=None):
    key = os.path.abspath(folder)
    if key not in _STORES:
        _STORES[key] = Store(folder, log)
    return _STORES[key]


def store(name, value, folder, log=None):
    """Keep value under name. True when it was stored."""
    return _store(folder, log).store(name, value)


def read(name, folder, log=None):
    """The value stored under name, or None."""
    return _store(folder, log).read(name)


def delete(name, folder, log=None):
    """Forget name. True when nothing is left under it."""
    return _store(folder, log).delete(name)


def warning(folder, log=None):
    """The plain sentence to show next to the key field ("" when keys are encrypted)."""
    return _store(folder, log).warning()
