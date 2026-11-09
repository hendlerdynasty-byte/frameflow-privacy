#!/usr/bin/env python3
"""FRAMEFLOW Upload-Key: sicher erzeugen (Passwort nie in argv/log).

Ablage nach bestehender Konvention:
  ~/.hendler-dynasty/secrets/android/frameflow-upload.jks   (PKCS12, 600)
  ~/.hendler-dynasty/secrets/android/frameflow-upload.env   (600, Passwort)
Zusaetzlich in der macOS-Keychain als Wiederherstellungsweg.
"""
import os
import pathlib
import secrets
import subprocess
import sys

SECRETS = pathlib.Path.home() / ".hendler-dynasty" / "secrets" / "android"
KEYSTORE = SECRETS / "frameflow-upload.jks"
ENVFILE = SECRETS / "frameflow-upload.env"
ALIAS = "frameflow-upload"
KEYTOOL = ("/Volumes/My Passport/Unity-Android-Module-6000.3.25f1/PlaybackEngines/"
           "AndroidPlayer/OpenJDK/Contents/Home/bin/keytool")

if KEYSTORE.exists():
    sys.exit(f"ABBRUCH: {KEYSTORE} existiert bereits - nichts ueberschrieben.")

SECRETS.mkdir(parents=True, exist_ok=True)
os.chmod(SECRETS, 0o700)

password = secrets.token_urlsafe(36)

fd = os.open(ENVFILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as fh:
    fh.write("# FRAMEFLOW Upload-Key (nicht ins Repository, nicht in Logs)\n")
    fh.write(f"FRAMEFLOW_KEYSTORE={KEYSTORE}\n")
    fh.write(f"FRAMEFLOW_KEYSTORE_PASSWORD={password}\n")
    fh.write(f"FRAMEFLOW_KEY_ALIAS={ALIAS}\n")
    fh.write(f"FRAMEFLOW_KEY_PASSWORD={password}\n")

env = dict(os.environ)
env["FF_STOREPASS"] = password
cmd = [KEYTOOL, "-genkeypair",
       "-keystore", str(KEYSTORE),
       "-storetype", "PKCS12",
       "-alias", ALIAS,
       "-keyalg", "RSA", "-keysize", "4096",
       "-sigalg", "SHA256withRSA",
       "-validity", "10000",
       "-dname", "CN=Hendler Dynasty FRAMEFLOW Upload, O=Hendler Dynasty, C=DE",
       "-storepass:env", "FF_STOREPASS",
       "-keypass:env", "FF_STOREPASS"]
r = subprocess.run(cmd, env=env, capture_output=True, text=True)
if r.returncode:
    print("keytool FEHLER:", (r.stderr or r.stdout)[:400])
    ENVFILE.unlink(missing_ok=True)
    sys.exit(1)
os.chmod(KEYSTORE, 0o600)

# Wiederherstellungsweg: Keychain (Passwort ueber stdin, nicht argv)
kc = subprocess.run(
    ["security", "add-generic-password", "-a", "frameflow-upload",
     "-s", "frameflow-upload-keystore", "-U", "-w"],
    input=password + "\n", capture_output=True, text=True)
print("keychain:", "OK" if kc.returncode == 0 else f"nicht gesetzt ({kc.stderr.strip()[:80]})")

# Verifikation ohne Passwortausgabe
v = subprocess.run([KEYTOOL, "-list", "-v", "-keystore", str(KEYSTORE),
                    "-storepass:env", "FF_STOREPASS"],
                   env=env, capture_output=True, text=True)
if v.returncode:
    print("Verifikation FEHLER:", (v.stderr or v.stdout)[:300])
    sys.exit(1)
for line in v.stdout.splitlines():
    s = line.strip()
    if s.startswith(("Aliasname", "Alias", "Eintragstyp", "Entry type",
                     "Valid", "G\u00fcltig", "SHA256:", "SHA-256")):
        print(" ", s)
print("keystore:", KEYSTORE, oct(KEYSTORE.stat().st_mode & 0o777))
print("env-file:", ENVFILE, oct(ENVFILE.stat().st_mode & 0o777))
