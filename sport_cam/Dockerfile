# SportCam development workspace.
# Everything needed to build every artifact in this repo:
#   node 22        — server + web app (npm run dev) + docs viewer (npm run docs)
#   openscad       — cad/*.scad → cad/stl/*.stl        (cad/render_all.sh)
#   python3 + libs — schematics/diagrams PNGs, STL previews, sim frames
FROM node:22-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        openscad \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages \
        schemdraw \
        matplotlib \
        pillow \
        numpy-stl

WORKDIR /workspace

# 5173 web app (vite) · 8787 API · 8090 docs viewer
EXPOSE 5173 8787 8090

CMD ["sleep", "infinity"]
