<!-- A copy of docs/sciforge/patch-release.md for AI models, made by tools/sciforge/make_ai_docs.py: edit the original, then run the script. -->

# Patch releases: a bug fix out in about half an hour

Most bugs are in SciForge's own Python files, not in the compiled FreeCAD program underneath.
A fix like that does not need the 4-hour build. A **patch release** publishes it as a new
version, for example `0.1.0-beta.2.1`, and every SciForge out there offers **Update now**: a
download of a few MB that installs itself and restarts SciForge. Nobody unzips anything.

A **full release** (the 4-hour build, started by pushing a tag `sciforge-v<version>`) is only
needed when the compiled program changes, or for a big release you want built from scratch.

## What you do

1. Claude fixes the bug on `develop`, sets the new number in `src/Mod/SciForge/VERSION`
   (`0.1.0-beta.2` becomes `0.1.0-beta.2.1`, then `.2`, ...) and writes what was fixed in
   `CHANGELOG.md`. Several fixes can go into one patch.
2. Wait until **Actions > SciForge tests** has a green tick for that commit (about 75
   minutes; Claude says when).
3. On GitHub (the phone app or the website): **Actions > SciForge patch release > Run
   workflow > Run workflow**. Leave "Use workflow from" as it is: the patch is always
   `develop`'s newest commit.
4. About half an hour later the new version is on the Releases page, and SciForge offers it
   (at its next start, or right away with **Help > Check for Updates**).

Untick **publish** for a trial run: everything is built and checked, nothing is published.

## What it does by itself

- **Refuses** (with a red message saying why) when the number in VERSION is already released or
  not newer, when CHANGELOG.md has nothing for it, when the tests are not green on that commit,
  or when the compiled program changed since the last full release (then a full release is
  needed).
- Takes the last full release's Windows portable build and Linux AppImage, puts the new
  SciForge files in, makes the Windows installer from that, and runs the golden models on
  Windows and the start-up, golden and journey tests on Linux.
- Publishes the release (and its tag: no Codespace step), then moves the `Release` branch to
  the commit.

## Who gets what

- **Windows, installed or portable:** Update now (Help > Check for Updates, or the update icon
  at the top right). A few MB, about a minute.
- **Linux AppImage:** an AppImage cannot replace itself; download the new one from the Releases
  page.
- **New people:** the downloads on the patch's page already contain the fix.

## The first time

GitHub only shows the **Run workflow** button for a workflow that is on the repository's main
branch, which is `Release`. The first patch therefore needs `Release` moved to `develop` once
(Claude does that when you say go); after that the button is always there.

## For Claude

`.github/workflows/sciforge-patch-release.yml`; the checks and the base release:
`tools/sciforge/patch_release.py` (unit tests: `SciForgeTests/unit/test_patch_release.py`); the
new module in the old downloads: `tools/sciforge/repack_module.sh`; the notes say "A patch
release" (`make_release_files.py --patch-of`). A push to `develop` that changes these files runs a
trial by itself.
