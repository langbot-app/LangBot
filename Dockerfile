FROM --platform=$BUILDPLATFORM node:22-alpine AS node

WORKDIR /app

COPY web ./web

RUN cd web && npm install && npx vite build

# Build nsjail from source so the image ships a self-contained sandbox backend
# that needs no host Docker socket. Pinned to a release tag for reproducibility.
# Multi-stage keeps the compile toolchain (bison/flex/protobuf-dev/libnl-dev)
# out of the final image; only the nsjail binary and its small runtime libs
# (libprotobuf, libnl-route-3) are carried over.
FROM python:3.12-slim-trixie AS nsjail-build

ARG NSJAIL_VERSION=3.6

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates git build-essential \
        autoconf bison flex libtool pkg-config \
        protobuf-compiler libprotobuf-dev libnl-route-3-dev \
    && git clone --depth 1 --branch "${NSJAIL_VERSION}" https://github.com/google/nsjail.git /nsjail \
    && make -C /nsjail \
    && install -m 0755 /nsjail/nsjail /usr/local/bin/nsjail \
    && rm -rf /var/lib/apt/lists/*

# Audio-only ffmpeg. Debian's ffmpeg package drags in ~200 packages (~400 MB:
# Mesa/LLVM via SDL, Vulkan, every video codec) while LangBot only transcodes
# voice messages (src/langbot/pkg/utils/audio.py). Cross-compiled on the build
# platform, so the arm64 image does not pay for QEMU emulation.
FROM --platform=$BUILDPLATFORM debian:trixie-slim AS ffmpeg-build

ARG TARGETARCH
ARG FFMPEG_VERSION=7.1.5
# sha256 of the PGP-signed release tarball from ffmpeg.org.
ARG FFMPEG_SHA256=de668509caf9e35e3cd162473441fdb29538c6d96ed080292b3cf9e6fc5d558f

RUN set -eux; \
    case "$TARGETARCH" in \
        amd64) triple=x86_64-linux-gnu; arch=x86_64 ;; \
        arm64) triple=aarch64-linux-gnu; arch=aarch64 ;; \
        *) echo "unsupported TARGETARCH=$TARGETARCH" >&2; exit 1 ;; \
    esac; \
    dpkg --add-architecture "$TARGETARCH"; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl xz-utils make pkgconf gcc libc6-dev \
        "gcc-$(echo "$triple" | tr _ -)" "libc6-dev:$TARGETARCH" \
        "libopus-dev:$TARGETARCH" "libmp3lame-dev:$TARGETARCH" \
        "libopencore-amrnb-dev:$TARGETARCH" "libopencore-amrwb-dev:$TARGETARCH"; \
    curl -fsSL "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz" -o /ffmpeg.tar.xz; \
    echo "${FFMPEG_SHA256}  /ffmpeg.tar.xz" | sha256sum -c -; \
    mkdir /ffmpeg; tar -xJf /ffmpeg.tar.xz -C /ffmpeg --strip-components=1; \
    cd /ffmpeg; \
    PKG_CONFIG_LIBDIR="/usr/lib/$triple/pkgconfig:/usr/share/pkgconfig" ./configure \
        --prefix=/opt/ffmpeg \
        --enable-cross-compile --arch="$arch" --target-os=linux --cross-prefix="$triple-" \
        --pkg-config=pkg-config --pkg-config-flags=--static \
        --enable-version3 \
        --disable-debug --disable-doc --disable-ffplay --disable-ffprobe \
        --disable-network --disable-autodetect --disable-everything \
        --disable-avdevice --disable-swscale --disable-x86asm \
        --enable-libopus --enable-libmp3lame \
        --enable-libopencore-amrnb --enable-libopencore-amrwb \
        --enable-protocol=file,pipe \
        --enable-demuxer=aac,amr,flac,matroska,mov,mp3,ogg,pcm_s16le,wav \
        --enable-decoder=aac,aac_latm,alac,amrnb,amrwb,flac,mp3,mp3float,opus,vorbis,adpcm_ima_wav,adpcm_ms,pcm_alaw,pcm_mulaw,pcm_f32le,pcm_s16be,pcm_s16le,pcm_s24le,pcm_s32le,pcm_u8,libopencore_amrnb,libopencore_amrwb,libopus \
        --enable-encoder=aac,flac,libmp3lame,libopencore_amrnb,libopus,pcm_s16le \
        --enable-muxer=adts,amr,flac,ipod,mp3,mp4,ogg,opus,pcm_s16le,wav \
        --enable-parser=aac,amr,flac,mpegaudio,opus,vorbis \
        --enable-bsf=aac_adtstoasc \
        --enable-filter=aformat,anull,aresample,atrim \
        || { tail -n 50 ffbuild/config.log; exit 1; }; \
    make -j"$(nproc)"; \
    make install; \
    "$triple-strip" /opt/ffmpeg/bin/ffmpeg

# Official Node.js build for the target platform. Only the runtime (node +
# npm/npx) is copied into the final image -- no headers, no python3 that the
# NodeSource package pulls in for node-gyp.
FROM node:22-trixie-slim AS node-runtime

# Resolve and install the Python environment with a compiler toolchain that
# never reaches the final image (pilk ships only an sdist for Linux).
FROM python:3.12-slim-trixie AS python-build

ENV UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && python -m pip install --no-cache-dir uv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project --extra seekdb --extra audio

COPY src ./src
RUN uv sync --frozen --no-dev --extra seekdb --extra audio

FROM python:3.12-slim-trixie

# Keep testing packages isolated to the SQLite release with the WAL-reset fix.
RUN printf 'deb http://deb.debian.org/debian forky main\n' > /etc/apt/sources.list.d/sqlite.list \
    && printf 'Package: libsqlite3-0\nPin: release n=forky\nPin-Priority: 990\n\nPackage: *\nPin: release n=forky\nPin-Priority: -1\n' > /etc/apt/preferences.d/sqlite \
    && apt-get update \
    && apt-get install -y --no-install-recommends libsqlite3-0=3.53.4-2 \
    && python -c 'import sqlite3; assert sqlite3.sqlite_version == "3.53.4"' \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    # nsjail runtime libraries (the build toolchain stays in the nsjail-build
    # stage; only these shared libs are needed to execute the binary).
    && apt-get install -y --no-install-recommends libprotobuf32t64 libnl-route-3-200 \
    # Shared codec libraries for the audio-only ffmpeg built above.
    && apt-get install -y --no-install-recommends libopus0 libmp3lame0 libopencore-amrnb0 libopencore-amrwb0 \
    # Install the Docker CLI (client only) so the optional langbot_box
    # service can drive the mounted host Docker socket and create sandbox
    # containers. The same image powers langbot / plugin_runtime / box; only
    # box uses the client. Arch-aware via dpkg so multi-arch builds work.
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/* \
    && touch /.dockerenv

# Node.js so the sandbox (nsjail/Docker box) can run npx-based stdio MCP
# servers. node/npx land in /usr/bin, which is on the nsjail read-only mount
# whitelist (_READONLY_SYSTEM_MOUNTS), so they are bound into the sandbox
# chroot automatically. Without node, any npx-launched MCP server exits with
# return_code=127 (command not found).
COPY --from=node-runtime /usr/local/bin/node /usr/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm /usr/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/bin/npx \
    && node --version && npx --version

# nsjail binary built in the dedicated stage above. Self-contained sandbox
# backend; lets the Box runtime isolate code without a host Docker socket.
COPY --from=nsjail-build /usr/local/bin/nsjail /usr/local/bin/nsjail
COPY --from=ffmpeg-build /opt/ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg

WORKDIR /app

COPY --from=python-build /app/.venv ./.venv
# `uv run` at startup resolves the project environment; reuse the uv that the
# lockfile already installs into the venv instead of a second copy.
RUN ln -s /app/.venv/bin/uv /usr/local/bin/uv

COPY . .

ARG LANGBOT_BUILD_REVISION
RUN if [ -n "$LANGBOT_BUILD_REVISION" ]; then python3 scripts/stamp_build_revision.py --revision "$LANGBOT_BUILD_REVISION"; fi

COPY --from=node /app/web/dist ./web/dist

CMD [ "uv", "run", "--no-sync", "main.py" ]
