import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGES = ROOT / "examples" / "pages"


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def smppbox():
    return _load("exporters/smppbox/smpp_exporter.py", "smpp_exporter")


@pytest.fixture(scope="session")
def ksmppd():
    return _load("exporters/ksmppd/ksmppd_exporter.py", "ksmppd_exporter")


@pytest.fixture(scope="session")
def kannel():
    return _load("exporters/kannel/kannel_exporter.py", "kannel_exporter")


@pytest.fixture
def page():
    return lambda name: (PAGES / name).read_bytes()
