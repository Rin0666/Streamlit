"""LDAP authentication without storing or caching user passwords."""
from __future__ import annotations

import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from ldap3 import Connection, Server, Tls, SIMPLE, NONE, SUBTREE
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from dashboard.access import DirectoryUser, parse_level


# Shared by login and Connections Checker; packaged with the Docker image.
LDAP_CONFIG = {
    "server": "ldaps://int.okadamanila.com:636",
    "domain": "int.okadamanila.com",
    "search_base": "DC=int,DC=okadamanila,DC=com",
    "ca_cert_file": str(Path(__file__).resolve().parent / "certificates" / "okada-ldap-ca.pem"),
    "timeout": 10,
}


class AuthenticationError(Exception):
    """A safe message that can be displayed on the login screen."""


@dataclass(frozen=True)
class LDAPSettings:
    server: str
    domain: str = ""
    ca_cert_file: str | None = None
    timeout: int = 10
    search_base: str = ""

    @classmethod
    def from_mapping(cls, values: Mapping | None = None) -> "LDAPSettings":
        if values is None:
            values = LDAP_CONFIG

        def value(name: str, default: str = "") -> str:
            return str(values.get(name, default)).strip()

        server = value("server")
        try:
            parsed = urlsplit(server)
            port = parsed.port
            timeout = int(value("timeout", "10"))
        except ValueError:
            raise AuthenticationError("LDAP configuration is invalid. Contact your administrator.") from None
        if (parsed.scheme not in {"ldap", "ldaps"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment or port == 0 or not 1 <= timeout <= 60):
            raise AuthenticationError("LDAP is not configured. Contact your administrator.")
        return cls(server, value("domain"), value("ca_cert_file") or None, timeout,
                   value("search_base"))


def _read_directory_user(connection, username: str, settings: LDAPSettings) -> DirectoryUser:
    search_base = settings.search_base or ",".join(
        f"DC={part}" for part in settings.domain.split(".") if part
    )
    if not search_base:
        raise AuthenticationError("LDAP search base is not configured. Contact your administrator.")
    # The domain suffix added for binding need not equal the user's stored UPN.
    # Look up short logins by their actual account name, not the synthesized UPN.
    user_filter = f"(&(objectClass=user)(sAMAccountName={escape_filter_chars(username)}))"
    connection.search(search_base, user_filter, search_scope=SUBTREE,
                      attributes=["tigerLevel"], size_limit=2,
                      time_limit=settings.timeout)
    result_code = (connection.result or {}).get("result")
    if result_code != 0:
        detail = {
            3: "The directory lookup timed out.",
            4: "The directory lookup matched multiple accounts.",
            32: "The configured LDAP search base was not found.",
            50: "The directory did not allow the access-profile lookup.",
        }.get(result_code, "The directory lookup failed.")
        raise AuthenticationError(f"Cannot read your directory access profile. {detail} Contact your administrator.")
    if not connection.entries:
        raise AuthenticationError(
            "Sign-in succeeded, but no directory profile matched your account. "
            "Check the LDAP search base and network username."
        )
    if len(connection.entries) != 1:
        raise AuthenticationError("The directory lookup matched multiple accounts. Contact your administrator.")
    entry = connection.entries[0]
    values = entry.entry_attributes_as_dict.get("tigerLevel", [])
    level = parse_level(values[0]) if len(values) == 1 else None
    # AD's membership-chain rule includes direct and nested email/security groups.
    group_filter = ("(&(objectClass=group)(member:1.2.840.113556.1.4.1941:="
                    f"{escape_filter_chars(entry.entry_dn)}))")
    connection.search(search_base, group_filter, search_scope=SUBTREE,
                      attributes=["cn"], time_limit=settings.timeout)
    if connection.result.get("result") != 0:
        raise AuthenticationError("Cannot read your directory groups. Contact your administrator.")
    groups = tuple(str(value) for group in connection.entries
                   for value in group.entry_attributes_as_dict.get("cn", []))
    return DirectoryUser(username, groups, level)


def authenticate(username: str, password: str, settings: LDAPSettings) -> DirectoryUser:
    username = username.strip()
    if not username or not password or not password.strip():
        raise AuthenticationError("Enter your username and password.")
    if "@" in username or "\\" in username:
        raise AuthenticationError("Enter your network username only, without an email address or domain.")
    bind_user = username
    if settings.domain:
        bind_user = f"{username}@{settings.domain}"
    connection = None
    try:
        tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=settings.ca_cert_file)
        server = Server(settings.server, tls=tls, get_info=NONE,
                        connect_timeout=settings.timeout)
        connection = Connection(server, user=bind_user, password=password,
                                authentication=SIMPLE, auto_referrals=False,
                                receive_timeout=settings.timeout, raise_exceptions=False)
        # Upgrade ldap:// before sending credentials.
        if urlsplit(settings.server).scheme == "ldap" and not connection.start_tls():
            raise AuthenticationError("Cannot establish a secure directory connection.")
        if not connection.bind():
            if connection.result and connection.result.get("result") == 49:
                raise AuthenticationError("Sign-in failed. Check your username and password.")
            raise AuthenticationError("Directory sign-in is unavailable. Try again later.")
        return _read_directory_user(connection, username, settings)
    except (LDAPException, OSError, ValueError):
        raise AuthenticationError("Cannot connect securely to the directory. Contact your administrator.") from None
    finally:
        if connection is not None:
            try:
                connection.unbind()
            except (LDAPException, OSError):
                pass
