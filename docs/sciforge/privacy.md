# SciForge and your privacy

Short version: **SciForge has no accounts and no telemetry. It does not send your designs or
anything about you anywhere on its own.** It goes online in exactly two cases that you can see
and control: the update check, and the AI features if you connect an AI service. Everything else
stays on your computer.

This page was written by reading SciForge's code, not from memory (the places in the code are
named so you can check them). If you find a sentence here that is not true, please open an
issue.

## What SciForge sends, and when

| What | When | Where to | What it contains |
|---|---|---|---|
| **Update check** | When SciForge starts (at most once a day), and when you choose Help > Check for Updates. You can switch the start-up check off: Preferences > General > "Check for updates when SciForge starts". | `api.github.com` (GitHub's public list of SciForge's releases) | A plain web request for the list of releases. The only thing it carries besides the address is a `User-Agent` line saying `SciForge/<your version>`. No design, no name, no id. GitHub sees your computer's internet address, as every website does. |
| **Downloading an update** | Only when you click "Update now" | `github.com` (the release's files) | The same kind of plain download request. |
| **The AI chat** | Only when you press Send (or "List" for the model list) in the AI panel's Chat tab, with an AI service you chose and gave your own key for | That service: Anthropic (`api.anthropic.com`), OpenAI (`api.openai.com`) or Google (`generativelanguage.googleapis.com`); or, for a local model, your own computer (Ollama or LM Studio at `localhost`) | Your messages, what the AI asks SciForge about the open design (its bodies, sizes, timeline steps, parameters, sketches, measurements) and the screenshots it takes of your view. Your key goes to that service in the request, as it must. |

That is the complete list for SciForge's own code. There is no analytics, no crash upload, no
"phone home", no advertising, and nothing runs in the background to collect data.

The AI chat's own screen says the same in its note: *"The design's data and the screenshots the
AI takes are sent to that provider. The local option (Ollama or LM Studio on this computer) is
free and private: nothing leaves your computer."* Using an AI service through its API is
billed by that service, separately from any chat subscription you have.

## AI apps (Claude Desktop and others) building in SciForge

This is a different feature from the chat: an AI app you already use (for example Claude
Desktop or Gemini CLI) can be allowed to build designs in SciForge.

- It is **off until you switch it on**: Preferences > AI > "Allow AI apps to control SciForge".
- When it is on, SciForge listens only on your own computer (address `127.0.0.1`, a random
  port). Nothing outside your computer can reach it. A small file in SciForge's settings folder
  (`ai/bridge.json`) holds the port and a random password that the AI app's helper needs. On Linux
  the file can only be read by your account; on Windows it sits in your own user profile.
- The first time an AI app asks for something in each session, SciForge asks you: Allow or Deny.
  Every step the AI makes is one Undo step and is listed in the AI panel's Activity tab.
- "Add an AI" writes a few lines into that AI app's own settings file so it can start SciForge's
  helper. SciForge makes a backup of that file first, and leaves a file alone that it cannot read
  as valid settings.
- What that AI app then does with what it learns about your design is governed by *that app's*
  service and privacy policy, not by SciForge. SciForge cannot see or limit it.

## Where your AI key is kept

You paste your own API key into the AI panel. SciForge keeps it on your computer
(`sciforge/secrets_store.py`):

- **Windows:** encrypted with Windows' own data protection (DPAPI) for your Windows user. The
  file is useless on another account or another computer.
- **Linux:** in the desktop's key store (GNOME Keyring or KWallet) **only if** the Python
  packages `keyring` or `secretstorage` are installed for SciForge's Python, which SciForge's own
  downloads are not set up to include. Otherwise it is a file that only your account can read, but **it is
  not encrypted**. SciForge says so next to the key field when this is the case.
- Keys are never written to SciForge's log, never put in a design file, and never included in a
  problem report. The AI chat's conversation is kept in memory while SciForge runs and is gone
  when you press New chat or close SciForge; SciForge does not save it to disk.
- Remove a key any time: empty the key field and press Save key.

Where this folder is: SciForge > Diagnostics shows "Settings folder" (on Windows under
`%APPDATA%\SciForge`); the keys are in a subfolder called `secrets`.

## Cloud places, NAS, "This computer"

A "place" on the Home tab is just a folder. A cloud place is the folder that your own cloud app
(Dropbox, OneDrive, Google Drive) keeps in sync. **SciForge never talks to those services and
never asks for your sign-in**: it only opens and saves files in the folder, and your cloud app
moves them.

One thing to know: next to your designs, SciForge keeps a small hidden folder named `.sciforge`
with preview pictures (`thumbs`) and, while a design is open, a short note (`locks`) holding
**your computer's name, your user name and the time**, so that another computer can say "open on
LAPTOP since 14:02". If the place is in a cloud folder, your cloud app syncs those files like
any other, so people who share that folder can see them.

## Your designs and settings

Designs are ordinary `.FCStd` files that you save where you choose. The version history, the
list of recent designs and the preview pictures are files on your computer (in the design's
folder and in SciForge's settings folder). Your preferences are in the settings folder too.

## Problem reports and the crash log

If SciForge closes unexpectedly, it leaves a log file on your computer (in the settings folder,
under `crash`). **Nothing is uploaded.** Help > Report a Problem shows you exactly what a report
would contain (SciForge version, Windows or Linux version, graphics card name, recent SciForge
messages, and the crash log if you tick it) with your user name and home folder replaced, and
anything that looks like an API key removed. You can then Save it to a file, Copy it, or press
"Open on GitHub", which opens your **browser** on a pre-filled issue; you read it there and decide
whether to submit. (GitHub needs an account for that; the Save and Copy buttons do not.)
Anything you post on GitHub is public.

## FreeCAD's own parts

SciForge is built on FreeCAD and includes FreeCAD's own Add-on Manager (UTILITIES > ADD-INS >
Add-on Manager, also the "Get Add-Ons" button of Scripts and Add-Ins) and FreeCAD's other
workbenches (UTILITIES > FreeCAD Tools). Those are FreeCAD's
code, not SciForge's. The Add-on Manager downloads its catalogue from the internet when you
open it, and some FreeCAD workbenches can open web pages or download things when you use their
tools. SciForge does not start any of them by itself. FreeCAD's own statement about its data use
is in `PRIVACY_POLICY.md`.

## What SciForge does not do

- It does not require or offer an account, a login or a licence key.
- It does not collect statistics, usage data, error reports or file names.
- It does not upload your designs.
- It does not contact any server at start-up other than the optional update check above.

If this ever changes, this page changes first and the release notes say so.
