"""Opt-in, sandbox-preserving browser launchers for synthetic test fixtures.

CLI profiles must live in the caller's TemporaryDirectory. The caller owns that
directory (including any intentional profile reuse) and its cleanup. No browser
or driver is installed here, and no arbitrary browser arguments are accepted.
"""

from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from urllib.parse import urlsplit


OPT_IN_ENV = "GURUMOJI_RUN_UI_BROWSER"
NOT_RUN_REASON = f"not-run: set {OPT_IN_ENV}=1 in a sandbox-capable browser environment"
_CLI_FLAGS = (
    "--headless=new",
    "--disable-gpu",
    "--disable-background-networking",
    "--disable-extensions",
    "--no-first-run",
    "--no-default-browser-check",
)


def ui_browser_enabled() -> bool:
    return os.environ.get(OPT_IN_ENV) == "1"


def ui_browser_test(test):
    """Skip only the decorated browser class/method, before fixture setup."""
    return unittest.skipUnless(ui_browser_enabled(), NOT_RUN_REASON)(test)


def require_ui_browser() -> None:
    # Also guard direct launcher calls, independently of collection decorators.
    if not ui_browser_enabled():
        raise unittest.SkipTest(NOT_RUN_REASON)


def browser_executable() -> str | None:
    """Find an already installed Chromium-family browser without spawning it."""
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    return next((str(path) for path in candidates if path and Path(path).is_file()), None)


def require_browser_executable() -> str:
    require_ui_browser()
    executable = browser_executable()
    if executable is None:
        raise unittest.SkipTest("blocked: an installed Chrome, Edge, or Chromium is required")
    return executable


def _launch_blocker(diagnostic: str) -> str | None:
    """Recognize explicit startup diagnostics only, never generic test errors."""
    for message in (
        "No usable sandbox!",
        "Running as root without --no-sandbox is not supported",
        "Executable doesn't exist at",
    ):
        if message in diagnostic:
            return message
    # Keep permission failures tied to browser namespace/socket startup, not an
    # arbitrary app error containing 'permission denied' or 'sandbox'.
    for line in diagnostic.splitlines():
        if "Operation not permitted" in line and any(message in line for message in (
            "Failed to move to new namespace",
            "Failed to unshare namespaces",
            "socket() failed",
        )):
            return line.strip()
    return None


def _positive_integer(name: str, value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def run_browser_dom(
    url: str,
    *,
    profile: Path,
    virtual_time_budget_ms: int,
    timeout_seconds: float,
    viewport: tuple[int, int] | None = None,
    device_scale_factor_one: bool = False,
    allow_media_autoplay: bool = False,
) -> subprocess.CompletedProcess:
    """Dump DOM with a fixed safe CLI; return test failures for caller assertions.

    subprocess.run reaps the launched process on timeout. A timeout is an error,
    not a skip. File URLs support the existing isolated component fixture only;
    they are not a fallback for blocked server/browser access.
    """
    executable = require_browser_executable()
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https", "file") or (
        parsed.scheme != "file" and not parsed.netloc
    ):
        raise ValueError("url must be an explicit http, https, or fixture file URL")
    _positive_integer("virtual_time_budget_ms", virtual_time_budget_ms)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 0 < timeout_seconds < float("inf"):
        raise ValueError("timeout_seconds must be a positive finite number")
    if type(device_scale_factor_one) is not bool or type(allow_media_autoplay) is not bool:
        raise ValueError("browser feature switches must be booleans")
    command = [executable, *_CLI_FLAGS]
    if viewport is not None:
        width, height = viewport
        _positive_integer("viewport width", width)
        _positive_integer("viewport height", height)
        command.append(f"--window-size={width},{height}")
    if device_scale_factor_one:
        command.append("--force-device-scale-factor=1")
    if allow_media_autoplay:
        # Media-state fixture only; this does not test normal user-gesture policy.
        command.append("--autoplay-policy=no-user-gesture-required")
    command.extend((
        f"--user-data-dir={Path(profile).resolve()}",
        f"--virtual-time-budget={virtual_time_budget_ms}",
        "--dump-dom",
        url,
    ))
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout_seconds, check=False,
        )
    except (FileNotFoundError, PermissionError) as error:
        raise unittest.SkipTest(f"blocked: browser executable unavailable: {error}") from error
    # Once DOM output exists, retain it for assertions even if a diagnostic also
    # mentions a startup problem. Never hide a rendered marker/JavaScript failure.
    if result.returncode and not result.stdout.strip():
        blocker = _launch_blocker(result.stderr)
        if blocker:
            raise unittest.SkipTest(f"blocked: browser launch: {blocker}")
    return result


@contextmanager
def sandboxed_playwright_browser():
    """Own Playwright and browser cleanup, even if launch or test assertions fail."""
    require_ui_browser()
    try:
        from playwright.sync_api import Error, TimeoutError, sync_playwright
    except ModuleNotFoundError as error:
        if error.name not in ("playwright", "playwright.sync_api"):
            raise
        raise unittest.SkipTest("blocked: optional Playwright dependency is not installed") from error

    with ExitStack() as cleanup:
        try:
            playwright = sync_playwright().start()
            cleanup.callback(playwright.stop)
            browser = playwright.chromium.launch(
                executable_path=browser_executable(), headless=True, chromium_sandbox=True,
            )
        except TimeoutError:
            raise
        except Error as error:
            blocker = _launch_blocker(str(error))
            if blocker:
                raise unittest.SkipTest(f"blocked: browser launch: {blocker}") from error
            raise
        cleanup.callback(browser.close)
        yield browser
