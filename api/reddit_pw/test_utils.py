"""Lightweight fakes to exercise reddit_pw helpers without Playwright."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import types


# Ensure the repo root is importable when running these tests directly.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Stub modules that api/__init__.py pulls in so imports succeed without external deps.
if "httpx" not in sys.modules:
    sys.modules["httpx"] = types.SimpleNamespace()
if "fastmcp" not in sys.modules:
    class _FakeFastMCP:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

    sys.modules["fastmcp"] = types.SimpleNamespace(FastMCP=_FakeFastMCP)
if "pydantic" not in sys.modules:
    class _DummyModel:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

    def _field(*_args: Any, **_kwargs: Any) -> None:
        return None

    sys.modules["pydantic"] = types.SimpleNamespace(BaseModel=_DummyModel, Field=_field)


class _DummyContext:
    """No-op context manager used for expect_load_state."""

    def __enter__(self):
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


class FakeLocator:
    """Minimal locator that supports the subset of Playwright APIs used in the SDK."""

    def __init__(
        self,
        text: str = "",
        html: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        children: Optional[List["FakeLocator"]] = None,
        nested: Optional[Dict[str, "FakeLocator"]] = None,
        count_value: Optional[int] = None,
        on_click: Optional[Callable[[], None]] = None,
        visible: bool = True,
    ) -> None:
        self.text = text
        self.html = html
        self.attributes = attributes or {}
        self.children = children or []
        self.nested = nested or {}
        self.count_value = len(self.children) if count_value is None else count_value
        self.actions: List[tuple[str, Any]] = []
        self.on_click = on_click
        self._visible = visible

    def count(self) -> int:
        return self.count_value

    def nth(self, idx: int) -> "FakeLocator":
        if 0 <= idx < len(self.children):
            return self.children[idx]
        return FakeLocator()

    @property
    def first(self) -> "FakeLocator":
        return self.nth(0)

    def locator(self, selector: str) -> "FakeLocator":
        return self.nested.get(selector, FakeLocator())

    def inner_text(self) -> str:
        return self.text

    def text_content(self) -> str:
        """Alias for inner_text for compatibility."""
        return self.text

    def inner_html(self) -> str:
        return self.html if self.html is not None else self.text

    def get_attribute(self, name: str) -> Optional[str]:
        value = self.attributes.get(name)
        return str(value) if value is not None else None

    def fill(self, value: Any) -> None:
        self.actions.append(("fill", value))
        self.text = str(value)

    def click(self, force: bool = False, timeout: int = 30000) -> None:
        self.actions.append(("click", {"force": force, "timeout": timeout}))
        if self.on_click:
            self.on_click()

    def check(self) -> None:
        self.actions.append(("check", None))
        self.attributes["checked"] = True

    def uncheck(self) -> None:
        self.actions.append(("uncheck", None))
        self.attributes["checked"] = False

    def set_checked(self, value: bool) -> None:
        self.actions.append(("set_checked", value))
        self.attributes["checked"] = value

    def select_option(self, value: Optional[str] = None, **kwargs: Any) -> None:
        option = value if value is not None else kwargs.get("value") or kwargs.get("label")
        if kwargs.get("raise_error"):
            raise Exception("select_option failure")
        self.actions.append(("select", option))

    def evaluate(self, script: str) -> None:
        self.actions.append(("evaluate", script))

    def wait_for(self, **kwargs: Any) -> None:
        self.actions.append(("wait_for", kwargs))

    def is_visible(self) -> bool:
        """Check if locator is visible."""
        return self._visible

    def all(self) -> List["FakeLocator"]:
        """Get all matching elements."""
        return self.children


class FakePage:
    """Simple fake for Playwright's Page to drive the helpers."""

    def __init__(
        self,
        locators: Optional[Dict[str, FakeLocator]] = None,
        url: str = "",
        title_text: str = "Test Page",
    ) -> None:
        self.locators = locators or {}
        self.visited: List[str] = []
        self.url = url
        self._title = title_text
        self.soup = None  # populated by tests when HTML parsing is needed

    def expect_load_state(self, *_args: Any, **_kwargs: Any) -> _DummyContext:
        return _DummyContext()

    def goto(self, url: str, wait_until: str = "load", timeout: int = 30000) -> None:
        self.url = url
        self.visited.append(url)

    def locator(self, selector: str) -> FakeLocator:
        return self.locators.get(selector, FakeLocator())

    def fill(self, selector: str, value: Any) -> None:
        loc = self.locators.setdefault(selector, FakeLocator())
        loc.fill(value)

    def press(self, selector: str, key: str) -> None:
        loc = self.locators.setdefault(selector, FakeLocator())
        loc.actions.append(("press", key))

    def title(self) -> str:
        """Get page title."""
        return self._title

    def wait_for_timeout(self, timeout: int) -> None:
        """Wait for specified timeout."""
        pass

    def wait_for_load_state(
        self,
        state: str = "load",
        timeout: int = 30000
    ) -> None:
        """Wait for load state."""
        pass


class FakeClient:
    """Client stub that mimics the HTML submission flow used in shipping.py."""

    def __init__(self, pages: List[FakePage]) -> None:
        self.pages = pages
        self.current_page = pages[0] if pages else FakePage()
        self.submissions: List[Dict[str, Any]] = []

    def submit_form(self, form: Any, extra_data: Optional[Dict[str, Any]] = None) -> FakePage:
        self.submissions.append({"form": form, "extra_data": extra_data})
        if len(self.pages) > 1:
            self.pages.pop(0)
            self.current_page = self.pages[0]
        return self.current_page

