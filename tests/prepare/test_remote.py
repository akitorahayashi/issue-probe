"""Every remote URL form names one repository, so the workspace records one identity."""

from __future__ import annotations

import pytest
from prepare import CLIError, normalize_remote


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:owner/wod-tvOS.git",
        "git@github.com:owner/wod-tvOS",
        "https://github.com/owner/wod-tvOS.git",
        "https://github.com/owner/wod-tvOS",
        "ssh://git@github.com/owner/wod-tvOS.git",
        "git@akt:owner/wod-tvOS.git",
    ],
)
def test_a_remote_url_reduces_to_owner_and_name(url):
    assert normalize_remote(url) == "owner/wod-tvOS"


def test_a_url_without_a_repository_path_reports_an_action():
    with pytest.raises(CLIError) as error:
        normalize_remote("https://github.com")

    assert error.value.action
