"""Single source of truth for the application version and update settings.

The installer (Inno Setup) and the build script read APP_VERSION from here,
so bumping this one value is enough to version a new release. GITHUB_REPO is
the repository whose GitHub Releases are checked by the in-app updater.
"""

from __future__ import annotations

APP_VERSION = "1.3.0"

# Repository that publishes the installer as GitHub Releases (owner/name).
# The updater reads https://api.github.com/repos/<repo>/releases/latest and
# compares the tag (e.g. "v1.2.0") with APP_VERSION.
GITHUB_REPO = "ON3VZ/n1mm-fieldday-tracker"
