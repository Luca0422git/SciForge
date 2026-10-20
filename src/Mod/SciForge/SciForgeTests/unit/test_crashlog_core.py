# SPDX-License-Identifier: LGPL-2.1-or-later
"""The crash log's rules (sciforge/crashlog_core.py): file names, the clean-exit marker, "did
the last session crash", rotation, the log's tail. Runs without FreeCAD, in a temp folder."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import crashlog_core as cc  # noqa: E402


def nobody(pid):
    return False  # no process is running


def everybody(pid):
    return True


class CrashLogCore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sciforge-crash-")
        self.folder = cc.folder_in(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def start(self, now, pid=100, version="0.1.0-beta"):
        session = cc.begin(self.folder, now, pid, version)
        self.assertIsNotNone(session)
        return session

    def write(self, path, text):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    # -- names
    def test_the_folder_is_in_sciforges_own_user_folder(self):
        self.assertEqual(cc.folder_in("/data"), os.path.join("/data", "SciForge", "crash"))

    def test_session_names_sort_by_time_and_carry_the_process_number(self):
        early = time.mktime((2026, 10, 20, 9, 5, 7, 0, 0, -1))
        late = time.mktime((2026, 10, 20, 15, 30, 12, 0, 0, -1))
        a, b = cc.session_id(early, 42), cc.session_id(late, 7)
        self.assertEqual(a, "20261020-090507-42")
        self.assertLess(a, b)
        self.assertEqual(cc.log_name(a), "session-20261020-090507-42.log")
        self.assertEqual(cc.marker_name(a), "running-20261020-090507-42.json")
        self.assertNotEqual(cc.session_id(early, 1), cc.session_id(early, 2))

    def test_the_id_comes_back_out_of_either_file_name_and_junk_gives_none(self):
        sid = "20261020-153012-4242"
        self.assertEqual(cc.id_of(cc.log_name(sid)), sid)
        self.assertEqual(cc.id_of(cc.marker_name(sid)), sid)
        for junk in ("notes.txt", "session-.log", "session-abc.log", "running-1-2-3.json", ""):
            self.assertIsNone(cc.id_of(junk), junk)
        self.assertIsNone(cc.id_of(None))
        self.assertEqual(cc.when_text(sid), "2026-10-20 15:30:12")
        self.assertEqual(cc.when_text("junk"), "junk")

    # -- starting and ending
    def test_a_start_makes_a_marker_and_an_empty_log(self):
        session = self.start(1_800_000_000, pid=4242, version="0.1.0-beta")
        self.assertTrue(os.path.isfile(session["marker"]))
        self.assertTrue(os.path.isfile(session["log"]))
        self.assertEqual(os.path.getsize(session["log"]), 0)
        self.assertTrue(session["log"].endswith(".log"))

    def test_a_clean_exit_removes_the_marker_and_an_empty_log(self):
        session = self.start(1_800_000_000)
        kept = cc.end(self.folder, session["id"])
        self.assertFalse(kept)
        self.assertEqual(os.listdir(self.folder), [])

    def test_a_clean_exit_keeps_a_log_with_something_in_it(self):
        session = self.start(1_800_000_000)
        self.write(session["log"], "Traceback ...\n")
        self.assertTrue(cc.end(self.folder, session["id"]))
        self.assertEqual(os.listdir(self.folder), [os.path.basename(session["log"])])
        # (no marker: it was a clean exit, so nothing is reported as a crash)
        self.assertEqual(cc.stale_sessions(self.folder, nobody), [])

    def test_a_folder_that_cannot_be_written_gives_none_and_never_raises(self):
        blocker = os.path.join(self.tmp, "file")
        self.write(blocker, "x")
        self.assertIsNone(cc.begin(os.path.join(blocker, "crash"), 1_800_000_000, 1))
        nowhere = os.path.join(self.tmp, "nowhere")
        self.assertEqual(cc.stale_sessions(nowhere), [])
        self.assertEqual(cc.logs(nowhere), [])
        self.assertIsNone(cc.last_crash_log(nowhere))
        cc.end(nowhere, "20261020-153012-1")  # (no error)

    # -- did the last session crash?
    def test_a_marker_whose_process_is_gone_is_a_session_that_did_not_end_cleanly(self):
        session = self.start(1_800_000_000, pid=4242, version="0.1.0-beta")
        self.write(session["log"], "Fatal Python error: Segmentation fault\n")
        found = cc.stale_sessions(self.folder, nobody)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["id"], session["id"])
        self.assertEqual(found[0]["pid"], 4242)
        self.assertEqual(found[0]["version"], "0.1.0-beta")
        self.assertEqual(found[0]["log"], session["log"])
        self.assertGreater(found[0]["log_size"], 0)

    def test_a_marker_whose_process_still_runs_is_another_window_and_left_alone(self):
        self.start(1_800_000_000, pid=4242)
        self.assertEqual(cc.stale_sessions(self.folder, everybody), [])

    def test_the_running_process_is_never_stale(self):
        self.start(1_800_000_000, pid=os.getpid())
        self.assertEqual(cc.stale_sessions(self.folder), [])  # (the real pid_alive)

    def test_a_crash_without_any_log_text_still_counts(self):
        """A kill or a power cut leaves no faulthandler text: the marker alone says it."""
        self.start(1_800_000_000, pid=4242)
        found = cc.stale_sessions(self.folder, nobody)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["log_size"], 0)

    def test_several_stale_sessions_come_oldest_first(self):
        self.start(1_800_000_000, pid=1)
        self.start(1_800_000_500, pid=2)
        ids = [s["id"] for s in cc.stale_sessions(self.folder, nobody)]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), 2)

    def test_a_damaged_marker_counts_as_stale_and_other_files_are_ignored(self):
        os.makedirs(self.folder, exist_ok=True)
        sid = "20261020-153012-99"
        self.write(os.path.join(self.folder, cc.marker_name(sid)), "{not json")
        self.write(os.path.join(self.folder, "readme.txt"), "hello")
        found = cc.stale_sessions(self.folder, everybody)
        self.assertEqual([s["id"] for s in found], [sid])

    def test_dismiss_removes_the_markers_keeps_a_log_with_text_and_drops_an_empty_one(self):
        a = self.start(1_800_000_000, pid=1)
        b = self.start(1_800_000_500, pid=2)
        self.write(a["log"], "crash text\n")
        found = cc.stale_sessions(self.folder, nobody)
        cc.dismiss(self.folder, found)
        self.assertEqual(cc.stale_sessions(self.folder, nobody), [])
        self.assertFalse(os.path.exists(a["marker"]))
        self.assertFalse(os.path.exists(b["marker"]))
        self.assertTrue(os.path.exists(a["log"]))
        self.assertFalse(os.path.exists(b["log"]))

    # -- the logs kept
    def test_only_the_newest_five_logs_are_kept(self):
        for i in range(8):
            session = self.start(1_800_000_000 + i * 100, pid=i + 1)
            self.write(session["log"], "x\n")
            cc.end(self.folder, session["id"])
        names = [os.path.basename(p) for _sid, p in cc.logs(self.folder)]
        self.assertEqual(len(names), 8)
        deleted = cc.rotate(self.folder)
        self.assertEqual(len(deleted), 3)
        kept = [os.path.basename(p) for _sid, p in cc.logs(self.folder)]
        self.assertEqual(kept, names[3:])  # the newest five

    def test_rotation_never_deletes_a_protected_log(self):
        sessions = []
        for i in range(7):
            session = self.start(1_800_000_000 + i * 100, pid=i + 1)
            self.write(session["log"], "x\n")
            sessions.append(session)
        oldest = sessions[0]["id"]
        cc.rotate(self.folder, protect={oldest})
        ids = [sid for sid, _p in cc.logs(self.folder)]
        self.assertIn(oldest, ids)
        self.assertEqual(len(ids), 6)  # one more than KEEP: the protected one

    def test_the_last_crash_log_is_the_newest_one_with_text_not_the_running_session(self):
        old = self.start(1_800_000_000, pid=1)
        new = self.start(1_800_000_500, pid=2)
        running = self.start(1_800_001_000, pid=3)
        self.write(old["log"], "old\n")
        self.write(running["log"], "running\n")
        # `new` is empty, `running` is this session
        self.assertEqual(
            cc.last_crash_log(self.folder, exclude=(running["id"],)), (old["id"], old["log"])
        )
        self.write(new["log"], "new\n")
        self.assertEqual(
            cc.last_crash_log(self.folder, exclude=(running["id"],)), (new["id"], new["log"])
        )

    # -- reading it
    def test_the_tail_is_the_last_lines(self):
        path = os.path.join(self.tmp, "log.txt")
        self.write(path, "\n".join("line %d" % i for i in range(1000)))
        rows = cc.tail(path, lines=300).splitlines()
        self.assertEqual(len(rows), 300)
        self.assertEqual(rows[-1], "line 999")
        self.assertEqual(rows[0], "line 700")
        self.assertEqual(cc.tail(path, lines=2), "line 998\nline 999")

    def test_the_tail_of_a_huge_file_reads_only_its_end_and_survives_bad_bytes(self):
        path = os.path.join(self.tmp, "big.txt")
        with open(path, "wb") as handle:
            handle.write(b"a" * 2_000_000 + b"\n\xff\xfe end\n")
        text = cc.tail(path, lines=5)
        self.assertTrue(text.endswith("end"))
        self.assertLess(len(text), 500_000)

    def test_the_tail_of_a_missing_file_is_empty(self):
        self.assertEqual(cc.tail(os.path.join(self.tmp, "nope.txt")), "")

    # -- is it running?
    def test_pid_alive(self):
        self.assertTrue(cc.pid_alive(os.getpid()))
        for junk in (None, "abc", 0, -5, ""):
            self.assertFalse(cc.pid_alive(junk), junk)

    @unittest.skipIf(sys.platform.startswith("win"), "the dead process is found another way")
    def test_pid_alive_is_false_for_a_process_that_ended(self):
        process = subprocess.Popen([sys.executable, "-c", "pass"])
        process.wait()
        self.assertFalse(cc.pid_alive(process.pid))


if __name__ == "__main__":
    unittest.main()
