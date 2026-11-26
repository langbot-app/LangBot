import pytest

from langbot_plugin.utils.version_compat import check, parse_range, plugin_version_key


@pytest.mark.parametrize(
    "upper", ["4", "4.x", "4.x.x", "4.*", "4.12", "v4.12.x", "4.12.3"]
)
@pytest.mark.parametrize("lower", ["v4", "4.12", "4.12.3"])
@pytest.mark.parametrize("current", ["4.12.3b1", "v4.12.3rc1", "4.12.3.dev0+g123"])
def test_inclusive_bounds(lower, upper, current):
    manifest = {
        "metadata": {"compatibility": {"langbot": {"min": lower, "max": upper}}}
    }
    assert check(manifest, current)["status"] == "compatible"
    assert check(manifest, "5.0.0")["status"] == "incompatible"


@pytest.mark.parametrize(
    "bounds", [{"min": 4.1}, {"max": 4}, {"min": "4.x"}, {"min": "5", "max": "4"}]
)
def test_invalid(bounds):
    with pytest.raises(ValueError):
        parse_range(bounds)
    assert (
        check({"metadata": {"compatibility": {"langbot": bounds}}}, "4.0.0")["status"]
        == "invalid"
    )


def test_plugin_order():
    versions = ["bad", "2.0b1", "2.0.0-beta.2", "2.0rc1", "1.2", "v1.3"]
    assert sorted(reversed(versions), key=plugin_version_key) == versions
    assert plugin_version_key("1.2", 2, 1) > plugin_version_key("1.2.0", 1, 2)
    assert plugin_version_key("bad", 1, 2) > plugin_version_key("unknown", 1, 1)
