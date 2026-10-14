ARG COOJA_BASE_IMAGE
FROM ${COOJA_BASE_IMAGE}

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        xvfb \
        x11vnc \
        openbox \
        novnc \
        websockify \
        curl \
        fonts-dejavu-core \
        xdotool && \
    rm -rf /var/lib/apt/lists/*

COPY experiments/cooja/gui/start-gui.sh \
     /usr/local/bin/start-cooja-gui

RUN chmod 0755 /usr/local/bin/start-cooja-gui

EXPOSE 6080

ENTRYPOINT ["/usr/local/bin/start-cooja-gui"]
