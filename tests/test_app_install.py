"""The Vinhomes app installed from a file: its signature read, and each MuMu instance given it,
with fakes; no emulator, adb or real APK."""

import hashlib
import struct
import zipfile

import pytest

from court_booker import app_install
from court_booker.app_install import (
    NotVinhomesError,
    certificates,
    check_signed,
    install_everywhere,
    outcome,
    unpack,
)
from court_booker.device_setup import read_apps_seen
from court_booker.errors import EmulatorError

CERT = b"a certificate's DER bytes"
OTHER = b"someone else's certificate"


def prefixed(data):
    return struct.pack("<I", len(data)) + data


def signed_apk(path, cert=CERT, scheme=0x7109871A, manifest=True):
    """Write a zip with an APK Signing Block holding one signer with ``cert``."""
    with zipfile.ZipFile(path, "w") as archive:
        if manifest:
            archive.writestr("AndroidManifest.xml", "manifest")
        archive.writestr("classes.dex", "code")
    data = path.read_bytes()
    eocd = data.rfind(b"PK\x05\x06")
    (directory,) = struct.unpack_from("<I", data, eocd + 16)
    signed = prefixed(b"") + prefixed(prefixed(cert)) + prefixed(b"")
    signer = prefixed(signed) + prefixed(b"") + prefixed(b"")
    value = prefixed(prefixed(signer))
    pair = struct.pack("<QI", 4 + len(value), scheme) + value
    size = len(pair) + 24
    block = struct.pack("<Q", size) + pair + struct.pack("<Q", size) + b"APK Sig Block 42"
    head, central = data[:directory], data[directory:eocd]
    end = bytearray(data[eocd:])
    struct.pack_into("<I", end, 16, directory + len(block))
    path.write_bytes(head + block + central + bytes(end))
    return path


def fingerprint(cert=CERT):
    return hashlib.sha256(cert).hexdigest()


def test_the_certificate_of_a_v2_or_v3_signature_is_read(tmp_path):
    assert certificates(signed_apk(tmp_path / "a.apk")) == {fingerprint()}
    assert certificates(signed_apk(tmp_path / "b.apk", scheme=0xF05368C0)) == {fingerprint()}


def test_only_the_apps_own_key_passes(tmp_path):
    check_signed([signed_apk(tmp_path / "a.apk")], fingerprint())

    with pytest.raises(NotVinhomesError, match="not signed"):
        check_signed([signed_apk(tmp_path / "b.apk", OTHER)], fingerprint())


def test_an_unsigned_zip_or_another_file_is_refused(tmp_path):
    plain = tmp_path / "plain.apk"
    with zipfile.ZipFile(plain, "w") as archive:
        archive.writestr("AndroidManifest.xml", "manifest")
    text = tmp_path / "notes.txt"
    text.write_text("hello")

    with pytest.raises(NotVinhomesError, match="no v2/v3 signature"):
        check_signed([plain], fingerprint())
    with pytest.raises(NotVinhomesError, match=r"cannot be read|not a zip"):
        check_signed([text], fingerprint())


def test_a_bundle_gives_its_apks_and_each_must_be_signed(tmp_path):
    base = signed_apk(tmp_path / "base.apk")
    split = signed_apk(tmp_path / "split_config.x86_64.apk", OTHER, manifest=False)
    bundle = tmp_path / "app.xapk"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.write(base, base.name)
        archive.write(split, split.name)

    apks = unpack(bundle, tmp_path / "out")

    assert sorted(apk.name for apk in apks) == ["base.apk", "split_config.x86_64.apk"]
    with pytest.raises(NotVinhomesError, match="split_config"):
        check_signed(apks, fingerprint())


def test_an_apk_is_its_own_list(tmp_path):
    apk = signed_apk(tmp_path / "app.apk")
    assert unpack(apk, tmp_path / "out") == [apk]


def test_what_adb_printed_is_read():
    assert outcome(0, "Performing Streamed Install\nSuccess\n").ok
    newer = outcome(1, "Failure [INSTALL_FAILED_VERSION_DOWNGRADE: Downgrade detected]")
    assert (newer.ok, newer.detail) == (True, "a newer version is installed already")
    failed = outcome(2, "adb: failed\nFailure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures]")
    assert not failed.ok and "UPDATE_INCOMPATIBLE" in failed.detail


class FakeMuMu:
    def __init__(self, index, on, log, broken=False):
        self.index, self.on, self.log, self.broken = index, on, log, broken

    def is_started(self):
        return self.on

    def ensure_started(self, timeout):
        if self.broken:
            raise EmulatorError("did not boot")
        if not self.on:
            self.log.append(("start", self.index))
        self.on = True

    def adb_serial(self):
        return f"127.0.0.1:{16384 + 32 * self.index}"

    def shutdown(self):
        self.log.append(("shut", self.index))


class FakeAdb:
    def __init__(self, log):
        self.log = log

    def connect_until(self, serial):
        return serial

    def install_all(self, serial, apks):
        self.log.append(("install", serial))
        return "Success"


def test_every_instance_gets_it_and_those_started_are_shut_again(tmp_path):
    log = []
    mumus = {
        0: FakeMuMu(0, True, log),
        1: FakeMuMu(1, False, log),
        2: FakeMuMu(2, False, log, True),
    }

    results = install_everywhere(
        tmp_path / "MuMuManager.exe",
        FakeAdb(log),
        [tmp_path / "base.apk"],
        180,
        indexes=lambda manager: [0, 1, 2],
        make=lambda manager, index: mumus[index],
        seen=tmp_path / "apps-seen.json",
    )

    assert [(r.index, r.ok) for r in results] == [(0, True), (1, True), (2, False)]
    assert read_apps_seen(tmp_path / "apps-seen.json") == {0: True, 1: True}
    assert log == [
        ("install", "127.0.0.1:16384"),
        ("start", 1),
        ("install", "127.0.0.1:16416"),
        ("shut", 1),
    ]


def test_the_key_is_the_one_read_from_the_installed_app():
    assert len(app_install.VINHOMES_CERTIFICATE) == 64
