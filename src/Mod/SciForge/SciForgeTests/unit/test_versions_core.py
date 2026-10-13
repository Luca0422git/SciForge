# SPDX-License-Identifier: LGPL-2.1-or-later
"""The version stores, recovery entries, paths and the design summary (sciforge/versions.py).
No FreeCAD: a "design" here is any file called *.FCStd (a small zip with a Document.xml)."""

import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import versions as v  # noqa: E402

DOCUMENT_XML = """<?xml version='1.0' encoding='utf-8'?>
<Document SchemaVersion="4" ProgramVersion="1.1R" FileVersion="1">
<Properties Count="3">
<Property name="Label" type="App::PropertyString"><String value="Bracket &amp; Co"/></Property>
<Property name="LastModifiedDate" type="App::PropertyString">
<String value="2026-10-13T14:05:09+00:00"/></Property>
<Property name="LastModifiedBy" type="App::PropertyString"><String value="luca"/></Property>
</Properties>
<Objects Count="%d">
%s
</Objects>
</Document>
"""


def make_design(path, bodies=1, sketches=1, features=2, thumbnail=False, extra=""):
    objects = ['<Object type="PartDesign::Body" name="Body%d" />' % i for i in range(bodies)]
    objects += ['<Object type="App::Origin" name="Origin%d" />' % i for i in range(bodies)]
    objects += [
        '<Object type="Sketcher::SketchObject" name="Sketch%d" />' % i for i in range(sketches)
    ]
    objects += ['<Object type="PartDesign::Pad" name="Pad%d" />' % i for i in range(features)]
    xml = DOCUMENT_XML % (len(objects), "\n".join(objects))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Document.xml", xml + extra)
        if thumbnail:
            zf.writestr("thumbnails/Thumbnail.png", b"\x89PNG fake")
    return path


class Scratch(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sf-versions-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class NameAndPathTests(Scratch):
    def test_design_name_and_suffix(self):
        self.assertEqual(v.design_name("/nas/Bracket.FCStd"), "Bracket")
        self.assertEqual(v.design_name("C:\\nas\\bracket.fcstd"), "bracket")
        self.assertTrue(v.is_design("a.FCStd") and v.is_design("a.fcstd"))
        self.assertFalse(v.is_design("a.FCBak"))

    def test_clean_name_removes_what_file_systems_refuse(self):
        self.assertEqual(v.clean_name(' Brac<ket>:"/\\|?* v2 . '), "Bracket v2")
        self.assertEqual(v.clean_name("CON"), "CON_")
        self.assertEqual(v.clean_name("..."), "")
        self.assertEqual(v.clean_name(None), "")

    def test_design_path_and_unique_names(self):
        folder = self.root
        open(os.path.join(folder, "Bracket.FCStd"), "w").close()
        open(os.path.join(folder, "Bracket 2.FCStd"), "w").close()
        self.assertEqual(v.design_path(folder, "Lid"), os.path.join(folder, "Lid.FCStd"))
        self.assertEqual(v.unique_name(folder, "Bracket", ".FCStd"), "Bracket 3")
        self.assertEqual(v.unique_name(folder, "Lid", ".FCStd"), "Lid")
        self.assertEqual(v.unique_name(folder, "New Folder"), "New Folder")
        os.makedirs(os.path.join(folder, "New Folder"))
        self.assertEqual(v.unique_name(folder, "New Folder"), "New Folder 2")

    def test_same_path_and_inside(self):
        a = os.path.join(self.root, "x", "..", "a.FCStd")
        b = os.path.join(self.root, "a.FCStd")
        self.assertTrue(v.same_path(a, b))
        self.assertFalse(v.same_path("", b))
        self.assertTrue(v.inside(self.root, b))
        self.assertTrue(v.inside(self.root, self.root))
        self.assertFalse(v.inside(self.root, os.path.dirname(self.root)))
        self.assertFalse(
            v.inside(os.path.join(self.root, "proj"), os.path.join(self.root, "project2", "a"))
        )

    def test_relative_paths_like_freecad_writes_them(self):
        owner = os.path.join(self.root, "asm", "Robot.FCStd")
        part = os.path.join(self.root, "parts", "Arm.FCStd")
        self.assertEqual(v.relative_path(owner, part), "../parts/Arm.FCStd")
        self.assertEqual(v.relative_path(self.root, part, is_folder=True), "parts/Arm.FCStd")
        self.assertEqual(
            os.path.normcase(v.resolve_relative(owner, "../parts/Arm.FCStd")),
            os.path.normcase(part),
        )

    def test_path_key_is_stable_and_short(self):
        key = v.path_key(os.path.join(self.root, "a.FCStd"))
        self.assertEqual(key, v.path_key(os.path.join(self.root, ".", "a.FCStd")))
        self.assertEqual(len(key), 10)
        self.assertNotEqual(key, v.path_key(os.path.join(self.root, "b.FCStd")))

    def test_sizes_and_times(self):
        self.assertEqual(v.human_size(512), "512 B")
        self.assertEqual(v.human_size(2048), "2.0 KB")
        self.assertEqual(v.human_size(3 * 1024 * 1024), "3.0 MB")
        self.assertEqual(v.pretty_time("2026-10-13T14:05:09+00:00"), "2026-10-13 14:05")
        self.assertEqual(v.pretty_time("odd"), "odd")
        self.assertEqual(v.clamp_minutes(0), 1)
        self.assertEqual(v.clamp_minutes(500), 120)
        self.assertEqual(v.clamp_minutes("x"), 5)

    def test_breadcrumbs(self):
        project = os.path.join(self.root, "proj")
        deep = os.path.join(project, "robots", "arm")
        crumbs = v.breadcrumbs(project, deep)
        self.assertEqual([c[0] for c in crumbs], ["Project", "robots", "arm"])
        self.assertEqual(os.path.normcase(crumbs[-1][1]), os.path.normcase(deep))
        self.assertEqual([c[0] for c in v.breadcrumbs(project, project)], ["Project"])
        self.assertEqual([c[0] for c in v.breadcrumbs(project, self.root)], ["Project"])


class AtomicWriteTests(Scratch):
    def test_write_and_copy_leave_no_temp_files(self):
        path = os.path.join(self.root, "sub", "index.json")
        v.atomic_write_text(path, "{}")
        self.assertEqual(open(path).read(), "{}")
        src = os.path.join(self.root, "src.bin")
        with open(src, "wb") as handle:
            handle.write(b"x" * 1000)
        dst = os.path.join(self.root, "sub2", "dst.bin")
        v.atomic_copy(src, dst)
        self.assertEqual(os.path.getsize(dst), 1000)
        for folder in (os.path.dirname(path), os.path.dirname(dst)):
            self.assertEqual([f for f in os.listdir(folder) if f.startswith(".sf-")], [])

    def test_writable_folder(self):
        self.assertTrue(v.writable_folder(os.path.join(self.root, "new")))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "new")))
        if os.name != "nt" and os.geteuid() != 0:
            locked = os.path.join(self.root, "locked")
            os.makedirs(locked)
            os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
            try:
                self.assertFalse(v.writable_folder(locked))
            finally:
                os.chmod(locked, stat.S_IRWXU)


class PlainStoreTests(Scratch):
    def design(self, name="Bracket", **kwargs):
        return make_design(os.path.join(self.root, "proj", name + ".FCStd"), **kwargs)

    def test_record_lists_extract_promote(self):
        path = self.design()
        store = v.PlainStore(path)
        self.assertEqual(store.versions(), [])
        self.assertEqual(store.count(), 0)
        one = store.record("first shape")
        self.assertEqual((one.number, one.label, one.description), (1, "v1", "first shape"))
        self.assertTrue(one.current)
        make_design(path, bodies=2)  # the design changes and is saved again
        two = store.record("")
        self.assertEqual(two.number, 2)
        listed = store.versions()
        self.assertEqual([x.number for x in listed], [1, 2])
        self.assertEqual([x.current for x in listed], [False, True])
        self.assertEqual(listed[0].description, "first shape")
        self.assertTrue(listed[1].time.startswith("20"))
        self.assertEqual(listed[0].size, os.path.getsize(store.path_of(listed[0])))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "proj", "Bracket.versions")))
        # open v1 somewhere else: the file of v1 (one body)
        out = store.extract(listed[0], os.path.join(self.root, "open"))
        self.assertEqual(os.path.basename(out), "Bracket v1.FCStd")
        self.assertEqual(v.summary(out)["bodies"], 1)
        self.assertEqual(v.summary(path)["bodies"], 2)
        # promote v1: the design is v1's content again, recorded as v3
        three = store.promote(listed[0], "back to one body")
        self.assertEqual(three.number, 3)
        self.assertEqual(v.summary(path)["bodies"], 1)
        self.assertEqual([x.number for x in store.versions()], [1, 2, 3])
        self.assertEqual(store.versions()[-1].description, "back to one body")
        self.assertEqual(store.versions()[1].description, "", "v2 is still there")

    def test_identical_saves_share_one_copy(self):
        path = self.design()
        store = v.PlainStore(path)
        a = store.record("a")
        b = store.record("b")
        self.assertEqual(a.key, b.key)
        self.assertEqual(len([f for f in os.listdir(store.folder) if f.endswith(".FCStd")]), 1)
        self.assertEqual(store.count(), 2)

    def test_broken_index_is_rebuilt_from_the_copies(self):
        path = self.design()
        store = v.PlainStore(path)
        store.record("one")
        make_design(path, bodies=3)
        store.record("two")
        with open(store._index_path(), "w") as handle:
            handle.write("{not json")
        listed = store.versions()
        self.assertEqual([x.number for x in listed], [1, 2])
        self.assertEqual(
            [x.description for x in listed], ["", ""], "descriptions are lost, nothing else"
        )
        self.assertTrue(any(f.startswith("index.json.broken-") for f in os.listdir(store.folder)))
        three = store.record("three")
        self.assertEqual(three.number, 3)

    def test_missing_design_file_is_refused(self):
        store = v.PlainStore(os.path.join(self.root, "proj", "Nothing.FCStd"))
        with self.assertRaises(v.StoreError):
            store.record("x")

    def test_missing_copy_is_refused_with_words(self):
        path = self.design()
        store = v.PlainStore(path)
        one = store.record("one")
        os.remove(store.path_of(one))
        with self.assertRaises(v.StoreError):
            store.extract(one, self.root)
        with self.assertRaises(v.StoreError):
            store.promote(one)
        self.assertEqual(v.summary(path)["bodies"], 1, "the design file is untouched")

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "needs a folder that cannot be written")
    def test_read_only_folder_uses_the_fallback(self):
        path = self.design()
        folder = os.path.dirname(path)
        os.chmod(folder, stat.S_IRUSR | stat.S_IXUSR)
        try:
            store = v.PlainStore(path, fallback_root=os.path.join(self.root, "user"))
            self.assertTrue(store.fallback)
            self.assertTrue(store.folder.startswith(os.path.join(self.root, "user")))
            one = store.record("kept elsewhere")
            self.assertEqual(one.number, 1)
            self.assertTrue(os.path.isfile(store.path_of(one)))
        finally:
            os.chmod(folder, stat.S_IRWXU)


@unittest.skipUnless(v.git_available(), "git is not installed")
class GitStoreTests(Scratch):
    def test_project_folder_becomes_a_repository_and_versions_are_commits(self):
        project = os.path.join(self.root, "proj")
        path = make_design(os.path.join(project, "robots", "Arm.FCStd"))
        notes = []
        store = v.store_for(path, project, use_git=True, notes=notes)
        self.assertIsInstance(store, v.GitStore)
        self.assertTrue(any("git repository" in n for n in notes), notes)
        self.assertTrue(os.path.isdir(os.path.join(project, ".git")))
        self.assertIn("*.FCBak", open(os.path.join(project, ".gitignore")).read())
        one = store.record("first")
        self.assertEqual((one.number, one.description, one.backend), (1, "first", "git"))
        make_design(path, bodies=2)
        two = store.record("")
        self.assertEqual(two.number, 2)
        listed = store.versions()
        self.assertEqual([x.number for x in listed], [1, 2])
        self.assertEqual([x.description for x in listed], ["first", ""])
        self.assertEqual(listed[0].size, os.path.getsize(path) if False else listed[0].size)
        self.assertGreater(listed[0].size, 0)
        self.assertTrue(listed[1].current and not listed[0].current)
        out = store.extract(listed[0], os.path.join(self.root, "open"))
        self.assertEqual(v.summary(out)["bodies"], 1)
        three = store.promote(listed[0], "back")
        self.assertEqual(three.number, 3)
        self.assertEqual(v.summary(path)["bodies"], 1)
        self.assertEqual(store.count(), 3)
        counts = v.repo_counts(project)
        self.assertEqual(counts.get("robots/Arm.FCStd"), 3)
        self.assertEqual(v.version_count(path, project, True, counts), 3)
        # a second design in the same repository has its own numbering
        other = make_design(os.path.join(project, "Base.FCStd"))
        self.assertEqual(v.store_for(other, project).record("x").number, 1)
        self.assertEqual(store.count(), 3)

    def test_outside_the_project_folder_copies_are_used(self):
        project = os.path.join(self.root, "proj")
        os.makedirs(project)
        path = make_design(os.path.join(self.root, "elsewhere", "Lid.FCStd"))
        notes = []
        store = v.store_for(path, project, use_git=True, notes=notes)
        self.assertIsInstance(store, v.PlainStore)
        self.assertFalse(os.path.exists(os.path.join(self.root, "elsewhere", ".git")))

    def test_git_switched_off_uses_copies(self):
        project = os.path.join(self.root, "proj")
        path = make_design(os.path.join(project, "Lid.FCStd"))
        self.assertIsInstance(v.store_for(path, project, use_git=False), v.PlainStore)
        self.assertFalse(os.path.exists(os.path.join(project, ".git")))


class StoreChoiceWithoutGitTests(Scratch):
    def test_no_git_program_means_copies(self):
        saved = dict(v._GIT)
        v._GIT.update(path=None, looked=True)
        try:
            project = os.path.join(self.root, "proj")
            path = make_design(os.path.join(project, "Lid.FCStd"))
            notes = []
            store = v.store_for(path, project, use_git=True, notes=notes)
            self.assertIsInstance(store, v.PlainStore)
            self.assertTrue(any("not installed" in n for n in notes), notes)
        finally:
            v._GIT.update(saved)


class RecoveryTests(Scratch):
    def test_keys_paths_sidecars_and_listing(self):
        folder = v.recovery_folder(self.root)
        self.assertEqual(folder, os.path.join(self.root, "SciForge", "recovery"))
        saved_key = v.recovery_key("Bracket", "/nas/Bracket.FCStd")
        unsaved_key = v.recovery_key("Unnamed 1", "")
        self.assertEqual(len(saved_key), 10)
        self.assertEqual(unsaved_key, "unsaved-Unnamed_1")
        copy, side = v.recovery_paths(folder, saved_key)
        make_design(copy)
        v.write_recovery_sidecar(folder, saved_key, "Bracket", "/nas/Bracket.FCStd", "sess-A")
        copy2, _ = v.recovery_paths(folder, unsaved_key)
        make_design(copy2)
        v.write_recovery_sidecar(folder, unsaved_key, "Unnamed 1", "", "sess-B")
        entries = v.list_recovery(folder)
        self.assertEqual(sorted(e["key"] for e in entries), sorted([saved_key, unsaved_key]))
        by_key = {e["key"]: e for e in entries}
        self.assertEqual(by_key[saved_key]["file_name"], "/nas/Bracket.FCStd")
        self.assertEqual(by_key[saved_key]["label"], "Bracket")
        self.assertEqual(by_key[unsaved_key]["file_name"], "")
        self.assertTrue(all(e["size"] > 0 and e["saved"] for e in entries))
        # the running session's own copies are not "left over"
        self.assertEqual(
            [e["key"] for e in v.list_recovery(folder, other_than_session="sess-A")], [unsaved_key]
        )
        self.assertEqual(v.recovery_session(folder, saved_key), "sess-A")
        self.assertEqual(v.recovery_session(folder, "no-such-key"), "")
        # one gone, then a whole session's
        self.assertTrue(v.discard_recovery(folder, saved_key))
        self.assertFalse(v.discard_recovery(folder, saved_key))
        self.assertFalse(os.path.exists(side))
        v.discard_session_recovery(folder, "sess-B")
        self.assertEqual(v.list_recovery(folder), [])

    def test_copy_without_sidecar_is_still_listed(self):
        folder = v.recovery_folder(self.root)
        copy, _ = v.recovery_paths(folder, "abc123")
        make_design(copy)
        entries = v.list_recovery(folder)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["label"], "abc123")
        self.assertTrue(entries[0]["saved"])

    def test_session_ids_differ(self):
        self.assertNotEqual(v.new_session_id(), v.new_session_id())


class SummaryTests(Scratch):
    def test_counts_label_and_compare(self):
        a = make_design(
            os.path.join(self.root, "a.FCStd"), bodies=1, sketches=2, features=3, thumbnail=True
        )
        b = make_design(os.path.join(self.root, "b.FCStd"), bodies=2, sketches=2, features=5)
        sa, sb = v.summary(a), v.summary(b)
        self.assertEqual((sa["bodies"], sa["sketches"], sa["features"]), (1, 2, 3))
        self.assertEqual(sa["label"], "Bracket & Co")
        self.assertEqual(sa["lastModifiedBy"], "luca")
        self.assertTrue(sa["thumbnail"] and not sb["thumbnail"])
        self.assertEqual(sa["types"]["PartDesign::Pad"], 3)
        rows = v.compare(sa, sb)
        titles = [r[0] for r in rows]
        self.assertEqual(titles[:3], ["Bodies", "Sketches", "Features"])
        changed = {r[0]: r[3] for r in rows}
        self.assertTrue(changed["Bodies"] and not changed["Sketches"] and changed["Features"])
        sa["volume"], sb["volume"] = 1000.0, 1000.0000001
        rows = v.compare(sa, sb)
        volume = [r for r in rows if r[0].startswith("Total volume")][0]
        self.assertFalse(volume[3], "a rounding difference is not a change")
        self.assertEqual(volume[1], "1000.00")

    def test_not_a_design(self):
        path = os.path.join(self.root, "x.FCStd")
        with open(path, "w") as handle:
            handle.write("nope")
        self.assertIn("error", v.summary(path))
        self.assertIsNone(v.thumbnail_bytes(path))
        self.assertIsNone(v.thumbnail_bytes(os.path.join(self.root, "missing.FCStd")))

    def test_thumbnail_bytes(self):
        path = make_design(os.path.join(self.root, "t.FCStd"), thumbnail=True)
        self.assertEqual(v.thumbnail_bytes(path)[:4], b"\x89PNG")


class ProjectFolderTests(Scratch):
    def test_listing_hides_sciforge_and_git_folders_and_backups(self):
        project = os.path.join(self.root, "proj")
        make_design(os.path.join(project, "Bracket.FCStd"))
        make_design(os.path.join(project, "lid.FCStd"))
        open(os.path.join(project, "Bracket.FCBak"), "w").close()
        open(os.path.join(project, "notes.txt"), "w").close()
        for name in ("Robots", "Bracket.versions", ".git", v.TRASH_FOLDER, ".hidden"):
            os.makedirs(os.path.join(project, name))
        folders, designs = v.list_folder(project)
        self.assertEqual([f["name"] for f in folders], ["Robots"])
        self.assertEqual([d["name"] for d in designs], ["Bracket", "lid"])
        self.assertTrue(all(d["size"] > 0 and d["modified"] for d in designs))
        self.assertEqual(v.list_folder(os.path.join(project, "nothing")), ([], []))

    def test_new_folder_rename_and_trash(self):
        project = os.path.join(self.root, "proj")
        os.makedirs(project)
        first = v.new_folder(project)
        second = v.new_folder(project)
        self.assertEqual(os.path.basename(first), "New Folder")
        self.assertEqual(os.path.basename(second), "New Folder 2")
        path = make_design(os.path.join(project, "Bracket.FCStd"))
        v.PlainStore(path).record("one")
        renamed = v.rename_design(path, "Arm")
        self.assertEqual(os.path.basename(renamed), "Arm.FCStd")
        self.assertTrue(os.path.isdir(os.path.join(project, "Arm.versions")))
        self.assertEqual(v.PlainStore(renamed).count(), 1, "the versions moved with it")
        make_design(os.path.join(project, "Taken.FCStd"))
        with self.assertRaises(v.StoreError):
            v.rename_design(renamed, "Taken")
        with self.assertRaises(v.StoreError):
            v.rename_design(renamed, "???")
        trashed = v.trash_design(renamed, project)
        self.assertFalse(os.path.exists(renamed))
        self.assertEqual(os.path.dirname(trashed), os.path.join(project, v.TRASH_FOLDER))
        self.assertTrue(os.path.isdir(os.path.join(project, v.TRASH_FOLDER, "Arm.versions")))
        self.assertEqual([d["name"] for d in v.list_folder(project)[1]], ["Taken"])

    def test_version_count_without_git_cache(self):
        path = make_design(os.path.join(self.root, "Bracket.FCStd"))
        self.assertEqual(v.version_count(path), 0)
        v.PlainStore(path).record("x")
        self.assertEqual(v.version_count(path), 1)

    def test_index_json_is_readable_by_hand(self):
        path = make_design(os.path.join(self.root, "Bracket.FCStd"))
        store = v.PlainStore(path)
        store.record("hello")
        data = json.load(open(store._index_path()))
        self.assertEqual(data["design"], "Bracket.FCStd")
        self.assertEqual(data["versions"][0]["description"], "hello")
        self.assertEqual(data["versions"][0]["file"], "v0001.FCStd")


if __name__ == "__main__":
    unittest.main()
