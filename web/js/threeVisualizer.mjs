import * as THREE from "three";
import { OrbitControls } from "../vendor/OrbitControls.mjs";
import { GLTFLoader } from "../vendor/GLTFLoader.mjs";
import { OBJLoader } from "../vendor/OBJLoader.mjs";
import { GLTFExporter } from "../vendor/GLTFExporter.mjs";
import { OBJExporter } from "../vendor/OBJExporter.mjs";

const SOURCE = "gokayfem.texture-simple";
const MAP_NAMES = [
    "color",
    "displacement",
    "normal",
    "ao",
    "metalness",
    "roughness",
    "alpha",
];
const MATERIAL_SLOTS = {
    color: "map",
    displacement: "displacementMap",
    normal: "normalMap",
    ao: "aoMap",
    metalness: "metalnessMap",
    roughness: "roughnessMap",
    alpha: "alphaMap",
};

const container = document.querySelector("#canvas-container");
const statusElement = document.querySelector("#status");
const errorElement = document.querySelector("#error");
const batchSelect = document.querySelector("#batch-select");
const meshSelect = document.querySelector("#mesh-select");
const meshFile = document.querySelector("#mesh-file");
const materialPanel = document.querySelector("#material-panel");

const renderer = new THREE.WebGLRenderer({
    antialias: true,
    preserveDrawingBuffer: true,
    powerPreference: "high-performance",
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
container.append(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x252a31);
const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 5000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.screenSpacePanning = true;

scene.add(new THREE.HemisphereLight(0xffffff, 0x263044, 2.4));
const keyLight = new THREE.DirectionalLight(0xffffff, 3);
keyLight.position.set(4, 7, 6);
keyLight.castShadow = true;
scene.add(keyLight);
const fillLight = new THREE.DirectionalLight(0x89a8ff, 1.2);
fillLight.position.set(-5, 2, -4);
scene.add(fillLight);

const previewMaterial = new THREE.MeshPhysicalMaterial({
    color: 0xffffff,
    roughness: 0.65,
    metalness: 0,
    side: THREE.DoubleSide,
});
previewMaterial.normalScale.set(1, 1);

let channel = null;
let viewUrl = null;
let output = Object.fromEntries(MAP_NAMES.map((name) => [name, []]));
let previewRoot = null;
let fittedBox = null;
let updateVersion = 0;
let animationFrame = null;
let disposed = false;
let textures = new Map();
const clock = new THREE.Clock();

function setStatus(message) {
    statusElement.textContent = message;
    statusElement.hidden = false;
    errorElement.hidden = true;
}

function setError(error) {
    console.error("[Texture Viewer]", error);
    errorElement.textContent = error instanceof Error ? error.message : String(error);
    errorElement.hidden = false;
    statusElement.hidden = true;
}

function resize() {
    const width = Math.max(container.clientWidth, 1);
    const height = Math.max(container.clientHeight, 1);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(container);
resize();

function prepareGeometry(geometry) {
    if (geometry.attributes.uv && !geometry.attributes.uv1) {
        geometry.setAttribute("uv1", geometry.attributes.uv.clone());
    }
    geometry.computeBoundingBox();
    geometry.computeBoundingSphere();
    return geometry;
}

function disposeOriginalMaterial(material) {
    if (!material || material === previewMaterial) {
        return;
    }
    for (const value of Object.values(material)) {
        if (value?.isTexture) {
            value.dispose();
        }
    }
    material.dispose();
}

function applyPreviewMaterial(root) {
    root.traverse((child) => {
        if (!child.isMesh) {
            return;
        }
        prepareGeometry(child.geometry);
        const originals = Array.isArray(child.material)
            ? child.material
            : [child.material];
        originals.forEach(disposeOriginalMaterial);
        child.material = previewMaterial;
        child.castShadow = true;
        child.receiveShadow = true;
    });
}

function disposeRoot(root) {
    root?.traverse((child) => {
        child.geometry?.dispose();
        if (Array.isArray(child.material)) {
            child.material.forEach(disposeOriginalMaterial);
        } else {
            disposeOriginalMaterial(child.material);
        }
    });
}

function fitCamera() {
    if (!previewRoot) {
        return;
    }
    fittedBox = new THREE.Box3().setFromObject(previewRoot);
    if (fittedBox.isEmpty()) {
        return;
    }
    const sphere = fittedBox.getBoundingSphere(new THREE.Sphere());
    const distance = Math.max(
        sphere.radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)),
        0.5,
    );
    camera.near = Math.max(distance / 1000, 0.001);
    camera.far = Math.max(distance * 100, 100);
    camera.updateProjectionMatrix();
    camera.position.copy(
        sphere.center.clone().add(new THREE.Vector3(0.75, 0.45, 1).normalize().multiplyScalar(distance * 1.25)),
    );
    controls.target.copy(sphere.center);
    controls.minDistance = Math.max(sphere.radius * 0.05, 0.01);
    controls.maxDistance = Math.max(sphere.radius * 20, 10);
    controls.update();
}

function replacePreview(root) {
    if (previewRoot) {
        scene.remove(previewRoot);
        disposeRoot(previewRoot);
    }
    previewRoot = root;
    applyPreviewMaterial(previewRoot);
    scene.add(previewRoot);
    fitCamera();
}

function primitiveMesh(geometry) {
    return new THREE.Mesh(prepareGeometry(geometry), previewMaterial);
}

function buildPrimitive(kind) {
    const root = new THREE.Group();
    if (kind === "cube") {
        root.add(primitiveMesh(new THREE.BoxGeometry(3.5, 3.5, 3.5, 48, 48, 48)));
    } else if (kind === "torus") {
        root.add(primitiveMesh(new THREE.TorusGeometry(2.2, 0.8, 96, 192)));
    } else if (kind === "plane") {
        root.add(primitiveMesh(new THREE.PlaneGeometry(5, 5, 192, 192)));
    } else if (kind === "showcase") {
        const sphere = primitiveMesh(new THREE.SphereGeometry(1.7, 128, 96));
        sphere.position.x = -4.2;
        const cube = primitiveMesh(new THREE.BoxGeometry(2.8, 2.8, 2.8, 40, 40, 40));
        const torus = primitiveMesh(new THREE.TorusGeometry(1.7, 0.65, 80, 160));
        torus.position.x = 4.2;
        root.add(sphere, cube, torus);
    } else {
        root.add(primitiveMesh(new THREE.SphereGeometry(2.4, 160, 112)));
    }
    replacePreview(root);
}

function imageUrl(descriptor) {
    if (!viewUrl) {
        throw new Error("The ComfyUI API URL has not been initialized.");
    }
    const url = new URL(viewUrl, window.location.origin);
    url.search = new URLSearchParams({
        filename: descriptor.filename,
        subfolder: descriptor.subfolder ?? "",
        type: descriptor.type ?? "temp",
    }).toString();
    return url.href;
}

function loadTexture(name, descriptor) {
    return new Promise((resolve, reject) => {
        new THREE.TextureLoader().load(
            imageUrl(descriptor),
            (texture) => {
                texture.colorSpace = name === "color"
                    ? THREE.SRGBColorSpace
                    : THREE.NoColorSpace;
                texture.wrapS = THREE.RepeatWrapping;
                texture.wrapT = THREE.RepeatWrapping;
                texture.anisotropy = Math.min(
                    8,
                    renderer.capabilities.getMaxAnisotropy(),
                );
                resolve([name, texture]);
            },
            undefined,
            () => reject(new Error(`Unable to load ${descriptor.filename}.`)),
        );
    });
}

function updateTextureRepeats() {
    const repeatX = Number(document.querySelector("#repeat-x").value);
    const repeatY = Number(document.querySelector("#repeat-y").value);
    for (const texture of textures.values()) {
        texture.repeat.set(repeatX, repeatY);
        texture.needsUpdate = true;
    }
}

function applyTextures(nextTextures) {
    for (const texture of textures.values()) {
        texture.dispose();
    }
    textures = nextTextures;
    for (const [name, slot] of Object.entries(MATERIAL_SLOTS)) {
        previewMaterial[slot] = textures.get(name) ?? null;
    }
    previewMaterial.transparent = textures.has("alpha");
    previewMaterial.alphaTest = textures.has("alpha") ? 0.01 : 0;
    previewMaterial.needsUpdate = true;
    updateTextureRepeats();
}

async function showFrame(index) {
    const requests = [];
    for (const name of MAP_NAMES) {
        const descriptors = output[name] ?? [];
        const descriptor = descriptors[index] ?? descriptors[0];
        if (descriptor) {
            requests.push(loadTexture(name, descriptor));
        }
    }

    const version = ++updateVersion;
    if (!requests.length) {
        applyTextures(new Map());
        setStatus("No maps connected. Showing the base material.");
        return;
    }

    setStatus(`Loading material frame ${index + 1}…`);
    try {
        const loaded = await Promise.all(requests);
        if (version !== updateVersion || disposed) {
            loaded.forEach(([, texture]) => texture.dispose());
            return;
        }
        applyTextures(new Map(loaded));
        statusElement.hidden = true;
    } catch (error) {
        if (version === updateVersion) {
            setError(error);
        }
    }
}

function setOutput(nextOutput) {
    output = Object.fromEntries(
        MAP_NAMES.map((name) => [name, nextOutput?.[name] ?? []]),
    );
    const count = Math.max(
        1,
        ...MAP_NAMES.map((name) => output[name].length),
    );
    batchSelect.replaceChildren();
    for (let index = 0; index < count; index += 1) {
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = `${index + 1} / ${count}`;
        batchSelect.append(option);
    }
    batchSelect.disabled = count === 1;
    batchSelect.value = "0";
    void showFrame(0);
}

function ensureCustomOption() {
    let option = meshSelect.querySelector('option[value="custom"]');
    if (!option) {
        option = document.createElement("option");
        option.value = "custom";
        option.textContent = "Custom mesh";
        meshSelect.append(option);
    }
    meshSelect.value = "custom";
}

async function loadCustomMesh(file) {
    const extension = file.name.split(".").pop()?.toLowerCase();
    setStatus(`Loading ${file.name}…`);
    let root;
    if (extension === "glb") {
        const buffer = await file.arrayBuffer();
        const result = await new Promise((resolve, reject) => {
            new GLTFLoader().parse(buffer, "", resolve, reject);
        });
        root = result.scene;
    } else if (extension === "obj") {
        root = new OBJLoader().parse(await file.text());
    } else {
        throw new Error("Choose a .glb or .obj mesh.");
    }
    ensureCustomOption();
    replacePreview(root);
    statusElement.hidden = true;
}

function updateMaterialSettings() {
    previewMaterial.roughness = Number(document.querySelector("#roughness").value);
    previewMaterial.metalness = Number(document.querySelector("#metalness").value);
    previewMaterial.displacementScale = Number(
        document.querySelector("#displacement").value,
    );
    const normalStrength = Number(
        document.querySelector("#normal-strength").value,
    );
    previewMaterial.normalScale.set(normalStrength, normalStrength);
    previewMaterial.aoMapIntensity = Number(
        document.querySelector("#ao-strength").value,
    );
    updateTextureRepeats();
}

function download(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportMesh() {
    if (!previewRoot) {
        throw new Error("There is no mesh to export.");
    }
    const format = document.querySelector("#export-format").value;
    if (format === "obj") {
        const data = new OBJExporter().parse(previewRoot);
        download(new Blob([data], { type: "text/plain" }), "texture-preview.obj");
        return;
    }
    const binary = format === "glb";
    const data = await new GLTFExporter().parseAsync(previewRoot, { binary });
    const blob = binary
        ? new Blob([data], { type: "model/gltf-binary" })
        : new Blob([JSON.stringify(data, null, 2)], {
            type: "model/gltf+json",
        });
    download(blob, `texture-preview.${format}`);
}

function takeScreenshot() {
    renderer.render(scene, camera);
    renderer.domElement.toBlob((blob) => {
        if (blob) {
            download(blob, "texture-preview.png");
        }
    }, "image/png");
}

function animate() {
    if (disposed) {
        return;
    }
    animationFrame = requestAnimationFrame(animate);
    const delta = Math.min(clock.getDelta(), 0.1);
    if (
        document.querySelector("#auto-rotate").checked
        && previewRoot
        && document.visibilityState === "visible"
    ) {
        previewRoot.rotation.y += delta * 0.45;
    }
    if (document.visibilityState === "visible") {
        controls.update();
        renderer.render(scene, camera);
    }
}

buildPrimitive("sphere");
animate();

batchSelect.addEventListener("change", () => {
    void showFrame(Number(batchSelect.value));
});
meshSelect.addEventListener("change", () => {
    if (meshSelect.value !== "custom") {
        buildPrimitive(meshSelect.value);
    }
});
document.querySelector("#load-mesh").addEventListener("click", () => {
    meshFile.click();
});
meshFile.addEventListener("change", () => {
    const [file] = meshFile.files;
    if (file) {
        void loadCustomMesh(file).catch(setError);
    }
    meshFile.value = "";
});
document.querySelector("#toggle-material").addEventListener("click", () => {
    materialPanel.hidden = !materialPanel.hidden;
});
document.querySelector("#close-material").addEventListener("click", () => {
    materialPanel.hidden = true;
});
document.querySelector("#reset-camera").addEventListener("click", fitCamera);
document.querySelector("#screenshot").addEventListener("click", takeScreenshot);
document.querySelector("#export-mesh").addEventListener("click", () => {
    void exportMesh().catch(setError);
});
for (const selector of [
    "#roughness",
    "#metalness",
    "#displacement",
    "#normal-strength",
    "#ao-strength",
    "#repeat-x",
    "#repeat-y",
]) {
    document.querySelector(selector).addEventListener("input", updateMaterialSettings);
}
document.querySelector("#background").addEventListener("input", (event) => {
    scene.background.set(event.target.value);
});

window.addEventListener("message", (event) => {
    if (
        event.origin !== window.location.origin
        || event.source !== window.parent
        || event.data?.source !== SOURCE
    ) {
        return;
    }
    if (event.data.type === "connect") {
        channel = event.data.channel;
        window.parent.postMessage(
            { source: SOURCE, channel, type: "ready" },
            window.location.origin,
        );
        return;
    }
    if (event.data.channel !== channel) {
        return;
    }
    if (event.data.type === "initialize") {
        viewUrl = event.data.viewUrl;
    } else if (event.data.type === "update") {
        setOutput(event.data.output);
    } else if (event.data.type === "dispose") {
        disposed = true;
        updateVersion += 1;
        cancelAnimationFrame(animationFrame);
        for (const texture of textures.values()) {
            texture.dispose();
        }
        textures.clear();
        if (previewRoot) {
            scene.remove(previewRoot);
            disposeRoot(previewRoot);
        }
        previewMaterial.dispose();
        controls.dispose();
        renderer.dispose();
    }
});
