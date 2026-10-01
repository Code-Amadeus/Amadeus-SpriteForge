import pytest
from spriteforge.demo import create_demo


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "workspace with spaces"
    create_demo(root)
    return root


@pytest.fixture
def studio(tmp_path):
    pytest.importorskip("cv2")
    from synthetic import build_studio
    return build_studio(tmp_path)
