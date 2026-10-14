FROM --platform=linux/amd64 ghcr.io/homebrew/brew@sha256:b03f29bb755e1b28c5082bd376e1539762e9dc4e9cff9485655002437595a5d0

ENV HOMEBREW_NO_ANALYTICS=1
ENV HOMEBREW_NO_AUTO_UPDATE=1
ENV HOMEBREW_NO_INSTALL_CLEANUP=1
ENV HOMEBREW_NO_INSTALL_FROM_API=1

USER linuxbrew

RUN set -eux;     test "$(uname -m)" = "x86_64";     brew --version;     test -d "$(brew --repository homebrew/core)"

RUN set -eux;     git config --global user.email "ranger-iot-reproducibility@invalid.example";     git config --global user.name "RANGER-IoT Reproducibility";     brew tap-new ranger/tamarin-pinned

COPY --chown=linuxbrew:linuxbrew     docker/tamarin/tap/Formula/     /home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/ranger/homebrew-tamarin-pinned/Formula/

RUN set -eux;     brew tap;     test -f       /home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/ranger/homebrew-tamarin-pinned/Formula/tamarin-prover.rb;     test -f       /home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/ranger/homebrew-tamarin-pinned/Formula/maude.rb;     test -f       /home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/ranger/homebrew-tamarin-pinned/Formula/libbuddy.rb

RUN set -eux;     brew install       --force-bottle       ranger/tamarin-pinned/libbuddy;     brew install       --force-bottle       ranger/tamarin-pinned/maude;     brew install       --force-bottle       graphviz;     brew install       --force-bottle       ranger/tamarin-pinned/tamarin-prover

RUN set -eux;     command -v tamarin-prover;     command -v maude;     command -v dot;     tamarin-prover --version;     maude --version 2>&1 | head -n 5 || true;     dot -V 2>&1;     tamarin-prover test

WORKDIR /workspace

ENTRYPOINT []
