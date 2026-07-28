from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pytest


class FakeTensor:
    def __init__(self, array):
        self.array = np.asarray(array, dtype=np.float32)

    def detach(self):
        return self

    def cpu(self):
        return self

    def float(self):
        return self

    def numpy(self):
        return self.array


class FakeBatch:
    def __init__(self, arrays):
        self.items = [FakeTensor(array) for array in arrays]

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)


@pytest.fixture()
def texture_module(tmp_path, monkeypatch):
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_temp_directory = lambda: str(tmp_path)

    def get_save_image_path(prefix, output_dir, width, height):
        assert width > 0 and height > 0
        return output_dir, f"{prefix}_%batch_num%", 1, "", prefix

    folder_paths.get_save_image_path = get_save_image_path
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths)

    module_path = Path(__file__).parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "texture_viewer_test_module", module_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module, tmp_path


def test_processes_all_maps_and_preserves_batches(texture_module):
    module, output_dir = texture_module
    color = FakeBatch(
        [
            np.zeros((8, 8, 3)),
            np.ones((8, 8, 3)),
        ]
    )
    roughness = FakeBatch([np.full((8, 8, 1), 0.5)])

    result = module.TextureViewer().process_images(
        color_map=color,
        roughness_map=roughness,
    )["ui"]

    assert len(result["color"]) == 2
    assert len(result["roughness"]) == 1
    assert result["normal"] == []
    for descriptor in result["color"] + result["roughness"]:
        assert descriptor["type"] == "temp"
        assert (output_dir / descriptor["filename"]).is_file()


def test_rejects_non_broadcastable_batch_size(texture_module):
    module, _ = texture_module
    color = FakeBatch([np.zeros((4, 4, 3)) for _ in range(2)])
    normal = FakeBatch([np.zeros((4, 4, 3)) for _ in range(3)])

    with pytest.raises(ValueError, match="Inputs must match"):
        module.TextureViewer().process_images(color_map=color, normal_map=normal)


def test_all_inputs_are_optional(texture_module):
    module, _ = texture_module

    result = module.TextureViewer().process_images()["ui"]

    assert set(result) == set(module.MAP_MODES)
    assert all(value == [] for value in result.values())
