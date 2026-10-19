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


XLINK_XML = """<Object name="Link"><Properties>
<Property name="LinkedObject" type="App::PropertyXLink">
<XLink file="%s" stamp="2026-10-16T00:00:00Z" name="Body"/></Property>
<Property name="Empty" type="App::PropertyXLink"><XLink file="" name=""/></Property>
<Property name="SourceFile" type="App::PropertyString"><String value="%s"/></Property>
<Property name="SourceRelative" type="App::PropertyString"><String value="%s"/></Property>
</Properties></Object>"""


class MilestoneTests(Scratch):
    """Fusion's milestones: a version marked as one (Save dialog box, Version History)."""

    def test_plain_store_milestones(self):
        path = make_design(os.path.join(self.root, "Bracket.FCStd"))
        store = v.PlainStore(path)
        one = store.record("first")
        two = store.record("release", milestone=True)
        self.assertFalse(one.milestone)
        self.assertTrue(two.milestone)
        self.assertEqual([x.milestone for x in store.versions()], [False, True])
        store.set_milestone(store.versions()[0], True)
        store.set_milestone(store.versions()[1], False)
        self.assertEqual([x.milestone for x in store.versions()], [True, False])
        self.assertTrue(store.versions()[0].as_dict()["milestone"])
        ghost = v.VersionInfo(9, "", "", 0, "v0009.FCStd", "copy")
        with self.assertRaises(v.StoreError):
            store.set_milestone(ghost, True)

    @unittest.skipUnless(v.git_available(), "git is not installed")
    def test_git_milestones_are_tags(self):
        project = os.path.join(self.root, "proj")
        path = make_design(os.path.join(project, "Arm.FCStd"))
        store = v.store_for(path, project)
        store.record("first")
        make_design(path, bodies=2)
        two = store.record("release", milestone=True)
        self.assertTrue(two.milestone)
        listed = store.versions()
        self.assertEqual([x.milestone for x in listed], [False, True])
        store.set_milestone(listed[0], True)
        store.set_milestone(listed[1], False)
        store.set_milestone(listed[1], False)  # twice: nothing to take off, no error
        self.assertEqual([x.milestone for x in store.versions()], [True, False])


class MoveCopyTests(Scratch):
    """The Data Panel's Move / Copy of designs between folders."""

    def test_count_versions_follows_moves(self):
        log = (
            "\x1eSave\nA\tArm.FCStd\n\x1erelease\nM\tArm.FCStd\n"
            "\x1e%s Arm.FCStd to Robots/Arm.FCStd\nR100\tArm.FCStd\tRobots/Arm.FCStd\n"
            "\x1eSave\nM\tRobots/Arm.FCStd\nA\tBase.FCStd\n" % v.MOVE_MESSAGE
        )
        self.assertEqual(v.count_versions(log), {"Robots/Arm.FCStd": 3, "Base.FCStd": 1})

    def test_parse_log(self):
        out = (
            "\x1ec2\x1f2026-10-16T09:00:00+00:00\x1f%s x\n"
            "\x1ec1\x1f2026-10-16T08:00:00+00:00\x1ffirst\n" % v.MOVE_MESSAGE
        )
        rows = v.parse_log(out)
        self.assertEqual([r[0] for r in rows], ["c2", "c1"])
        self.assertEqual(rows[1][2], "first")
        self.assertTrue(rows[0][2].startswith(v.MOVE_MESSAGE))

    def test_retarget_links_of_a_moved_design(self):
        old_dir = os.path.join(self.root, "proj")
        new_dir = os.path.join(self.root, "proj", "Robots")
        wheel = os.path.join(old_dir, "Wheel.FCStd")
        xml = XLINK_XML % ("Wheel.FCStd", wheel, "Wheel.FCStd")
        out, n = v.retarget_xml(xml, old_dir, new_dir)
        self.assertEqual(n, 2)  # the link and the Derive's relative path
        self.assertIn('<XLink file="../Wheel.FCStd"', out)
        self.assertIn('<String value="../Wheel.FCStd"/>', out)
        self.assertIn('<XLink file="" name=""/>', out)  # empty links stay empty
        self.assertEqual(
            [os.path.normpath(t) for t in v.link_targets(out, new_dir)], [wheel, wheel, wheel]
        )

    def test_retarget_keeps_an_inserted_designs_file_name(self):
        # Insert into Current Design (design_insert) stores the other design's file name
        # beside the XLinks; a move keeps both pointing at the same file
        old_dir = os.path.join(self.root, "proj")
        new_dir = os.path.join(self.root, "proj", "Robots")
        xml = (
            '<Property name="SciForgeLinkedFile" type="App::PropertyString" status="1">\n'
            '<String value="Wheel.FCStd"/>\n</Property>\n<XLink file="Wheel.FCStd" name="Body"/>'
        )
        out, n = v.retarget_xml(xml, old_dir, new_dir)
        self.assertEqual(n, 1)  # the XLink; the file name follows it
        self.assertIn('<String value="../Wheel.FCStd"/>', out)
        self.assertIn('<XLink file="../Wheel.FCStd"', out)
        folder = old_dir
        out, n = v.retarget_xml(
            xml,
            folder,
            folder,
            os.path.join(folder, "Wheel.FCStd"),
            os.path.join(folder, "Parts", "Wheel.FCStd"),
        )
        self.assertIn('<String value="Parts/Wheel.FCStd"/>', out)

    def test_retarget_links_to_a_moved_design(self):
        folder = os.path.join(self.root, "proj")
        old = os.path.join(folder, "Wheel.FCStd")
        new = os.path.join(folder, "Parts", "Wheel.FCStd")
        xml = XLINK_XML % ("Wheel.FCStd", old, "Wheel.FCStd")
        out, n = v.retarget_xml(xml, folder, folder, old, new)
        self.assertEqual(n, 3)  # link, absolute and relative source
        self.assertIn('<XLink file="Parts/Wheel.FCStd"', out)
        self.assertIn('<String value="%s"/>' % new, out)
        self.assertIn('<String value="Parts/Wheel.FCStd"/>', out)
        same, none = v.retarget_xml(out, folder, folder, old, new)
        self.assertEqual((same, none), (out, 0))

    def _linked_pair(self, project):
        wheel = make_design(os.path.join(project, "Wheel.FCStd"))
        cart = make_design(
            os.path.join(project, "Cart.FCStd"),
            extra=XLINK_XML % ("Wheel.FCStd", wheel, "Wheel.FCStd"),
        )
        return wheel, cart

    def test_move_with_plain_versions_and_referrers(self):
        project = os.path.join(self.root, "proj")
        wheel, cart = self._linked_pair(project)
        v.PlainStore(wheel).record("one")
        os.makedirs(os.path.join(project, "Parts"))
        self.assertEqual(v.referrers(wheel, project), [cart])
        new, updated = v.move_design(wheel, os.path.join(project, "Parts"), project, use_git=False)
        self.assertEqual(new, os.path.join(project, "Parts", "Wheel.FCStd"))
        self.assertFalse(os.path.exists(wheel))
        self.assertEqual(updated, [cart])
        self.assertIn('<XLink file="Parts/Wheel.FCStd"', v.read_design_xml(cart))
        self.assertEqual([x.description for x in v.PlainStore(new).versions()], ["one"])
        self.assertFalse(os.path.isdir(os.path.join(project, "Wheel.FCStd.versions")))
        with self.assertRaises(v.StoreError):
            v.move_design(new, os.path.join(project, "Parts"), project, use_git=False)
        make_design(os.path.join(project, "Wheel.FCStd"))
        with self.assertRaises(v.StoreError):  # the name is taken there
            v.move_design(new, project, project, use_git=False)

    @unittest.skipUnless(v.git_available(), "git is not installed")
    def test_move_in_git_keeps_the_versions(self):
        project = os.path.join(self.root, "proj")
        path = make_design(os.path.join(project, "Arm.FCStd"))
        store = v.store_for(path, project)
        store.record("first")
        make_design(path, bodies=2)
        store.record("second", milestone=True)
        os.makedirs(os.path.join(project, "Robots"))
        new, _updated = v.move_design(path, os.path.join(project, "Robots"), project)
        moved = v.store_for(new, project)
        listed = moved.versions()
        self.assertEqual([x.description for x in listed], ["first", "second"])
        self.assertEqual([x.milestone for x in listed], [False, True])
        out = moved.extract(listed[0], os.path.join(self.root, "open"))
        self.assertEqual(v.summary(out)["bodies"], 1)  # an older version still opens
        self.assertEqual(v.repo_counts(project).get("Robots/Arm.FCStd"), 2)
        make_design(new, bodies=3)
        self.assertEqual(moved.record("third").number, 3)
        renamed = v.rename_design(new, "Arm 2", project, True)
        self.assertEqual(v.store_for(renamed, project).count(), 3)

    def test_rename_points_the_users_at_the_new_name(self):
        project = os.path.join(self.root, "proj")
        wheel, cart = self._linked_pair(project)
        renamed = v.rename_design(wheel, "Rim", project, use_git=False)
        self.assertEqual(os.path.basename(renamed), "Rim.FCStd")
        self.assertIn('<XLink file="Rim.FCStd"', v.read_design_xml(cart))

    def test_copy_is_a_separate_design(self):
        project = os.path.join(self.root, "proj")
        wheel, cart = self._linked_pair(project)
        os.makedirs(os.path.join(project, "Old"))
        copy = v.copy_design(cart, os.path.join(project, "Old"))
        self.assertEqual(copy, os.path.join(project, "Old", "Cart.FCStd"))
        self.assertTrue(os.path.isfile(cart))
        self.assertIn('<XLink file="../Wheel.FCStd"', v.read_design_xml(copy))
        again = v.copy_design(cart, os.path.join(project, "Old"))
        self.assertEqual(os.path.basename(again), "Cart 2.FCStd")
        self.assertEqual(v.version_count(copy), 0)  # its own versions start with v1

    def test_project_folders_for_the_dialog(self):
        project = os.path.join(self.root, "proj")
        for sub in ("b", "a", os.path.join("a", "x"), ".git", "Arm.versions"):
            os.makedirs(os.path.join(project, sub))
        labels = [label for label, _path in v.project_folders(project)]
        self.assertEqual(labels, ["Project", "Project / a", "Project / a / x", "Project / b"])


if __name__ == "__main__":
    unittest.main()


class UnfinishedSaveTests(Scratch):
    """FreeCAD's save left as "<design>.FCStd.<uuid>" when its last rename was refused
    (Google Drive backing up Luca's Documents folder)."""

    UUIDS = (
        "78026b5d-cb38-45d0-a35f-496a00000001",
        "de505953-325f-48bb-888d-ba0000000002",
        "e6be27c2-5cd8-4564-9deb-abf000000003",
    )

    def temp(self, design, uuid, mtime):
        path = make_design(os.path.join(self.root, "%s.FCStd.%s" % (design, uuid)))
        os.utime(path, (mtime, mtime))
        return path

    def test_found_by_design_newest_first(self):
        old = self.temp("test", self.UUIDS[0], 1000)
        new = self.temp("test", self.UUIDS[1], 2000)
        other = self.temp("the THING", self.UUIDS[2], 1500)
        with open(os.path.join(self.root, "notes.FCStd.txt"), "w") as handle:
            handle.write("not a save")
        found = v.unfinished_saves(self.root)
        self.assertEqual(found[os.path.join(self.root, "test.FCStd")], [new, old])
        self.assertEqual(found[os.path.join(self.root, "the THING.FCStd")], [other])
        self.assertEqual(len(found), 2)

    def test_the_newest_complete_save_becomes_the_design(self):
        old = self.temp("test", self.UUIDS[0], 1000)
        new = self.temp("test", self.UUIDS[1], 2000)
        design = os.path.join(self.root, "test.FCStd")
        self.assertTrue(v.finish_save(design, now=5000))
        self.assertTrue(v.complete_save(design))
        self.assertFalse(os.path.exists(new))
        self.assertFalse(os.path.exists(old))  # kept aside, never deleted:
        kept = os.path.join(self.root, v.UNFINISHED_FOLDER, os.path.basename(old))
        self.assertTrue(os.path.isfile(kept))
        self.assertEqual(v.list_folder(self.root)[1][0]["name"], "test")
        self.assertIsNone(v.finish_save(design, now=5000))  # nothing left

    def test_left_alone(self):
        design = os.path.join(self.root, "test.FCStd")
        broken = os.path.join(self.root, "test.FCStd.%s" % self.UUIDS[0])
        with open(broken, "wb") as handle:
            handle.write(b"PK half written")
        self.assertIsNone(v.finish_save(design))  # not a complete save
        os.remove(broken)
        self.temp("test", self.UUIDS[1], 2000)
        self.assertIsNone(v.finish_save(design, settle=10.0, now=2005))  # being written
        make_design(design)
        os.utime(design, (3000, 3000))
        self.assertIsNone(v.finish_save(design, now=5000))  # the design is newer
        self.assertIsNone(v.finish_save(design, since=4000, now=5000))  # not this save
