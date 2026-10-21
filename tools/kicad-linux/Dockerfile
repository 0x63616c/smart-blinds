# Stable KiCad PPA, ARM64 runner. No native macOS tools or 3D library bundle.
FROM ubuntu@sha256:18b33ff3829707f31ada654a963b9ee35f2e6f0241b964bd17a22a9b330cb63d AS metadata
ARG DEBIAN_FRONTEND=noninteractive
LABEL org.opencontainers.image.title="Smart Blinds isolated KiCad runner"
COPY kicad-ppa.asc /usr/share/keyrings/kicad-ppa.asc
RUN printf 'Acquire::Retries "0";\nAcquire::http::Timeout "60";\nAcquire::https::Timeout "60";\n' > /etc/apt/apt.conf.d/80-bounded-downloads \
 && apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates gnupg \
 && test "$(gpg --show-keys --with-colons /usr/share/keyrings/kicad-ppa.asc | awk -F: '$1=="fpr" {print $10; exit}')" = FDA854F61C4D0D9572BB95E5245D5502FAD7A805 \
 && printf 'deb [signed-by=/usr/share/keyrings/kicad-ppa.asc] https://ppa.launchpadcontent.net/kicad/kicad-10.0-releases/ubuntu noble main\n' > /etc/apt/sources.list.d/kicad.list \
 && apt-get update

FROM metadata AS runtime
ARG KICAD_VERSION=10.0.7~ubuntu24.04.1
RUN test -n "$KICAD_VERSION" \
 && apt-get install -y --no-install-recommends "kicad=$KICAD_VERSION" xvfb xauth python3-wxgtk4.0 python3-shapely python3-yaml \
 && dpkg-query -W -f='${Package}\t${Version}\n' > /usr/local/share/kicad-runner-packages.tsv \
 && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
COPY --chmod=755 entrypoint.sh /usr/local/bin/kicad-runner-entrypoint
ENV LIBGL_ALWAYS_SOFTWARE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    XDG_CONFIG_HOME=/tmp/kicad-config XDG_CACHE_HOME=/tmp/kicad-cache XDG_RUNTIME_DIR=/tmp/kicad-runtime
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/kicad-runner-entrypoint"]
