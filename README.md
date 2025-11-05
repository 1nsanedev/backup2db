# backup2db

CLI helper to map iOS real filesystem paths and bundle identifiers to the actual file path inside a local iTunes / idevicebackup2 backup.

This solves the *"ok I know the path (/var/mobile/Library/SMS/sms.db) but where in Manifest.db / SHA1 bucket is that file actually stored"* problem.

---

## Features

* validate the backup (checks minimum iOS version 11.0)
* lookup a **single iOS path** → return backup fileID path on disk
* lookup **all files for a bundle identifier** (com.apple.MobileSMS etc)

---

## Requirements

* Python 3.10+
* a LOCAL iOS backup folder (Finder / iTunes / `idevicebackup2 backup`)

---

## Usage

### lookup single path

```bash
python3 backup2db.py \
  --backup-path /path/to/backup \
  --device-path "/var/mobile/Library/SMS/sms.db"
```

### lookup bundle files

```bash
python3 backup2db.py \
  --backup-path /path/to/backup \
  --bundle-paths com.apple.MobileSMS
```

---

## notes

* this does **NOT** decrypt/parse file contents
* this only maps lookup → file on disk

---

## MIT license

see header in script

