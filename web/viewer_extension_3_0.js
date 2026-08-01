// Versioned entrypoint prevents stale browser modules after major upgrades.
import { api } from "../../scripts/api.js";
import { app } from "../../scripts/app.js";

const EXTENSION_NAME = "gokayfem.texture-simple.viewer";
const PATCHED = Symbol("textureViewerPatched");
const VIEWER_URL = new URL("./html/threeVisualizer.html?v=3.0.0", import.meta.url).href;
const MAP_NAMES = [
    "color",
    "displacement",
    "normal",
    "ao",
    "metalness",
    "roughness",
    "alpha",
];

function normalizeOutput(message) {
    const payload = message?.output ?? message ?? {};
    return Object.fromEntries(
        MAP_NAMES.map((name) => [name, payload[name] ?? []]),
    );
}

function hasViewerOutput(message) {
    const payload = message?.output ?? message ?? {};
    return MAP_NAMES.some((name) => (payload[name]?.length ?? 0) > 0);
}

function chainCallback(previous, next) {
    return function chainedCallback(...args) {
        const result = previous?.apply(this, args);
        next.apply(this, args);
        return result;
    };
}

function createViewer(node) {
    const container = document.createElement("div");
    Object.assign(container.style, {
        width: "100%",
        height: "100%",
        minHeight: "480px",
        overflow: "hidden",
        borderRadius: "8px",
        background: "#14171c",
    });

    const iframe = document.createElement("iframe");
    iframe.title = "Interactive PBR texture preview";
    iframe.loading = "lazy";
    iframe.setAttribute(
        "sandbox",
        "allow-scripts allow-same-origin allow-downloads",
    );
    Object.assign(iframe.style, {
        width: "100%",
        height: "100%",
        border: "0",
        display: "block",
        background: "#14171c",
    });
    const channel = globalThis.crypto?.randomUUID?.()
        ?? `texture-${Date.now()}-${Math.random()}`;
    let ready = false;
    let lastOutput = null;
    let restoring = false;

    const post = (type, payload = {}) => {
        iframe.contentWindow?.postMessage(
            {
                source: EXTENSION_NAME,
                channel,
                type,
                ...payload,
            },
            window.location.origin,
        );
    };

    const initialize = () => {
        post("initialize", { viewUrl: api.apiURL("/view") });
        if (lastOutput) {
            post("update", { output: lastOutput });
        }
    };

    const restoreLatestOutput = async () => {
        if (lastOutput || restoring) {
            return;
        }
        restoring = true;
        try {
            const response = await api.fetchApi("/history?max_items=32");
            if (!response.ok) {
                return;
            }
            const histories = Object.values(await response.json()).reverse();
            for (const history of histories) {
                const nodeId = String(node.id);
                const graph = history?.prompt?.[2];
                const output = history?.outputs?.[nodeId];
                if (
                    graph?.[nodeId]?.class_type === "TextureViewer"
                    && hasViewerOutput(output)
                ) {
                    lastOutput = normalizeOutput(output);
                    if (ready) {
                        post("update", { output: lastOutput });
                    }
                    break;
                }
            }
        } catch (error) {
            console.debug("[Texture Viewer] Cached output restore skipped.", error);
        } finally {
            restoring = false;
        }
    };

    const onMessage = (event) => {
        if (
            event.origin !== window.location.origin
            || event.source !== iframe.contentWindow
            || event.data?.source !== EXTENSION_NAME
            || event.data?.channel !== channel
            || event.data?.type !== "ready"
        ) {
            return;
        }
        ready = true;
        initialize();
        void restoreLatestOutput();
    };

    window.addEventListener("message", onMessage);
    iframe.addEventListener("load", () => {
        ready = false;
        post("connect");
    });
    iframe.src = VIEWER_URL;
    container.append(iframe);
    const connectTimer = window.setInterval(() => {
        if (!ready) {
            post("connect");
        }
    }, 500);

    const widget = node.addDOMWidget(
        "texture_preview",
        "TEXTURE_PREVIEW",
        container,
        {
            canvasOnly: true,
            hideOnZoom: true,
        },
    );
    widget.serialize = false;
    widget.computeLayoutSize = () => ({
        minWidth: 580,
        minHeight: 480,
    });

    const currentWidth = node.size?.[0] ?? 0;
    const currentHeight = node.size?.[1] ?? 0;
    if (currentWidth < 620 || currentHeight < 600) {
        node.setSize([
            Math.max(currentWidth, 620),
            Math.max(currentHeight, 600),
        ]);
    }

    node.__textureViewerUpdate = (output) => {
        lastOutput = output;
        if (!ready) {
            return;
        }
        post("update", { output });
    };

    const onExecution = ({ detail }) => {
        const outputNodeId = String(detail?.node ?? "").split(":")[0];
        if (outputNodeId === String(node.id)) {
            node.__textureViewerUpdate?.(normalizeOutput(detail?.output));
        }
    };
    const onExecutionCached = () => {
        void restoreLatestOutput();
    };
    api.addEventListener("executed", onExecution);
    api.addEventListener("execution_cached", onExecutionCached);

    node.onRemoved = chainCallback(node.onRemoved, () => {
        window.clearInterval(connectTimer);
        api.removeEventListener("executed", onExecution);
        api.removeEventListener("execution_cached", onExecutionCached);
        window.removeEventListener("message", onMessage);
        post("dispose");
        iframe.src = "about:blank";
    });
}

app.registerExtension({
    name: EXTENSION_NAME,

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "TextureViewer" || nodeType.prototype[PATCHED]) {
            return;
        }
        nodeType.prototype[PATCHED] = true;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function onTextureViewerCreated(...args) {
            const result = onNodeCreated?.apply(this, args);
            createViewer(this);
            requestAnimationFrame(() => {
                const cached = app.nodeOutputs?.[this.id];
                if (cached) {
                    this.__textureViewerUpdate?.(normalizeOutput(cached));
                }
            });
            return result;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function onTextureViewerExecuted(message) {
            const result = onExecuted?.apply(this, arguments);
            this.__textureViewerUpdate?.(normalizeOutput(message));
            return result;
        };
    },
});
