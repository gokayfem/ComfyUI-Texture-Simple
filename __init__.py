"""Interactive material and texture-map preview node for ComfyUI."""

from __future__ import annotations

import os
from typing import Any

import folder_paths
import numpy as np
from PIL import Image


MAP_MODES = {
    "color": "RGB",
    "displacement": "L",
    "normal": "RGB",
    "ao": "L",
    "metalness": "L",
    "roughness": "L",
    "alpha": "L",
}


def _as_pil(image: Any, mode: str) -> Image.Image:
    array = image.detach().cpu().float().numpy()
    array = np.nan_to_num(array, nan=0.0, posinf=1.0, neginf=0.0)
    array = np.clip(array, 0.0, 1.0)

    if array.ndim == 2:
        source_mode = "L"
    elif array.ndim == 3 and array.shape[-1] == 1:
        array = array[..., 0]
        source_mode = "L"
    elif array.ndim == 3 and array.shape[-1] >= 3:
        array = array[..., :3]
        source_mode = "RGB"
    else:
        raise ValueError(f"Expected an HxW, HxWx1, or HxWx3+ image, got {array.shape}.")

    converted = Image.fromarray(
        (array * 255.0).round().astype(np.uint8),
        mode=source_mode,
    )
    return converted.convert(mode)


def _save_map(
    image: Image.Image,
    *,
    map_type: str,
    batch_number: int,
) -> dict[str, str]:
    output_dir = folder_paths.get_temp_directory()
    full_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
        "texture_viewer",
        output_dir,
        image.width,
        image.height,
    )
    filename = filename.replace("%batch_num%", str(batch_number))
    image_name = f"{filename}_{counter:05}_{map_type}.png"
    image.save(os.path.join(full_folder, image_name), compress_level=1)
    return {"filename": image_name, "subfolder": subfolder, "type": "temp"}


class TextureViewer:
    """Preview PBR texture maps on built-in or browser-loaded 3D meshes."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "color_map": ("IMAGE",),
                "displacement_map": ("IMAGE",),
                "normal_map": ("IMAGE",),
                "ao_map": ("IMAGE",),
                "metalness_map": ("IMAGE",),
                "roughness_map": ("IMAGE",),
                "alpha_map": ("IMAGE",),
            },
        }

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "process_images"
    CATEGORY = "visualization/3D"
    DESCRIPTION = (
        "Interactively previews PBR texture maps on selectable primitives or a "
        "browser-loaded GLB/OBJ mesh. Supports batches, screenshots, and mesh export."
    )

    def process_images(
        self,
        color_map=None,
        displacement_map=None,
        normal_map=None,
        ao_map=None,
        metalness_map=None,
        roughness_map=None,
        alpha_map=None,
    ):
        provided = {
            "color": color_map,
            "displacement": displacement_map,
            "normal": normal_map,
            "ao": ao_map,
            "metalness": metalness_map,
            "roughness": roughness_map,
            "alpha": alpha_map,
        }
        counts = [len(batch) for batch in provided.values() if batch is not None]
        target_count = max(counts, default=0)

        for map_type, batch in provided.items():
            if batch is not None and len(batch) not in (1, target_count):
                raise ValueError(
                    f"{map_type}_map has {len(batch)} images, but the largest input "
                    f"batch has {target_count}. Inputs must match or contain one image."
                )

        saved: dict[str, list[dict[str, str]]] = {
            map_type: [] for map_type in provided
        }
        for map_type, batch in provided.items():
            if batch is None:
                continue
            mode = MAP_MODES[map_type]
            saved[map_type] = [
                _save_map(
                    _as_pil(image, mode),
                    map_type=map_type,
                    batch_number=index,
                )
                for index, image in enumerate(batch)
            ]

        return {"ui": saved}


NODE_CLASS_MAPPINGS = {"TextureViewer": TextureViewer}
NODE_DISPLAY_NAME_MAPPINGS = {"TextureViewer": "Texture Viewer"}
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
