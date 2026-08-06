"""职责：验证不依赖网络和外部凭据的公共工具行为。"""

from src.comticket.versioning import bump_version


def test_bump_version_increments_patch() -> None:
    assert bump_version("3.0.0") == "3.0.1"


def test_bump_version_carries_to_minor() -> None:
    assert bump_version("3.0.9") == "3.1.0"


def test_bump_version_expands_two_part_version() -> None:
    assert bump_version("3.3") == "3.3.1"
