"""Retired recovery snapshot, not a test or UI acceptance result.

The executable duplicate was removed after root pytest accidentally collected it.
Its historical source remains in Git (for example, a4e142d); do not run it.
Maintained coverage is in tests/test_browser_e2e.py and requires the explicit
GURUMOJI_RUN_UI_BROWSER=1 opt-in in a sandbox-capable environment.
The scratch run's six failures remain non-acceptance evidence, not passing tests.
"""

__test__ = False


def main() -> int:
    print(
        "not-run: this historical browser-test copy is retired. "
        "Use tests/test_browser_e2e.py with the documented browser opt-in."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
