# Transcript Validator

A small browser tool for manually checking AI transcriptions of voice notes against the original recordings.

It loads a CSV of entries, shows the voice entries one at a time with the matching recording, and lets you correct the transcript in place. For each entry you record a verdict (Accurate / Minor errors / Major errors / Cannot verify), error types and notes. The tool highlights your changes and computes a word error rate (WER). Results export to CSV.

## Input format

**CSV** with at least these columns:

| Column | Used for |
|---|---|
| `UniqueID` | matching each entry to its recording |
| `EntryFormat` | `Voice` entries are shown by default |
| `Content` | the AI transcript (`null` or empty is flagged as a failed transcription) |
| `ParticipantID`, `Timestamp`, `DataType`, `WordCount` | shown as context and used for filtering |

**Audio files** are matched to entries by the `UniqueID` at the end of the file name, e.g.
`XY12345_Journal_1234567890_1-1-2026_1767225600000_AbCdEfGhIj.oga` → `AbCdEfGhIj`.
Any common audio format works. `.oga`/`.ogg` play in Chrome and Firefox; Safari support depends on the macOS version.

## Usage

### Files on your computer
Open `transcript-validator.html` in Chrome or Firefox, click **Load CSV**, then **Audio folder** (or **or audio files** and select them all). Nothing is uploaded: the browser reads the files locally.

### Files on a remote server (SSH)
Stream recordings from a server without copying them to your laptop:

```bash
python3 validator_server.py USER@HOST /remote/path/to/audio --csv /remote/path/to/data.csv
```

`USER@HOST` can be a `Host` alias from `~/.ssh/config`. The script signs in once over SSH, opens the tool at `http://localhost:8765`, and fetches each recording into memory when you play it (nothing is written to disk, nothing is installed on the server, and the page only listens on localhost). Leave `--csv` out to load a local CSV instead. Stop it with Ctrl+C.

Requires Python 3.7+ and `ssh`; no other dependencies.

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Esc` | play/pause from anywhere (rewinds 1 s on pause) |
| `Space` | play/pause |
| `←` / `→` | skip back/forward 3 s |
| `1`–`4` | set verdict |
| `N` / `P` | next/previous entry |
| `E` | edit the transcript |

## Progress and export

Progress autosaves in the browser (per address: the local file, `localhost`, etc. are separate). **Export results** writes a CSV with `UniqueID`, `ParticipantID`, `Timestamp`, `Verdict`, `ErrorTypes`, `WER`, `AI_Transcript`, `Corrected_Transcript`, `Notes` and `ReviewedAt`. **Import results** restores progress from an exported file.

WER is computed at word level, ignoring case and punctuation, with your corrected transcript as the reference.

## Data

This repository contains code only. The `.gitignore` excludes CSV and audio files; do not commit participant data or exported results.
