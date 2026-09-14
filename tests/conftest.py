import pytest
from spriteforge.demo import create_demo


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "workspace with spaces"
    create_demo(root)
    return root
