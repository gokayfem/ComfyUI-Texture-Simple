from __future__ import annotations

import json

import numpy as np
import torch

import texture_nodes as nodes


def gradient(batch=1, height=24, width=32):
    x = torch.linspace(0, 1, width).view(1, 1, width, 1)
    return x.repeat(batch, height, 1, 3)


def test_normal_from_height_is_unit_length_and_finite():
    output, = nodes.TextureNormalFromHeight().generate(
        gradient(), 3.0, 1, "OpenGL (+Y)", True
    )
    vectors = output.numpy() * 2.0 - 1.0
    assert output.shape == (1, 24, 32, 3)
    assert np.isfinite(vectors).all()
    assert np.allclose(np.linalg.norm(vectors, axis=-1), 1.0, atol=1e-5)


def test_ao_and_channel_pack_contracts():
    ao, = nodes.TextureAOFromHeight().generate(gradient(), 2.0, 4, "8", True)
    packed, manifest = nodes.TextureChannelPack().pack(
        "ORM (glTF)", 1.0, 1.0, 0.0, 1.0,
        red_or_ao=ao,
        green_or_roughness=gradient(),
    )
    assert packed.shape == (1, 24, 32, 4)
    assert packed.min() >= 0 and packed.max() <= 1
    assert json.loads(manifest)["channels"]["G"] == "roughness"
    channel, mask = nodes.TextureChannelExtract().extract(packed, "green")
    assert channel.shape[-1] == 3
    assert mask.shape == packed.shape[:3]


def test_tileable_emits_larger_visual_proof_and_low_edge_error():
    image = torch.rand((2, 20, 30, 3), generator=torch.Generator().manual_seed(4))
    tileable, proof, report = nodes.TextureMakeTileable().make(
        image, "Offset + feather", 0.2
    )
    data = json.loads(report)
    assert tileable.shape == image.shape
    assert proof.shape == (2, 40, 60, 3)
    assert data["edge_mae_horizontal"] < 0.02
    assert data["edge_mae_vertical"] < 0.02


def test_pbr_analyzer_highlights_clipped_pixels():
    report, diagnostic = nodes.TexturePBRAnalyze().analyze(torch.zeros((1, 8, 8, 3)), "albedo")
    assert json.loads(report)["clipped_pixel_fraction"] == 1.0
    assert diagnostic.shape == (1, 8, 8, 3)
