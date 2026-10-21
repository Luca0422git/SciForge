# SPDX-License-Identifier: LGPL-2.1-or-later
"""Keeping API keys (sciforge/secrets_store.py): the owner-only file fallback for real, and
the Windows DPAPI, macOS Keychain and Linux keyring paths with their system calls
replaced by stand-ins. Runs without FreeCAD."""

import base64
import ctypes
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import secrets_store  # noqa: E402

VALUE = "sk-ant-api03-VERYSECRETVALUE-0123456789"


class Logged:
    def __init__(self):
        self.lines = []

    def __call__(self, line):
        self.lines.append(line)


class TempFolder(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sciforge-secrets-")
        self.folder = os.path.join(self.root, "SciForge", "secrets")
        self.log = Logged()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def assert_never_logged(self):
        self.assertTrue(all(line.startswith("[SciForge]") for line in self.log.lines))
        self.assertNotIn(VALUE, "\n".join(self.log.lines))
        self.assertNotIn("VERYSECRET", "\n".join(self.log.lines))


class FileFallback(TempFolder):
    def store(self):
        return secrets_store.Store(self.folder, self.log, backend="file")

    def test_round_trip_and_delete(self):
        s = self.store()
        self.assertTrue(s.store("ai.anthropic", VALUE))
        self.assertEqual(s.read("ai.anthropic"), VALUE)
        self.assertTrue(s.store("ai.openai", "sk-other"))
        self.assertEqual(
            secrets_store.Store(self.folder, self.log, "file").read("ai.anthropic"), VALUE
        )
        self.assertTrue(s.delete("ai.anthropic"))
        self.assertIsNone(s.read("ai.anthropic"))
        self.assertEqual(s.read("ai.openai"), "sk-other")
        self.assertTrue(s.delete("never.stored"))
        self.assert_never_logged()

    @unittest.skipIf(os.name == "nt", "POSIX permissions")
    def test_owner_only_permissions(self):
        s = self.store()
        s.store("ai.anthropic", VALUE)
        path = os.path.join(self.folder, secrets_store.FILE_NAME)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.folder).st_mode) & 0o077, 0)
        os.chmod(path, 0o644)  # someone loosened it: the next write tightens it again
        s.store("ai.gemini", "AIza-x")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertFalse(os.path.exists(path + ".tmp"))

    def test_corrupt_file_is_tolerated_and_kept(self):
        os.makedirs(self.folder)
        path = os.path.join(self.folder, secrets_store.FILE_NAME)
        with open(path, "w") as handle:
            handle.write("{not json")
        s = self.store()
        self.assertIsNone(s.read("ai.anthropic"))
        self.assertTrue(s.store("ai.anthropic", VALUE))
        self.assertEqual(s.read("ai.anthropic"), VALUE)
        with open(path + ".unreadable") as handle:
            self.assertEqual(handle.read(), "{not json")
        with open(path, "w") as handle:
            json.dump({"secrets": ["wrong shape"]}, handle)
        self.assertIsNone(s.read("ai.anthropic"))
        self.assertTrue(any("could not be read" in line for line in self.log.lines))
        self.assert_never_logged()

    def test_bad_names_and_values(self):
        s = self.store()
        for name in ("", "a/b", "../x", "x" * 101, None, 5):
            self.assertFalse(s.store(name, VALUE), name)
            self.assertIsNone(s.read(name))
        self.assertFalse(s.store("ok", ""))
        self.assertFalse(s.store("ok", None))
        self.assertFalse(os.path.exists(os.path.join(self.folder, secrets_store.FILE_NAME)))

    def test_warning_sentence(self):
        self.assertEqual(
            self.store().warning(),
            "Your key is kept in a file only your account can read; it is not encrypted on "
            "this computer.",
        )
        self.assertEqual(self.store().backend_name, "file")

    def test_unwritable_folder_is_a_false_not_an_exception(self):
        blocker = os.path.join(self.root, "file-not-folder")
        open(blocker, "w").close()
        s = secrets_store.Store(os.path.join(blocker, "secrets"), self.log, backend="file")
        self.assertFalse(s.store("ai.anthropic", VALUE))
        self.assertIsNone(s.read("ai.anthropic"))
        self.assert_never_logged()

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux choice")
    def test_auto_on_linux(self):
        s = secrets_store.Store(self.folder, self.log)
        if (
            secrets_store._keyring_module() is None
            and secrets_store._secretstorage_module() is None
        ):
            self.assertEqual(s.backend_name, "file")
            self.assertTrue(s.warning())
        # Module-level helpers work the same way.
        self.assertTrue(secrets_store.store("ai.x", VALUE, self.folder, self.log))
        self.assertEqual(secrets_store.read("ai.x", self.folder), VALUE)
        self.assertTrue(secrets_store.delete("ai.x", self.folder))
        self.assertIsNone(secrets_store.read("ai.x", self.folder))
        self.assertIsInstance(secrets_store.warning(self.folder), str)


class FakeCrypt32:
    """Stands in for crypt32.dll: reads the DATA_BLOBs ctypes passes, as Windows would, and
    answers in a buffer the caller must LocalFree. "Encryption" is a XOR, enough to see that
    blobs, entropy and lengths are handled right."""

    def __init__(self, fail=False):
        self.fail = fail
        self.buffers = []
        self.entropies = []
        self.descriptions = []

    @staticmethod
    def _read(byref_blob):
        blob = byref_blob._obj
        return ctypes.string_at(blob.pbData, blob.cbData)

    def _answer(self, out_byref, data):
        buffer = ctypes.create_string_buffer(data, len(data))
        self.buffers.append(buffer)
        out = out_byref._obj
        out.cbData = len(data)
        out.pbData = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))
        return 1

    def CryptProtectData(self, data_in, description, entropy, reserved, prompt, flags, out):
        if self.fail:
            return 0
        self.descriptions.append(description)
        self.entropies.append(self._read(entropy))
        assert flags == secrets_store.CRYPTPROTECT_UI_FORBIDDEN
        return self._answer(out, b"DPAPI" + bytes(b ^ 0x5A for b in self._read(data_in)))

    def CryptUnprotectData(self, data_in, description, entropy, reserved, prompt, flags, out):
        blob = self._read(data_in)
        if self.fail or not blob.startswith(b"DPAPI"):
            return 0
        self.entropies.append(self._read(entropy))
        return self._answer(out, bytes(b ^ 0x5A for b in blob[5:]))


class FakeKernel32:
    def __init__(self):
        self.freed = []

    def LocalFree(self, pointer):
        self.freed.append(pointer.value)
        return None


class Dpapi(TempFolder):
    def backend(self, fail=False):
        self.crypt32, self.kernel32 = FakeCrypt32(fail), FakeKernel32()
        dpapi = secrets_store.Dpapi(self.crypt32, self.kernel32)
        return secrets_store.DpapiBackend(self.folder, self.log, dpapi)

    def test_blob_round_trip(self):
        dpapi = secrets_store.Dpapi(FakeCrypt32(), FakeKernel32())
        for data in (b"", b"x", VALUE.encode("utf-8"), bytes(range(256)) * 10):
            self.assertEqual(dpapi.unprotect(dpapi.protect(data)), data)

    def test_store_read_delete_through_the_store(self):
        s = secrets_store.Store(self.folder, self.log, backend=self.backend())
        self.assertTrue(s.store("ai.anthropic", VALUE))
        self.assertEqual(s.backend_name, "dpapi")
        self.assertEqual(s.warning(), "")
        path = os.path.join(self.folder, secrets_store.DPAPI_FILE_NAME)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn(VALUE, text)  # only the encrypted blob is on disk
        blob = base64.b64decode(json.loads(text)["secrets"]["ai.anthropic"])
        self.assertTrue(blob.startswith(b"DPAPI"))
        self.assertEqual(s.read("ai.anthropic"), VALUE)
        self.assertEqual(set(self.crypt32.entropies), {b"SciForge secrets v1"})
        self.assertEqual(self.crypt32.descriptions, ["SciForge"])
        freed = {ctypes.addressof(b) for b in self.crypt32.buffers}
        self.assertEqual(set(self.kernel32.freed), freed)  # every answer buffer is freed
        self.assertTrue(s.delete("ai.anthropic"))
        self.assertIsNone(s.read("ai.anthropic"))
        self.assert_never_logged()

    def test_failures_are_false_and_none(self):
        s = secrets_store.Store(self.folder, self.log, backend=self.backend(fail=True))
        self.assertFalse(s.store("ai.anthropic", VALUE))
        good = self.backend()
        good.store("ai.anthropic", VALUE)
        self.assertIsNone(self.backend(fail=True).read("ai.anthropic"))  # another Windows user
        with open(good.path, "w", encoding="utf-8") as handle:
            json.dump({"secrets": {"ai.anthropic": "!!not base64!!"}}, handle)
        self.assertIsNone(good.read("ai.anthropic"))
        self.assert_never_logged()


class FakeRun:
    def __init__(self, code=0, stdout=""):
        self.code, self.stdout, self.commands = code, stdout, []

    def __call__(self, command, **kwargs):
        self.commands.append(command)

        class Done:
            returncode = self.code
            stdout = self.stdout

        return Done()


class Keychain(TempFolder):
    def test_security_commands(self):
        run = FakeRun(stdout=VALUE + "\n")
        backend = secrets_store.KeychainBackend(self.folder, self.log, run)
        self.assertTrue(backend.store("ai.anthropic", VALUE))
        self.assertEqual(
            run.commands[0],
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                "SciForge",
                "-a",
                "ai.anthropic",
                "-w",
                VALUE,
            ],
        )
        self.assertEqual(backend.read("ai.anthropic"), VALUE)
        self.assertTrue(backend.delete("ai.anthropic"))
        self.assertFalse(
            secrets_store.KeychainBackend(None, self.log, FakeRun(code=45)).store("a", VALUE)
        )
        self.assertIsNone(secrets_store.KeychainBackend(None, self.log, FakeRun(code=44)).read("a"))

        def missing(command, **kwargs):
            raise FileNotFoundError("security")

        self.assertIsNone(secrets_store.KeychainBackend(None, self.log, missing).read("a"))
        self.assert_never_logged()


class FakeKeyring:
    def __init__(self):
        self.data = {}

    def set_password(self, service, name, value):
        self.data[(service, name)] = value

    def get_password(self, service, name):
        return self.data.get((service, name))

    def delete_password(self, service, name):
        del self.data[(service, name)]


class BrokenKeyring(FakeKeyring):
    """A keyring module with no keyring service behind it (a bare desktop, a container)."""

    def set_password(self, service, name, value):
        raise RuntimeError("no keyring service is running")


class Keyring(TempFolder):
    def test_a_keyring_without_a_service_falls_back_to_the_private_file(self):
        # Found by the first release build: a runner had the keyring module but no service, and the
        # key was simply not saved. It goes to the private file, and the warning says so.
        s = secrets_store.Store(
            self.folder,
            self.log,
            backend=secrets_store.KeyringBackend(BrokenKeyring(), self.log),
        )
        self.assertEqual(s.warning(), "")  # (until a key has had to go to the file)
        self.assertTrue(s.store("ai.anthropic", VALUE))
        self.assertEqual(s.read("ai.anthropic"), VALUE)
        self.assertEqual(
            secrets_store.FileBackend(self.folder, self.log).read("ai.anthropic"), VALUE
        )
        self.assertEqual(s.warning(), secrets_store.FILE_WARNING)
        self.assert_never_logged()

    def test_keyring_and_old_plain_copy(self):
        # A key stored in the file while the keyring was unavailable is still found, and
        # storing it again moves it into the keyring.
        secrets_store.Store(self.folder, self.log, backend="file").store("ai.anthropic", "old")
        ring = FakeKeyring()
        s = secrets_store.Store(
            self.folder, self.log, backend=secrets_store.KeyringBackend(ring, self.log)
        )
        self.assertEqual(s.read("ai.anthropic"), "old")
        self.assertTrue(s.store("ai.anthropic", VALUE))
        self.assertEqual(ring.data[("SciForge", "ai.anthropic")], VALUE)
        self.assertIsNone(secrets_store.FileBackend(self.folder, self.log).read("ai.anthropic"))
        self.assertEqual(s.read("ai.anthropic"), VALUE)
        self.assertTrue(s.delete("ai.anthropic"))
        self.assertTrue(s.delete("ai.anthropic"))  # twice is fine
        self.assertIsNone(s.read("ai.anthropic"))
        self.assertEqual(s.warning(), "")
        self.assert_never_logged()


if __name__ == "__main__":
    unittest.main()
