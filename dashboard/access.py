"""Page authorization from a YAML policy and a server-verified LDAP identity."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re

import yaml


ACCESS_FILE = Path(os.environ.get("DASHBOARD_ACCESS_FILE", Path(__file__).with_name("page_access.yaml")))
# Server-owned exception: page_access.yaml cannot remove this account's access.
MASTER_USERNAMES = frozenset({"rinzai.terrado"})


class AccessConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class DirectoryUser:
    username: str
    groups: tuple[str, ...] = ()
    tiger_level: int | None = None


def parse_level(value: object) -> int | None:
    if type(value) is int:
        return value if value >= 0 else None
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        return int(value.strip())
    return None


class _PolicyLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise AccessConfigurationError("Policy keys must be unique strings.")
        result[key] = loader.construct_object(value_node)
    return result


_PolicyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def parse_access_rules(text: str) -> dict[str, dict[str, int]]:
    """Validate editor input using the same rules as runtime authorization."""
    try:
        rules = yaml.load(text, Loader=_PolicyLoader)
        if not isinstance(rules, dict):
            raise AccessConfigurationError("Enter a YAML mapping of page URLs to groups and maximum levels.")
        for page, groups in rules.items():
            if not page.startswith("/") or not isinstance(groups, dict):
                raise AccessConfigurationError("Each page key must start with / and contain a group mapping (or {}).")
            seen = set()
            for group, level in groups.items():
                if (not group.strip() or group.strip() != group or group.casefold() in seen
                        or type(level) is not int or level < 0):
                    raise AccessConfigurationError(
                        f"Invalid rule for {page}: use unique group names without surrounding spaces "
                        "and unquoted, non-negative integer levels."
                    )
                seen.add(group.casefold())
        return rules
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise AccessConfigurationError(f"Invalid YAML{location}. Check indentation and mapping syntax.") from None


def load_access_rules(path: Path | None = None) -> dict[str, dict[str, int]]:
    try:
        return parse_access_rules((path or ACCESS_FILE).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, AccessConfigurationError):
        raise AccessConfigurationError(
            "Page access configuration is unavailable or invalid. Contact your administrator."
        ) from None


def is_master_user(user: DirectoryUser) -> bool:
    return user.username.casefold() in MASTER_USERNAMES


def can_access(user: DirectoryUser, path: str, rules: dict[str, dict[str, int]]) -> bool:
    if is_master_user(user):
        return True
    if type(user.tiger_level) is not int or user.tiger_level < 0:
        return False
    memberships = {group.casefold() for group in user.groups}
    return any(group.casefold() in memberships and user.tiger_level <= maximum
               for group, maximum in rules.get(path, {}).items())
