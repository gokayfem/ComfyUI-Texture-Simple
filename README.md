# ComfyUI Texture Simple

An interactive PBR material viewer inside ComfyUI. Preview any combination of
color, displacement, normal, ambient-occlusion, metalness, roughness, and alpha
maps on built-in primitives or your own GLB/OBJ mesh.

![Texture Viewer](https://github.com/gokayfem/ComfyUI-Texture-Simple/assets/88277926/594f4b2b-12a6-40a9-9ecc-8f56c5c0448f)

## Features

- Modern ComfyUI DOM-widget integration
- Sphere, cube, torus, plane, and multi-object showcase
- Local GLB and OBJ mesh loading in the browser
- Batch-aware texture-map selection with single-map broadcasting
- Live roughness, metalness, displacement, normal, AO, repeat, and background controls
- Optional auto-rotation
- PNG screenshots and GLB, GLTF, or OBJ export
- Pinned local Three.js assets with no CDN dependency
- Correct copy/paste, collapse, resize, removal, and WebGL cleanup
- Stale-load cancellation and visible errors

## Installation

Install with ComfyUI Manager, or clone manually:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/gokayfem/ComfyUI-Texture-Simple.git
python -m pip install -r ComfyUI-Texture-Simple/requirements.txt
```

Restart ComfyUI after installation.

## Usage

1. Add **Texture Viewer** from `visualization/3D`.
2. Connect any texture maps you have and queue the workflow.
3. Choose a built-in mesh, or select **Load GLB/OBJ** for a local model.
4. Open **Material** to tune PBR values and texture tiling.

When one texture input contains a single image and another contains a batch, the
single texture is reused for every frame. Other mismatched batch sizes produce
a clear error.

GLB is the recommended export format. OBJ contains geometry only. The glTF
material standard does not support displacement maps, so displacement remains a
live preview control rather than a baked glTF property.

## Development

```bash
python -m pip install pytest
pytest -q
```

The browser assets are vendored from Three.js 0.185.1. Its MIT license is in
`web/vendor/THREE-LICENSE.txt`.

<details>
<summary><strong>Cite this project</strong></summary>

If ComfyUI Texture Simple supports your work, please cite the software. GitHub
also provides ready-to-copy APA and BibTeX entries via **Cite this repository**.

```bibtex
@software{Aydogan_ComfyUI_Texture_Simple_2026,
  author  = {Aydoğan, Gökay},
  title   = {ComfyUI Texture Simple},
  version = {2.0.0},
  year    = {2026},
  url     = {https://github.com/gokayfem/ComfyUI-Texture-Simple}
}
```

[ORCID](https://orcid.org/0000-0002-2343-9433) · [Citation metadata](CITATION.cff)

</details>

## Acknowledgements

Thanks to [MrForExample](https://github.com/MrForExample) and the ComfyUI
community for the original viewer patterns and feedback.
