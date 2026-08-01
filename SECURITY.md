# Security and privacy

This package does not collect telemetry, call remote model APIs, or send images, textures, meshes, prompts, or credentials over the network. All runtime browser dependencies are vendored.

Files chosen with **Load GLB/OBJ** stay in browser memory. PNG and mesh exports are initiated by the user and downloaded by the browser. Backend temp images are written through ComfyUI's managed temp directory.

Never include private material in public workflows or bug reports. Report a vulnerability with GitHub's private vulnerability-reporting feature when available; otherwise contact the maintainer without attaching sensitive source media to a public issue.
