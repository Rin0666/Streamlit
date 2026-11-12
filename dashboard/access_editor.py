"""Authorized, validated writes to the active page-access policy."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import tempfile
import threading

from dashboard import access

EDITOR_PATH = "/page-access"
_save_lock = threading.Lock()


class AccessEditError(Exception):
    """A user-facing editor or save error."""


@dataclass(frozen=True)
class AccessDocument:
    text: str
    revision: str


def _read_authorized(user: access.DirectoryUser, path: Path) -> tuple[AccessDocument, bytes]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    except (OSError, UnicodeError) as error:
        raise AccessEditError("Cannot read a valid access file. Contact your administrator.") from error
    # A master account can repair malformed policies, but proposed saves still
    # pass the normal YAML validator below.
    if access.is_master_user(user):
        return AccessDocument(text, hashlib.sha256(raw).hexdigest()), raw
    try:
        rules = access.parse_access_rules(text)
    except access.AccessConfigurationError as error:
        raise AccessEditError("Cannot read a valid access file. Contact your administrator.") from error
    if not access.can_access(user, EDITOR_PATH, rules):
        raise AccessEditError("You do not have permission to edit page access.")
    return AccessDocument(text, hashlib.sha256(raw).hexdigest()), raw


def read_access_document(user: access.DirectoryUser, path: Path | None = None) -> AccessDocument:
    return _read_authorized(user, path or access.ACCESS_FILE)[0]


def _replace_file(path: Path, content: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_access_document(user: access.DirectoryUser, text: str, expected_revision: str,
                         path: Path | None = None) -> AccessDocument:
    path = path or access.ACCESS_FILE
    # Serialize saves across browser tabs in this server process. An external
    # edit since the document was loaded is detected by its content revision.
    with _save_lock:
        current, original = _read_authorized(user, path)
        if current.revision != expected_revision:
            raise AccessEditError("The file changed since you loaded it. Reload from disk before saving again.")
        try:
            proposed = access.parse_access_rules(text)
        except access.AccessConfigurationError as error:
            raise AccessEditError(str(error)) from None
        if not access.can_access(user, EDITOR_PATH, proposed):
            raise AccessEditError("Keep a /page-access rule that allows your current account to use this editor.")
        content = (text.rstrip("\r\n") + "\n").encode("utf-8")
        if content == original:
            return current
        try:
            _replace_file(path.with_name(path.name + ".bak"), original)
            _replace_file(path, content)
        except OSError as error:
            raise AccessEditError(
                "Could not save the file. Check that the app can write to the access file's folder."
            ) from error
        return AccessDocument(content.decode("utf-8"), hashlib.sha256(content).hexdigest())
