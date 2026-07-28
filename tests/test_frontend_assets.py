from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_only_extension_entrypoint_uses_js_suffix():
    javascript_files = sorted(
        path.relative_to(ROOT).as_posix() for path in (ROOT / "web").rglob("*.js")
    )
    assert javascript_files == ["web/visualization.js"]


def test_frontend_has_no_runtime_cdn_dependency():
    frontend_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "web").rglob("*")
        if path.suffix in {".html", ".js", ".mjs", ".css"}
        and "vendor" not in path.parts
    )
    assert "https://" not in frontend_text
    assert "http://" not in frontend_text
    assert "@latest" not in frontend_text


def test_vendored_three_modules_are_present():
    vendor = ROOT / "web" / "vendor"
    expected = {
        "three.module.min.mjs",
        "OrbitControls.mjs",
        "GLTFLoader.mjs",
        "OBJLoader.mjs",
        "GLTFExporter.mjs",
        "OBJExporter.mjs",
        "BufferGeometryUtils.mjs",
        "SkeletonUtils.mjs",
        "THREE-LICENSE.txt",
    }
    assert expected.issubset({path.name for path in vendor.iterdir()})


def test_gltf_loader_uses_local_mjs_dependencies():
    loader = (ROOT / "web" / "vendor" / "GLTFLoader.mjs").read_text(
        encoding="utf-8"
    )
    assert "./BufferGeometryUtils.mjs" in loader
    assert "./SkeletonUtils.mjs" in loader
    assert "../utils/" not in loader
