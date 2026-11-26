"""Install the Vinhomes app from a file on every MuMu instance: ``court-booker install-app``.

The file is an APK, or a bundle of them (``.xapk`` or ``.apks``: a zip of the base APK and its
splits), downloaded by the user. It is installed only when every APK in it is signed with the
Vinhomes app's certificate (:data:`VINHOMES_CERTIFICATE`), read from the app Google Play
installed: a copy signed by someone else could show a login screen like the app's and keep the
password a run types in. Android itself refuses a damaged file, and an update signed otherwise.

Each MuMu instance on the PC gets it in turn: started if it is off (and shut again after),
connected over adb, then ``adb install-multiple -r`` (the app's data stays). A newer version
already there counts as installed. It is a task of the app's, as a new machine is: refused around
the scheduled run and while a run goes on.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
import struct
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from court_booker.adb import Adb
from court_booker.emulator import CALL_ATTEMPTS, MuMu, instance_indexes
from court_booker.errors import CourtBookerError, RequestError

logger = logging.getLogger(__name__)

VINHOMES_CERTIFICATE = "068b2026894b7ecbeac6281c26035454c384e428b5e38bcb55a5848f1f970388"
"""SHA-256 of the certificate the Vinhomes Resident app is signed with (Google Play's app
signing key, valid 2023-2053), read on 2026-11-26 from version 1.6.0 installed by Google Play:
the same in its v2 and v3 signatures and in every split."""

MAX_FILE_BYTES = 1024**3
"""The app and its splits are about 175 MB; a file of a GB is not one."""
_SIGNING_MAGIC = b"APK Sig Block 42"
_SIGNATURE_IDS = (0x7109871A, 0xF05368C0)
"""APK Signature Scheme v2 and v3: the schemes the app is signed with (no v1)."""
_EOCD_SEARCH = 65_557
"""The end of central directory record is in the last 22 bytes plus a comment of 64 kB at most."""
_MAX_BLOCK = 16 * 1024**2


class NotVinhomesError(RequestError):
    """The file is not the Vinhomes app: unreadable, unsigned, or signed by someone else."""


@dataclass(frozen=True)
class Installed:
    """How the app went on one MuMu instance."""

    index: int
    ok: bool
    detail: str


def _prefixed(data: bytes, offset: int) -> tuple[bytes, int]:
    (size,) = struct.unpack_from("<I", data, offset)
    end = offset + 4 + size
    if end > len(data):
        raise ValueError("a length runs past its block")
    return data[offset + 4 : end], end


def _sequence(data: bytes) -> list[bytes]:
    items, offset = [], 0
    while offset < len(data):
        item, offset = _prefixed(data, offset)
        items.append(item)
    return items


def _signing_block(path: Path) -> bytes | None:
    """Return the APK Signing Block's pairs, or None when the APK has none."""
    with path.open("rb") as file:
        size = file.seek(0, 2)
        file.seek(max(0, size - _EOCD_SEARCH))
        tail = file.read()
        eocd = tail.rfind(b"PK\x05\x06")
        if eocd < 0 or eocd + 20 > len(tail):
            raise ValueError("not a zip file")
        (directory,) = struct.unpack_from("<I", tail, eocd + 16)
        if directory < 32:
            return None
        file.seek(directory - 24)
        footer = file.read(24)
        if footer[8:] != _SIGNING_MAGIC:
            return None
        (block_size,) = struct.unpack_from("<Q", footer, 0)
        if not 24 <= block_size <= _MAX_BLOCK or block_size + 8 > directory:
            raise ValueError("a signing block of a wrong size")
        file.seek(directory - block_size)  # past the block's first size
        return file.read(block_size - 24)


def certificates(path: Path) -> set[str]:
    """Return the SHA-256 of every signer certificate of ``path``'s v2 and v3 signatures.

    Raises :class:`NotVinhomesError` when ``path`` is not an APK that can be read.
    """
    try:
        pairs = _signing_block(path)
        found: set[str] = set()
        offset = 0
        while pairs is not None and offset < len(pairs):
            (length,) = struct.unpack_from("<Q", pairs, offset)
            (kind,) = struct.unpack_from("<I", pairs, offset + 8)
            value = pairs[offset + 12 : offset + 8 + length]
            offset += 8 + length
            if kind not in _SIGNATURE_IDS:
                continue
            signers, _ = _prefixed(value, 0)
            for signer in _sequence(signers):
                signed, _ = _prefixed(signer, 0)
                _digests, after = _prefixed(signed, 0)
                chain, _ = _prefixed(signed, after)
                found.update(hashlib.sha256(cert).hexdigest() for cert in _sequence(chain))
    except (OSError, ValueError, struct.error) as exc:
        raise NotVinhomesError(f"{path.name} is not an APK that can be read: {exc}") from exc
    return found


def unpack(file: Path, folder: Path) -> list[Path]:
    """Return the APKs of ``file``: itself, or those of a bundle, extracted into ``folder``."""
    try:
        with zipfile.ZipFile(file) as archive:
            names = archive.namelist()
            if "AndroidManifest.xml" in names:
                return [file]
            inner = [name for name in names if name.endswith(".apk") and "/" not in name]
            if not inner:
                raise NotVinhomesError(f"{file.name} holds no APK")
            folder.mkdir(parents=True, exist_ok=True)
            apks = []
            for name in inner:
                target = folder / name
                with archive.open(name) as source, target.open("wb") as copy:
                    shutil.copyfileobj(source, copy)
                apks.append(target)
            return apks
    except (OSError, zipfile.BadZipFile) as exc:
        raise NotVinhomesError(f"{file.name} is not an APK or a bundle of them: {exc}") from exc


def check_signed(apks: Sequence[Path], certificate: str = VINHOMES_CERTIFICATE) -> None:
    """Raise :class:`NotVinhomesError` unless every APK is signed with ``certificate``."""
    for apk in apks:
        found = certificates(apk)
        if certificate not in found:
            raise NotVinhomesError(
                f"{apk.name} is not signed by the Vinhomes app's key "
                f"({', '.join(sorted(found)) or 'no v2/v3 signature'})"
            )
    logger.info("Signed by the Vinhomes app's key: %s", ", ".join(apk.name for apk in apks))


def outcome(index: int, output: str) -> Installed:
    """Read what ``adb install`` printed: installed, or a newer version there already."""
    if "Success" in output:
        return Installed(index, True, "installed")
    if "INSTALL_FAILED_VERSION_DOWNGRADE" in output:
        return Installed(index, True, "a newer version is installed already")
    failure = next((line for line in output.splitlines() if "Failure" in line), output.strip())
    return Installed(index, False, failure or "adb printed nothing")


def install_on(mumu: MuMu, adb: Adb, apks: Sequence[Path], boot_timeout: float) -> Installed:
    """Install ``apks`` on ``mumu``, starting it first if it is off and shutting it after."""
    was_on = mumu.is_started()
    mumu.ensure_started(boot_timeout)
    try:
        serial = mumu.adb_serial()
        if serial is None:
            return Installed(mumu.index, False, "MuMu gave no adb address")
        adb.connect_until(serial)
        result = outcome(mumu.index, adb.install_all(serial, apks))
    finally:
        if not was_on:
            mumu.shutdown()
    logger.info("MuMu %d: %s", mumu.index, result.detail)
    return result


def install_everywhere(
    manager: Path,
    adb: Adb,
    apks: Sequence[Path],
    boot_timeout: float,
    indexes: Callable[[Path], list[int]] = instance_indexes,
    make: Callable[[Path, int], MuMu] | None = None,
) -> list[Installed]:
    """Install ``apks`` on every MuMu instance on the PC, one after the other."""
    results = []
    for index in indexes(manager):
        mumu = make(manager, index) if make else MuMu(manager, index, attempts=CALL_ATTEMPTS)
        try:
            results.append(install_on(mumu, adb, apks, boot_timeout))
        except CourtBookerError as exc:  # the next instance still gets it
            logger.error("MuMu %d: %s", index, exc)
            results.append(Installed(index, False, str(exc)))
    return results


def main(argv: list[str]) -> int:
    """Run ``court-booker install-app FILE``; exit codes as a run's (0 installed everywhere, 1
    not on some instance, 2 refused (not the Vinhomes app, or around the scheduled run),
    3 MuMu or adb failed, 5 a run goes on)."""
    from court_booker import cli
    from court_booker.adb import find_adb
    from court_booker.config import load_config
    from court_booker.lock import RunLock, check_quiet_time
    from court_booker.logging_setup import add_file_handler, configure_logging
    from court_booker.paths import data_folder
    from court_booker.ready import find_manager

    parser = argparse.ArgumentParser(
        prog="court-booker install-app",
        description="Install the Vinhomes app from an APK or XAPK file on every MuMu instance.",
    )
    parser.add_argument("file", type=Path, help="the .apk, .xapk or .apks file")
    parser.add_argument(
        "--remove-file", action="store_true", help="delete the file once done (the app's upload)"
    )
    parser.add_argument("--config", default="config.toml", help="config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug output")
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)
    lock: RunLock | None = None
    folder = data_folder().root / "app-unpacked"
    try:
        config = load_config(args.config)
        if config.log_dir:
            logs = Path(args.config).resolve().parent / config.log_dir
            add_file_handler(logs, suffix="-install-app")
        check_quiet_time(datetime.now(), config.wake_at, config.start_at, "app install")
        apks = unpack(args.file, folder)
        check_signed(apks)
        manager = find_manager(config.mumu_manager)
        adb = Adb(find_adb(config.adb_path, [manager.parent]))
        lock = RunLock(data_folder().lock)
        lock.acquire("install_app")
        adb.ensure_server()
        results = install_everywhere(manager, adb, apks, config.boot_timeout)
        if not results:
            logger.error("MuMu lists no instance")
            return cli.EXIT_DEVICE
        return cli.EXIT_OK if all(result.ok for result in results) else cli.EXIT_ROUND_FAILED
    except CourtBookerError as exc:
        logger.error("%s", exc)
        return cli.exit_code(exc)
    except Exception:  # the task must still log
        logger.exception("Unexpected error")
        return cli.EXIT_ROUND_FAILED
    finally:
        if lock is not None:
            lock.release()
        shutil.rmtree(folder, ignore_errors=True)
        if args.remove_file:
            args.file.unlink(missing_ok=True)
