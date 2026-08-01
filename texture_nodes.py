"""Deterministic texture-authoring utilities for ComfyUI.

The module deliberately depends only on NumPy, Pillow, and the torch runtime that
ComfyUI already provides.  No model downloads, network calls, or GPU allocation
occur at import time.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from PIL import Image


CATEGORY = "texture/PBR toolkit"


def _numpy_batch(images: Any) -> np.ndarray:
    array = images.detach().cpu().float().numpy()
    array = np.nan_to_num(array, nan=0.0, posinf=1.0, neginf=0.0)
    if array.ndim == 3:
        array = array[None, ...]
    if array.ndim != 4:
        raise ValueError(f"Expected a BHWC image batch, got {array.shape}.")
    if array.shape[-1] == 1:
        array = np.repeat(array, 3, axis=-1)
    elif array.shape[-1] < 3:
        raise ValueError(f"Expected one or at least three channels, got {array.shape}.")
    return np.clip(array[..., :3], 0.0, 1.0).astype(np.float32, copy=False)


def _torch(array: np.ndarray):
    import torch

    return torch.from_numpy(np.ascontiguousarray(array, dtype=np.float32))


def _luma(batch: np.ndarray) -> np.ndarray:
    return (
        batch[..., 0] * 0.2126
        + batch[..., 1] * 0.7152
        + batch[..., 2] * 0.0722
    ).astype(np.float32)


def _resize_batch(batch: np.ndarray, height: int, width: int) -> np.ndarray:
    if batch.shape[1:3] == (height, width):
        return batch
    resized = []
    for image in batch:
        pil = Image.fromarray((image * 255.0).round().astype(np.uint8), "RGB")
        pil = pil.resize((width, height), Image.Resampling.LANCZOS)
        resized.append(np.asarray(pil, dtype=np.float32) / 255.0)
    return np.stack(resized)


def _broadcast(batch: np.ndarray, count: int, name: str) -> np.ndarray:
    if len(batch) == count:
        return batch
    if len(batch) == 1:
        return np.repeat(batch, count, axis=0)
    raise ValueError(f"{name} has {len(batch)} images; expected 1 or {count}.")


def _box_blur(channel: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return channel
    radius = int(radius)
    kernel = radius * 2 + 1
    padded = np.pad(channel, ((0, 0), (radius, radius), (radius, radius)), mode="reflect")
    integral = np.pad(padded, ((0, 0), (1, 0), (1, 0)), mode="constant")
    integral = integral.cumsum(axis=1, dtype=np.float64).cumsum(axis=2, dtype=np.float64)
    summed = integral[:, kernel:, kernel:] - integral[:, :-kernel, kernel:] - integral[:, kernel:, :-kernel] + integral[:, :-kernel, :-kernel]
    return (summed / float(kernel * kernel)).astype(np.float32)


class TextureNormalFromHeight:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "height": ("IMAGE",),
                "strength": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 20.0, "step": 0.05}),
                "blur_px": ("INT", {"default": 0, "min": 0, "max": 32}),
                "convention": (["OpenGL (+Y)", "DirectX (-Y)"],),
                "wrap_edges": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("normal_map",)
    FUNCTION = "generate"
    CATEGORY = CATEGORY
    DESCRIPTION = "Creates a normalized tangent-space normal map from height without loading a model."

    def generate(self, height, strength, blur_px, convention, wrap_edges):
        values = _box_blur(_luma(_numpy_batch(height)), int(blur_px))
        if wrap_edges:
            dx = (np.roll(values, -1, axis=2) - np.roll(values, 1, axis=2)) * 0.5
            dy = (np.roll(values, -1, axis=1) - np.roll(values, 1, axis=1)) * 0.5
        else:
            dy, dx = np.gradient(values, axis=(1, 2))
        ny_sign = -1.0 if convention.startswith("OpenGL") else 1.0
        vectors = np.stack((-dx * float(strength), ny_sign * dy * float(strength), np.ones_like(dx)), axis=-1)
        vectors /= np.maximum(np.linalg.norm(vectors, axis=-1, keepdims=True), 1e-8)
        return (_torch(vectors * 0.5 + 0.5),)


class TextureAOFromHeight:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "height": ("IMAGE",),
                "strength": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 10.0, "step": 0.05}),
                "radius_px": ("INT", {"default": 12, "min": 1, "max": 128}),
                "directions": (["4", "8", "16"],),
                "wrap_edges": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("ambient_occlusion",)
    FUNCTION = "generate"
    CATEGORY = CATEGORY
    DESCRIPTION = "Approximates multi-direction ambient occlusion from a height map."

    def generate(self, height, strength, radius_px, directions, wrap_edges):
        source = _luma(_numpy_batch(height))
        count = int(directions)
        radius = max(1, int(radius_px))
        occlusion = np.zeros_like(source)
        angles = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False)
        steps = sorted({1, max(1, radius // 3), max(1, (2 * radius) // 3), radius})
        samples = 0
        for step in steps:
            for angle in angles:
                oy = int(round(np.sin(angle) * step))
                ox = int(round(np.cos(angle) * step))
                shifted = np.roll(source, (oy, ox), axis=(1, 2))
                if not wrap_edges:
                    if oy > 0:
                        shifted[:, :oy, :] = source[:, :oy, :]
                    elif oy < 0:
                        shifted[:, oy:, :] = source[:, oy:, :]
                    if ox > 0:
                        shifted[:, :, :ox] = source[:, :, :ox]
                    elif ox < 0:
                        shifted[:, :, ox:] = source[:, :, ox:]
                occlusion += np.maximum(shifted - source, 0.0) / np.sqrt(float(step))
                samples += 1
        ao = np.clip(1.0 - occlusion * float(strength) / max(samples, 1), 0.0, 1.0)
        return (_torch(np.repeat(ao[..., None], 3, axis=-1)),)


class TextureChannelPack:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "preset": (["Custom RGBA", "ORM (glTF)", "RMA", "MSA (Unity HDRP)"],),
                "red_fill": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "green_fill": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "blue_fill": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "alpha_fill": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
            "optional": {
                "red_or_ao": ("IMAGE",),
                "green_or_roughness": ("IMAGE",),
                "blue_or_metalness": ("IMAGE",),
                "alpha_or_smoothness": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("packed_rgba", "manifest")
    FUNCTION = "pack"
    CATEGORY = CATEGORY
    DESCRIPTION = "Packs grayscale sources into RGBA with documented ORM, RMA, and Unity HDRP presets."

    def pack(self, preset, red_fill, green_fill, blue_fill, alpha_fill, **sources):
        named = [
            ("red_or_ao", red_fill),
            ("green_or_roughness", green_fill),
            ("blue_or_metalness", blue_fill),
            ("alpha_or_smoothness", alpha_fill),
        ]
        arrays = {name: _numpy_batch(value) for name, value in sources.items() if value is not None}
        count = max((len(value) for value in arrays.values()), default=1)
        if arrays:
            height = max(value.shape[1] for value in arrays.values())
            width = max(value.shape[2] for value in arrays.values())
        else:
            height = width = 64
        channels = []
        for name, fill in named:
            if name not in arrays:
                channels.append(np.full((count, height, width), float(fill), dtype=np.float32))
            else:
                batch = _broadcast(_resize_batch(arrays[name], height, width), count, name)
                channels.append(_luma(batch))
        packed = np.stack(channels, axis=-1)
        semantics = {
            "Custom RGBA": ["red", "green", "blue", "alpha"],
            "ORM (glTF)": ["occlusion", "roughness", "metalness", "alpha"],
            "RMA": ["roughness", "metalness", "ambient_occlusion", "alpha"],
            "MSA (Unity HDRP)": ["metallic", "occlusion", "detail_mask", "smoothness"],
        }[preset]
        manifest = json.dumps({"preset": preset, "channels": dict(zip("RGBA", semantics))}, indent=2)
        return (_torch(packed), manifest)


class TextureChannelExtract:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"packed_texture": ("IMAGE",), "channel": (["red", "green", "blue", "alpha", "luminance"],)}}

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("channel_image", "channel_mask")
    FUNCTION = "extract"
    CATEGORY = CATEGORY
    DESCRIPTION = "Extracts one packed channel as both IMAGE and MASK."

    def extract(self, packed_texture, channel):
        raw = packed_texture.detach().cpu().float().numpy()
        if raw.ndim == 3:
            raw = raw[None, ...]
        raw = np.nan_to_num(raw, nan=0.0, posinf=1.0, neginf=0.0)
        indices = {"red": 0, "green": 1, "blue": 2, "alpha": 3}
        if channel == "luminance":
            rgb = raw[..., :3]
            if rgb.shape[-1] == 1:
                selected = rgb[..., 0]
            else:
                selected = _luma(rgb)
        else:
            index = indices[channel]
            selected = raw[..., index] if raw.shape[-1] > index else np.ones(raw.shape[:3], dtype=np.float32)
        selected = np.clip(selected, 0.0, 1.0).astype(np.float32)
        return (_torch(np.repeat(selected[..., None], 3, axis=-1)), _torch(selected))


class TextureMakeTileable:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "method": (["Offset + feather", "Mirror"],),
                "blend_fraction": ("FLOAT", {"default": 0.12, "min": 0.01, "max": 0.49, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE", "STRING")
    RETURN_NAMES = ("tileable", "tiled_2x2_proof", "seam_report")
    FUNCTION = "make"
    CATEGORY = CATEGORY
    DESCRIPTION = "Creates a repeatable texture and a 2x2 proof image for immediate seam inspection."

    def make(self, image, method, blend_fraction):
        batch = _numpy_batch(image)
        if method == "Mirror":
            top = np.concatenate((batch, batch[:, :, ::-1, :]), axis=2)
            result = np.concatenate((top, top[:, ::-1, :, :]), axis=1)
        else:
            result = batch.copy()
            h, w = result.shape[1:3]
            bx = max(1, min(w // 2, int(round(w * float(blend_fraction)))))
            by = max(1, min(h // 2, int(round(h * float(blend_fraction)))))
            for x in range(bx):
                t = (x + 1) / (bx + 1)
                left = result[:, :, x, :].copy()
                right = result[:, :, w - 1 - x, :].copy()
                blend = left * t + right * (1.0 - t)
                result[:, :, x, :] = blend
                result[:, :, w - 1 - x, :] = blend
            for y in range(by):
                t = (y + 1) / (by + 1)
                top = result[:, y, :, :].copy()
                bottom = result[:, h - 1 - y, :, :].copy()
                blend = top * t + bottom * (1.0 - t)
                result[:, y, :, :] = blend
                result[:, h - 1 - y, :, :] = blend
        tiled = np.tile(result, (1, 2, 2, 1))
        horizontal = float(np.mean(np.abs(result[:, :, 0, :] - result[:, :, -1, :])))
        vertical = float(np.mean(np.abs(result[:, 0, :, :] - result[:, -1, :, :])))
        report = json.dumps({"edge_mae_horizontal": horizontal, "edge_mae_vertical": vertical, "method": method}, indent=2)
        return (_torch(result), _torch(tiled), report)


class TexturePBRAnalyze:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "role": (["albedo", "roughness", "metalness", "normal", "height", "ao"],)}}

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("report_json", "diagnostic")
    FUNCTION = "analyze"
    CATEGORY = CATEGORY
    DESCRIPTION = "Reports PBR range, clipping, seam energy, and normal-vector validity."

    def analyze(self, image, role):
        batch = _numpy_batch(image)
        flat = batch.reshape(-1, 3)
        seam_x = float(np.mean(np.abs(batch[:, :, 0, :] - batch[:, :, -1, :])))
        seam_y = float(np.mean(np.abs(batch[:, 0, :, :] - batch[:, -1, :, :])))
        clipped = np.any((batch <= 1.0 / 255.0) | (batch >= 254.0 / 255.0), axis=-1)
        diagnostic = batch.copy()
        diagnostic[clipped] = diagnostic[clipped] * 0.2 + np.array([0.8, 0.0, 0.65], dtype=np.float32)
        report: dict[str, Any] = {
            "role": role,
            "resolution": [int(batch.shape[2]), int(batch.shape[1])],
            "batch": int(len(batch)),
            "min": [round(float(x), 6) for x in flat.min(axis=0)],
            "max": [round(float(x), 6) for x in flat.max(axis=0)],
            "mean": [round(float(x), 6) for x in flat.mean(axis=0)],
            "clipped_pixel_fraction": round(float(clipped.mean()), 6),
            "edge_mae_horizontal": round(seam_x, 6),
            "edge_mae_vertical": round(seam_y, 6),
        }
        if role == "normal":
            vectors = batch * 2.0 - 1.0
            lengths = np.linalg.norm(vectors, axis=-1)
            report["normal_length_mean"] = round(float(lengths.mean()), 6)
            report["normal_invalid_fraction"] = round(float((np.abs(lengths - 1.0) > 0.1).mean()), 6)
        return (json.dumps(report, indent=2), _torch(np.clip(diagnostic, 0.0, 1.0)))


NODE_CLASS_MAPPINGS = {
    "TextureNormalFromHeight": TextureNormalFromHeight,
    "TextureAOFromHeight": TextureAOFromHeight,
    "TextureChannelPack": TextureChannelPack,
    "TextureChannelExtract": TextureChannelExtract,
    "TextureMakeTileable": TextureMakeTileable,
    "TexturePBRAnalyze": TexturePBRAnalyze,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TextureNormalFromHeight": "Normal from Height (PBR)",
    "TextureAOFromHeight": "AO from Height (PBR)",
    "TextureChannelPack": "Pack PBR Channels",
    "TextureChannelExtract": "Extract Texture Channel",
    "TextureMakeTileable": "Make Texture Tileable",
    "TexturePBRAnalyze": "Analyze PBR Texture",
}
