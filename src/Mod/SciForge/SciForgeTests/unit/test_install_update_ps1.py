# SPDX-License-Identifier: LGPL-2.1-or-later
"""tools/sciforge/install_update.ps1 -Quiet (what "Update now" starts after SciForge quits), run
against a fake SciForge folder with PowerShell 7 (pwsh, on GitHub's Linux runners; skipped where
there is none). The real Windows PowerShell 5.1 runs the same steps in the "update script" job
of .github/workflows/sciforge-tests.yml. The fake program is a tiny shell script named
SciForge.exe that leaves a marker when it is started again."""

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))
SCRIPT = os.path.join(REPO, "tools", "sciforge", "install_update.ps1")
PWSH = os.environ.get("SCIFORGE_PWSH") or shutil.which("pwsh")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


@unittest.skipUnless(
    PWSH and os.path.isfile(SCRIPT) and sys.platform != "win32",
    "needs pwsh and the tools folder (the Windows job runs the script on Windows)",
)
class QuietUpdate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sciforge-ps1-")
        self.fake = os.path.join(self.tmp, "fake")
        self.payload = os.path.join(self.tmp, "payload")
        program = os.path.join(self.fake, "bin", "SciForge.exe")
        write(program, '#!/bin/sh\necho "started" > "$(dirname "$0")/restarted.txt"\n')
        os.chmod(program, 0o755)
        mod = os.path.join(self.fake, "Mod", "SciForge")
        write(os.path.join(mod, "InitGui.py"), "old init\n")
        write(os.path.join(mod, "sciforge", "a_first.py"), "OLD\n")
        write(os.path.join(mod, "sciforge", "old_only.py"), "only in the old version\n")
        write(os.path.join(self.payload, "SciForge", "InitGui.py"), "new init\n")
        write(os.path.join(self.payload, "SciForge", "sciforge", "a_first.py"), "NEW\n")
        write(os.path.join(self.payload, "SciForge", "sciforge", "zz_new.py"), "brand new\n")
        shutil.copy(SCRIPT, self.payload)
        self.mod = mod

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_script(self, *args, wait_for=None):
        """Run the copy of the script next to the fake update; returns (exit code, output, seconds).
        wait_for: seconds a helper process (the 'SciForge' that is quitting) lives, passed as -WaitPid."""
        command = [PWSH, "-NoProfile", "-NonInteractive", "-File", os.path.join(self.payload, "install_update.ps1")]
        helper = None
        if wait_for is not None:
            helper = subprocess.Popen(["sleep", str(wait_for)])
            threading.Thread(target=helper.wait, daemon=True).start()  # (reaped at once, as Windows does)
            command += ["-WaitPid", str(helper.pid)]
        started = time.time()
        done = subprocess.run(
            command + list(args), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120
        )
        return done.returncode, done.stdout + done.stderr, time.time() - started

    def marker(self):
        return os.path.join(self.fake, "bin", "restarted.txt")

    def wait_for_marker(self):
        for _n in range(50):
            if os.path.exists(self.marker()):
                return True
            time.sleep(0.1)
        return False

    def test_the_update_waits_replaces_backs_up_and_restarts(self):
        code, out, seconds = self.run_script("-Target", self.fake + "/", "-Restart", "-Quiet", "-NoDialog", wait_for=2)
        self.assertEqual(code, 0, out)
        self.assertGreaterEqual(seconds, 1.8, "it must wait for the process to end")
        self.assertIn("SciForge has closed", out)
        self.assertEqual(read(os.path.join(self.mod, "InitGui.py")), "new init\n")
        self.assertEqual(read(os.path.join(self.mod, "sciforge", "a_first.py")), "NEW\n")
        self.assertTrue(os.path.isfile(os.path.join(self.mod, "sciforge", "zz_new.py")))
        self.assertFalse(os.path.exists(os.path.join(self.mod, "sciforge", "old_only.py")), "old files go")
        backups = os.path.join(self.fake, "SciForge-backups")
        (stamp,) = os.listdir(backups)
        self.assertEqual(read(os.path.join(backups, stamp, "sciforge", "a_first.py")), "OLD\n")
        self.assertTrue(os.path.isfile(os.path.join(backups, stamp, "sciforge", "old_only.py")))
        self.assertTrue(self.wait_for_marker(), "SciForge was not started again")

    def test_without_restart_nothing_is_started(self):
        code, out, _seconds = self.run_script("-Target", self.fake, "-Quiet", "-NoDialog")
        self.assertEqual(code, 0, out)
        time.sleep(0.5)
        self.assertFalse(os.path.exists(self.marker()))

    def test_quiet_never_asks(self):
        # no -Target: it must stop with a message, not open a folder picker or wait for Enter
        code, out, seconds = self.run_script("-Quiet", "-NoDialog")
        self.assertEqual(code, 1, out)
        self.assertIn("No -Target given", out)
        self.assertLess(seconds, 30)
        self.assertEqual(read(os.path.join(self.mod, "InitGui.py")), "old init\n")

    def test_a_failure_puts_the_old_version_back_and_does_not_restart(self):
        # a file of the new version that cannot be read (a link to nowhere): copying fails half
        # way through, after a_first.py was already replaced
        blocked = os.path.join(self.payload, "SciForge", "sciforge", "zz_new.py")
        os.remove(blocked)
        os.symlink(os.path.join(self.tmp, "no", "such", "folder", "x.py"), blocked)
        code, out, _seconds = self.run_script("-Target", self.fake, "-Restart", "-Quiet", "-NoDialog")
        self.assertEqual(code, 1, out)
        self.assertIn("putting the old version back", out)
        self.assertEqual(read(os.path.join(self.mod, "InitGui.py")), "old init\n")
        self.assertEqual(read(os.path.join(self.mod, "sciforge", "a_first.py")), "OLD\n")
        self.assertTrue(os.path.isfile(os.path.join(self.mod, "sciforge", "old_only.py")))
        self.assertFalse(os.path.exists(os.path.join(self.mod, "sciforge", "zz_new.py")))
        time.sleep(0.5)
        self.assertFalse(os.path.exists(self.marker()), "a failed update must not restart SciForge")

    def test_a_folder_that_is_not_sciforge_changes_nothing(self):
        empty = os.path.join(self.tmp, "nothing")
        os.makedirs(empty)
        code, out, _seconds = self.run_script("-Target", empty, "-Quiet", "-NoDialog")
        self.assertEqual(code, 1, out)
        self.assertEqual(os.listdir(empty), [])

    def test_run_installer_waits_then_starts_it(self):
        installer = os.path.join(self.tmp, "SciForge-installer.exe")
        write(installer, '#!/bin/sh\necho "installer ran" > "%s"\n' % os.path.join(self.tmp, "installer.txt"))
        os.chmod(installer, 0o755)
        code, out, seconds = self.run_script("-RunInstaller", installer, "-Quiet", "-NoDialog", wait_for=2)
        self.assertEqual(code, 0, out)
        self.assertGreaterEqual(seconds, 1.8)
        for _n in range(50):
            if os.path.exists(os.path.join(self.tmp, "installer.txt")):
                break
            time.sleep(0.1)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "installer.txt")))
        self.assertEqual(read(os.path.join(self.mod, "InitGui.py")), "old init\n", "the module is not touched")

    def test_run_installer_that_is_missing_fails(self):
        code, out, _seconds = self.run_script("-RunInstaller", os.path.join(self.tmp, "nope.exe"), "-Quiet", "-NoDialog")
        self.assertEqual(code, 1, out)
        self.assertIn("The installer is not there", out)

    def test_a_process_that_is_already_gone_does_not_hold_it_up(self):
        code, out, seconds = self.run_script("-Target", self.fake, "-Quiet", "-NoDialog", "-WaitPid", "999999")
        self.assertEqual(code, 0, out)
        self.assertLess(seconds, 20)


if __name__ == "__main__":
    unittest.main()
