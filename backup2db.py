#!/usr/bin/env python3

####################################################
# MIT License
#
# Copyright (c) 2025 1nsane_dev
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
####################################################


import os
import plistlib
import sqlite3

from argparse import ArgumentParser
from dataclasses import dataclass

####################################################
# iOS Version
#################################################### 

@dataclass(frozen=True)
class iOSVersion:
    major: int
    minor: int
    bugfix: int

    def __init__(self, major, minor:int=0, bugfix:int=0):
        if isinstance(major, str):
            parts = major.split(".")
            object.__setattr__(self, "major", int(parts[0]))
            object.__setattr__(self, "minor", int(parts[1]) if len(parts)>1 else 0)
            object.__setattr__(self, "bugfix", int(parts[2]) if len(parts)>2 else 0)

    def __eq__(self, other: "iOSVersion") -> bool:
        if not isinstance(other, iOSVersion):
            return NotImplemented
        return (self.major, self.minor, self.bugfix) == (other.major, other.minor, other.bugfix)

    def __lt__(self, other: "iOSVersion") -> bool:
        if not isinstance(other, iOSVersion):
            return NotImplemented
        return (self.major, self.minor, self.bugfix) < (other.major, other.minor, other.bugfix)

    def __le__(self, other: "iOSVersion") -> bool:
        return self.__lt__(other) or self.__eq__(other)

    def __gt__(self, other: "iOSVersion") -> bool:
        if not isinstance(other, iOSVersion):
            return NotImplemented
        return (self.major, self.minor, self.bugfix) > (other.major, other.minor, other.bugfix)

    def __ge__(self, other: "iOSVersion") -> bool:
        return self.__gt__(other) or self.__eq__(other)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.bugfix}"

TARGET_BACKUP_INFO_KEY = "Product Version"
TARGET_BACKUP_MIN_VER = iOSVersion("11.0")

def is_backup_compatible(backup_dir) -> tuple[bool, iOSVersion|None]:
    """
    Make sure the provided backup is supported.
    """
    backup_info = os.path.abspath(os.path.join(backup_dir, "Info.plist"))

    if not os.path.exists(backup_info):
        print(f"[!] Info.plist: not found in {backup_dir}")
        return False, None

    try:
        with open(backup_info, "rb") as bifp:
            info = plistlib.loads(bifp.read())
    except Exception as e:
        print(f"[!] Info.plist: {e}")
        return False, None

    target_version = iOSVersion(
            info.get(TARGET_BACKUP_INFO_KEY)
    )
    return (
        TARGET_BACKUP_MIN_VER <= target_version
    ), target_version

####################################################
# Backup 2 DB 
#################################################### 

def find_ios_backup_file(backup_dir, ios_path) -> str | None:
    """
    Find the backup file corresponding to a given iOS filesystem path.
    """

    SEARCH_QUERY = """
        SELECT fileID
        FROM Files
        WHERE relativePath = ? OR domain || '-' || relativePath = ?
    """

    manifest_db = os.path.abspath(os.path.join(backup_dir, "Manifest.db"))

    if not os.path.exists(manifest_db):
        print(f"[!] Manifest.db not found in {backup_dir}")
        return None

    conn = sqlite3.connect(manifest_db)
    cur = conn.cursor()

    try:
        cur.execute(SEARCH_QUERY, (ios_path, ios_path))
    except sqlite3.OperationalError:
        print("[!] Could not query Manifest.db — is it a valid iTunes backup?")
        conn.close()
        return None

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    file_id = row[0]
    subdir = file_id[:2]
    file_path = os.path.join(backup_dir, subdir, file_id)

    if os.path.exists(file_path):
        return file_path
    else:
        print(f"[!] Expected file not found at {file_path}")
        return None


def get_app_folders_from_backup(backup_dir, bundle_identifier):
    """
    Get the folders related to an installed app in an iOS backup created with idevicebackup2,
    combining info from both the Manifest.plist and Manifest.db.
    """

    SEARCH_QUERY = """
        SELECT fileID, relativePath
        FROM Files
        WHERE domain = ?;
    """

    manifest_db = os.path.abspath(os.path.join(backup_dir, "Manifest.db"))

    if not os.path.exists(manifest_db):
        print(f"[!] Manifest.db not found in {backup_dir}")
        return None

    conn = sqlite3.connect(manifest_db)
    cur = conn.cursor()

    cur.execute(SEARCH_QUERY, (bundle_identifier,))
    rows = cur.fetchall()

    # in manifest.db:
    #   SMS ==> com.apple.MobileSMS
    #   Facebook ==> AppDomain-com.facebook.Facebook
    #
    # user can pass either
    # so try exact domain first;
    # if not found, prefix with AppDomain-

    if not rows:
        prefixed = f"AppDomain-{bundle_identifier}"
        cur.execute(SEARCH_QUERY, (prefixed,))
        rows = cur.fetchall()

    if not rows:
        print(f"[!] No files found for {bundle_identifier}")
        conn.close()
        return None

    backup_paths = []
    for file_id, rel_path in rows:
        # on disk each file is stored under SHA1 first 2 chars dir
        f = os.path.join(backup_dir, file_id[:2], file_id)
        backup_paths.append((f, rel_path))

    conn.close()
    return backup_paths


####################################################
# Main logic
#################################################### 

def main():
    ap = ArgumentParser()
    ap.add_argument(
        "-d","--device-path",
        default=None,
        dest="path",
        metavar="PATH",
        type=str,
        help=(
            "Lookup a single iOS filesystem path (e.g. "
            "'/var/mobile/Library/SMS/sms.db') and print the "
            "corresponding file path inside the backup."
        ),
    )
    ap.add_argument(
        "-b","--bundle-paths",
        default=None,
        dest="bundle",
        metavar="BUNDLE",
        type=str,
        help=(
            "Lookup all backed-up files belonging to a bundle identifier "
            "(e.g. 'com.apple.MobileSMS' or 'com.facebook.Messenger') "
            "and print their on-disk backup paths."
        ),
    )
    ap.add_argument(
        "--backup-path",
        default=".",
        dest="search_path",
        metavar="BACKUP_PATH",
        help=(
            "Path to the root folder of the local iOS backup. "
            "Defaults to current working directory."
        ),
    )   
    args = ap.parse_args()

    result, ver = is_backup_compatible(args.search_path)
    if not result:
        print(f"[-] Backup: {ver} is not supported (min {TARGET_BACKUP_MIN_VER})")
        exit(-2)

    if args.path is not None:
        if result := find_ios_backup_file(
            args.search_path,
            args.path
        ):
            print(f"[+] Found: {result}")
            exit(0)

        print("[-] File not found.")
        exit(-1)

    elif args.bundle is not None:
        if result := get_app_folders_from_backup(
            args.search_path,
            args.bundle
        ):
            print(f"[+] Found:\n{'\n'.join([f"{x} -> {y}" for x,y in result])}")
            exit(0)

        print("[-] No paths not found.")
        exit(-1)


if __name__ == '__main__':
    main()

