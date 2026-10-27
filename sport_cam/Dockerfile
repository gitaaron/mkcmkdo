# SportCam development workspace.
# Everything needed to build every artifact in this repo:
#   node 22        — Firebase emulators + simulated camera (npm run dev) + docs viewer (npm run docs)
#   java 17        — the Firestore and Storage emulators
#   openscad       — <build>/cad/*.scad → <build>/cad/stl/*.stl   (<build>/cad/render_all.sh)
#   python3 + libs — schematics/diagrams PNGs, STL previews, sim frames
FROM node:22-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        openscad \
        openjdk-17-jre-headless \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages \
        schemdraw \
        matplotlib \
        pillow \
        numpy-stl

WORKDIR /workspace

# 5001 functions · 8080 Firestore · 9199 Storage
# · 4000 emulator UI · 8090 docs viewer
EXPOSE 5001 8080 9199 4000 8090

CMD ["sleep", "infinity"]
