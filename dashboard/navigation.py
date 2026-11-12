"""Validated YAML navigation shared by URLs, Home, and the sidebar."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re

import yaml

from dashboard.access import DirectoryUser, can_access

PAGES_FILE = Path(__file__).with_name("pages.yaml")


class NavigationConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class Page:
    title: str
    path: str
    renderer: str
    description: str = ""
    icon: str = ":material/article:"


@dataclass(frozen=True)
class Category:
    title: str
    pages: tuple[Page, ...]
    description: str = ""
    icon: str = ":material/folder:"


def load_page_categories(path: Path = PAGES_FILE) -> tuple[Category, ...]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"categories"}:
            raise ValueError("Expected a categories list.")
        if not isinstance(data["categories"], list) or not data["categories"]:
            raise ValueError("Add at least one category.")
        titles, paths, category_titles = {"Home"}, {"/"}, set()
        categories = []
        for raw in data["categories"]:
            if not isinstance(raw, dict) or set(raw) - {"title", "description", "icon", "pages"}:
                raise ValueError("Unknown category fields.")
            title = _text(raw, "title")
            if title in category_titles:
                raise ValueError("Category titles must be unique.")
            category_titles.add(title)
            if not isinstance(raw.get("pages"), list) or not raw["pages"]:
                raise ValueError("Each category needs a pages list.")
            pages = []
            for item in raw["pages"]:
                if not isinstance(item, dict) or set(item) - {"title", "path", "renderer", "description", "icon"}:
                    raise ValueError("Unknown page fields.")
                page = Page(_text(item, "title"), _text(item, "path"), _text(item, "renderer"),
                            _text(item, "description", ""), _icon(item, ":material/article:"))
                if not re.fullmatch(r"/[A-Za-z0-9_-]+", page.path):
                    raise ValueError("Page paths must be a single URL segment beginning with /.")
                if page.title in titles or page.path in paths:
                    raise ValueError("Page titles and paths must be unique.")
                titles.add(page.title)
                paths.add(page.path)
                pages.append(page)
            categories.append(Category(title, tuple(pages), _text(raw, "description", ""),
                                       _icon(raw, ":material/folder:")))
        return tuple(categories)
    except (OSError, UnicodeError, yaml.YAMLError, ValueError) as error:
        raise NavigationConfigurationError(
            "Page navigation configuration is unavailable or invalid. Check dashboard/pages.yaml."
        ) from error


def _text(item: dict, key: str, default: str | None = None) -> str:
    value = item.get(key, default)
    if not isinstance(value, str) or (not value.strip() and default is None):
        raise ValueError(f"Invalid {key}.")
    return value.strip()


def _icon(item: dict, default: str) -> str:
    value = _text(item, "icon", default)
    if not re.fullmatch(r":material/[a-z0-9_]+:", value):
        raise ValueError("Use a Material icon, such as :material/folder:.")
    return value


def accessible_categories(categories: tuple[Category, ...], user: DirectoryUser,
                          rules: dict[str, dict[str, int]]) -> tuple[Category, ...]:
    visible = []
    for category in categories:
        pages = tuple(page for page in category.pages if can_access(user, page.path, rules))
        if pages:
            visible.append(replace(category, pages=pages))
    return tuple(visible)
