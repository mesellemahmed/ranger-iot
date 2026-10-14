#!/usr/bin/env bash
set -euo pipefail

# ================================================================
# RANGER-IoT
# STEP 7D.1-R
#
# DOCKER-ONLY + REPRODUCIBLE FORMAL VERIFICATION FOUNDATION
#
# HOST RESPONSIBILITY:
#   - Bash orchestration only
#   - Docker / Docker Compose only
#   - file creation/redirection only
#
# FORBIDDEN ON HOST:
#   python / pytest / ruff / mypy
#   gcc / cc / make
#   java / gradle
#   tamarin-prover / maude
#   scientific parsers / statistics / hashes
#
# All scientific/tooling execution occurs inside containers.
# ================================================================

ROOT_COMPOSE="docker-compose.yml"

REPRO_COMPOSE="compose.reproducibility.yaml"

TAMARIN_DIR="docker/tamarin"
TAP_DIR="$TAMARIN_DIR/tap/Formula"

POLICY_DIR="reproducibility"

FORMAL_DIR="formal/tamarin"

MODEL="$FORMAL_DIR/ranger_authorization_transport.spthy"

OUT_PREV="artifacts/article-evidence/24-step7d0-formal-executability-audit"
OUT_FAILED="artifacts/article-evidence/25-step7d1-formal-model"

OUT="artifacts/article-evidence/26-step7d1-docker-reproducible"

READINESS="$OUT/step7d1r-final-readiness.json"
PROOF_SUMMARY="$OUT/tamarin-proof-summary.json"
PROVE_LOG="$OUT/tamarin-prove.log"

IMAGE="ranger-tamarin:1.12.0-repro"

#
# Official Homebrew GHCR 7.0.6 manifest digest.
#
HOMEBREW_BASE="ghcr.io/homebrew/brew@sha256:b03f29bb755e1b28c5082bd376e1539762e9dc4e9cff9485655002437595a5d0"

TAMARIN_VERSION="1.12.0"

TAMARIN_SOURCE_SHA256="35f0262e770db3632fcb297deb6ecc2d7c724c693fecfe97892e8224fa161956"

TAMARIN_BOTTLE_SHA256="936631c692ce9fd4c797400eff32e47d6d09e371ca251250cceac15b93f71d99"

MAUDE_SOURCE_SHA256="3dce4f7b42fae2430a08ab2663303d1be244792bb3cc365c58cdb2f3f7bff170"

MAUDE_BOTTLE_SHA256="3a941ae6e9eaa567827959dcac44129166c87b020d238c742c32467980e99936"

LIBBUDDY_SOURCE_SHA256="d3df80a6a669d9ae408cb46012ff17bd33d855529d20f3a7e563d0d913358836"

LIBBUDDY_BOTTLE_SHA256="0807d5706dc37213dbc466b06819fc1b93d710c3543b92eec3c07e7c4fc317d5"


mkdir -p \
    "$TAP_DIR" \
    "$POLICY_DIR" \
    "$OUT"


echo "===================================================================="
echo "RANGER-IOT — STEP 7D.1-R"
echo "DOCKER-ONLY REPRODUCIBLE FORMAL VERIFICATION"
echo
echo "HOST:"
echo "  orchestration only"
echo
echo "SCIENTIFIC EXECUTION:"
echo "  Docker only"
echo
echo "NETWORK:"
echo "  allowed during immutable image construction"
echo "  forbidden during Tamarin proof execution"
echo
echo "NO COMMIT / NO PUSH"
echo "===================================================================="


# ------------------------------------------------------------------
# Helper.
#
# This is the ONLY Python executor used by this script.
# Python therefore runs in the project's Docker service.
# ------------------------------------------------------------------

ranger_python()
{
    docker compose \
        -f "$ROOT_COMPOSE" \
        run \
        --rm \
        -T \
        --no-deps \
        ranger \
        python "$@"
}


ranger_exec()
{
    docker compose \
        -f "$ROOT_COMPOSE" \
        run \
        --rm \
        -T \
        --no-deps \
        ranger \
        "$@"
}


tamarin_exec()
{
    docker compose \
        -f "$REPRO_COMPOSE" \
        run \
        --rm \
        -T \
        --no-deps \
        tamarin \
        "$@"
}


echo
echo "===== 1. DOCKER-ONLY HOST PREFLIGHT ====="

docker version \
    > "$OUT/docker-version.txt"

docker compose version \
    > "$OUT/docker-compose-version.txt"


echo "DOCKER_ENGINE=PASS"
echo "DOCKER_COMPOSE=PASS"


if [ ! -f "$MODEL" ]; then
    echo "ERROR: missing formal model:"
    echo "  $MODEL"
    exit 1
fi


if [ ! -f "$OUT_PREV/step7d0-final-readiness.json" ]; then
    echo "ERROR: missing STEP7D0 readiness"
    exit 1
fi


echo "MODEL_PRESENT=PASS"
echo "STEP7D0_EVIDENCE_PRESENT=PASS"


echo
echo "===== 2. WRITE PERMANENT DOCKER-ONLY POLICY ====="

cat > "$POLICY_DIR/docker-only-policy.json" <<'JSON'
{
  "schema_version": 1,
  "project": "RANGER-IoT",
  "policy": "DOCKER_ONLY_REPRODUCIBLE_EXECUTION",
  "host_allowed": [
    "docker",
    "docker compose",
    "git for repository operations",
    "thin shell orchestration",
    "file creation and redirection"
  ],
  "host_forbidden_for_scientific_execution": [
    "python",
    "pytest",
    "ruff",
    "mypy",
    "gcc",
    "cc",
    "clang",
    "make",
    "java",
    "gradle",
    "tamarin-prover",
    "maude",
    "statistical analysis",
    "scientific oracle execution"
  ],
  "requirements": {
    "all_scientific_tools_execute_in_containers": true,
    "all_tool_versions_recorded": true,
    "docker_base_images_pinned_by_digest_when_available": true,
    "formal_proof_network_disabled": true,
    "scientific_source_hashes_recorded": true,
    "container_image_identity_recorded": true,
    "evidence_packages_hashed": true,
    "host_python_forbidden": true,
    "host_compiler_forbidden": true,
    "host_formal_tools_forbidden": true
  },
  "publication_rule": "A result is not reproducible evidence if any scientific computation was executed by an uncontrolled host tool."
}
JSON


echo "DOCKER_ONLY_POLICY_CREATED=PASS"


echo
echo "===== 3. VENDOR PINNED LIBBUDDY FORMULA ====="

cat > "$TAP_DIR/libbuddy.rb" <<'RUBY'
class Libbuddy < Formula
  desc "Pinned BuDDy runtime for RANGER-IoT Tamarin"
  homepage "https://sourceforge.net/projects/buddy/"

  url "https://downloads.sourceforge.net/project/buddy/buddy/BuDDy%202.4/buddy-2.4.tar.gz"

  version "2.4"

  sha256 "d3df80a6a669d9ae408cb46012ff17bd33d855529d20f3a7e563d0d913358836"

  bottle do
    root_url "https://raw.githubusercontent.com/tamarin-prover/binaries/HEAD/dependencies"

    rebuild 3

    sha256 \
      cellar: :any_skip_relocation,
      x86_64_linux: "0807d5706dc37213dbc466b06819fc1b93d710c3543b92eec3c07e7c4fc317d5"
  end

  def install
    odie("RANGER-IoT reproducibility policy: source build forbidden; expected official bottle")
  end
end
RUBY


echo "PINNED_LIBBUDDY_FORMULA=PASS"


echo
echo "===== 4. VENDOR PINNED MAUDE FORMULA ====="

cat > "$TAP_DIR/maude.rb" <<'RUBY'
class Maude < Formula
  desc "Pinned Maude runtime for RANGER-IoT Tamarin"
  homepage "https://maude.cs.illinois.edu"

  url "https://github.com/maude-lang/Maude/archive/refs/tags/Maude3.5.1.tar.gz"

  version "3.5.1"

  sha256 "3dce4f7b42fae2430a08ab2663303d1be244792bb3cc365c58cdb2f3f7bff170"

  revision 1

  bottle do
    root_url "https://raw.githubusercontent.com/tamarin-prover/binaries/HEAD/dependencies"

    sha256 \
      cellar: :any_skip_relocation,
      x86_64_linux: "3a941ae6e9eaa567827959dcac44129166c87b020d238c742c32467980e99936"
  end

  depends_on "gmp"
  depends_on "ranger/tamarin-pinned/libbuddy"
  depends_on "libsigsegv"
  depends_on "libtecla"
  depends_on "flex"

  def install
    odie("RANGER-IoT reproducibility policy: source build forbidden; expected official bottle")
  end
end
RUBY


echo "PINNED_MAUDE_FORMULA=PASS"


echo
echo "===== 5. VENDOR PINNED TAMARIN FORMULA ====="

cat > "$TAP_DIR/tamarin-prover.rb" <<'RUBY'
class TamarinProver < Formula
  desc "Pinned Tamarin Prover for RANGER-IoT"
  homepage "https://tamarin-prover.com/"

  url "https://github.com/tamarin-prover/tamarin-prover/archive/refs/tags/1.12.0.tar.gz"

  version "1.12.0"

  sha256 "35f0262e770db3632fcb297deb6ecc2d7c724c693fecfe97892e8224fa161956"

  bottle do
    root_url "https://github.com/tamarin-prover/tamarin-prover/releases/download/1.12.0"

    sha256 \
      cellar: :any_skip_relocation,
      x86_64_linux: "936631c692ce9fd4c797400eff32e47d6d09e371ca251250cceac15b93f71d99"
  end

  depends_on "graphviz"
  depends_on "ranger/tamarin-pinned/maude"

  def install
    odie("RANGER-IoT reproducibility policy: source build forbidden; expected official 1.12.0 bottle")
  end

  test do
    system "#{bin}/tamarin-prover", "test"
  end
end
RUBY


echo "PINNED_TAMARIN_FORMULA=PASS"


echo
echo "===== 6. CREATE REPRODUCIBLE TAMARIN DOCKERFILE ====="

cat > "$TAMARIN_DIR/Dockerfile" <<EOF
FROM --platform=linux/amd64 ${HOMEBREW_BASE}

ENV HOMEBREW_NO_ANALYTICS=1
ENV HOMEBREW_NO_AUTO_UPDATE=1
ENV HOMEBREW_NO_INSTALL_CLEANUP=1
ENV HOMEBREW_NO_INSTALL_FROM_API=1

USER linuxbrew

RUN set -eux; \
    test "\$(uname -m)" = "x86_64"; \
    brew --version; \
    test -d "\$(brew --repository homebrew/core)"

RUN set -eux; \
    git config --global user.email "ranger-iot-reproducibility@invalid.example"; \
    git config --global user.name "RANGER-IoT Reproducibility"; \
    brew tap-new ranger/tamarin-pinned

COPY --chown=linuxbrew:linuxbrew \
    docker/tamarin/tap/Formula/ \
    /home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/ranger/homebrew-tamarin-pinned/Formula/

RUN set -eux; \
    brew tap; \
    test -f \
      /home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/ranger/homebrew-tamarin-pinned/Formula/tamarin-prover.rb; \
    test -f \
      /home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/ranger/homebrew-tamarin-pinned/Formula/maude.rb; \
    test -f \
      /home/linuxbrew/.linuxbrew/Homebrew/Library/Taps/ranger/homebrew-tamarin-pinned/Formula/libbuddy.rb

RUN set -eux; \
    brew install \
      --force-bottle \
      ranger/tamarin-pinned/libbuddy; \
    brew install \
      --force-bottle \
      ranger/tamarin-pinned/maude; \
    brew install \
      --force-bottle \
      graphviz; \
    brew install \
      --force-bottle \
      ranger/tamarin-pinned/tamarin-prover

RUN set -eux; \
    command -v tamarin-prover; \
    command -v maude; \
    command -v dot; \
    tamarin-prover --version; \
    maude --version 2>&1 | head -n 5 || true; \
    dot -V 2>&1; \
    tamarin-prover test

WORKDIR /workspace

ENTRYPOINT []
EOF


echo "REPRODUCIBLE_TAMARIN_DOCKERFILE=PASS"


echo
echo "===== 7. CREATE LOCK MANIFEST ====="

cat > "$TAMARIN_DIR/toolchain.lock.json" <<EOF
{
  "schema_version": 1,
  "architecture": "linux/amd64",
  "homebrew_base": "${HOMEBREW_BASE}",
  "homebrew_install_from_api": false,
  "tamarin": {
    "version": "${TAMARIN_VERSION}",
    "source_sha256": "${TAMARIN_SOURCE_SHA256}",
    "linux_x86_64_bottle_sha256": "${TAMARIN_BOTTLE_SHA256}"
  },
  "maude": {
    "version": "3.5.1",
    "revision": 1,
    "source_sha256": "${MAUDE_SOURCE_SHA256}",
    "linux_x86_64_bottle_sha256": "${MAUDE_BOTTLE_SHA256}"
  },
  "libbuddy": {
    "version": "2.4",
    "bottle_rebuild": 3,
    "source_sha256": "${LIBBUDDY_SOURCE_SHA256}",
    "linux_x86_64_bottle_sha256": "${LIBBUDDY_BOTTLE_SHA256}"
  },
  "proof_execution_network": "none",
  "source_build_fallback": false
}
EOF


echo "TOOLCHAIN_LOCK_CREATED=PASS"


echo
echo "===== 8. CREATE REPRODUCIBILITY COMPOSE ====="

cat > "$REPRO_COMPOSE" <<'YAML'
services:
  tamarin:
    image: ranger-tamarin:1.12.0-repro

    build:
      context: .
      dockerfile: docker/tamarin/Dockerfile

    platform: linux/amd64

    working_dir: /workspace

    volumes:
      - .:/workspace

    network_mode: none
YAML


echo "REPRODUCIBILITY_COMPOSE_CREATED=PASS"


echo
echo "===== 9. DOCKER-ONLY STATIC POLICY VALIDATION ====="

ranger_python - \
    "$POLICY_DIR/docker-only-policy.json" \
    "$TAMARIN_DIR/toolchain.lock.json" \
    "$MODEL" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


policy = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

lock = json.loads(
    Path(sys.argv[2]).read_text(
        encoding="utf-8"
    )
)

model = Path(
    sys.argv[3]
).read_text(
    encoding="utf-8"
)


lemmas = re.findall(
    r"(?m)^\s*lemma\s+([A-Za-z0-9_.-]+)\s*:",
    model,
)


expected = {
    "executable_initial_accept",
    "executable_same_epoch_recovery",
    "revocation_reachable",
    "accept_has_rekey_origin",
    "accept_requires_authorization",
    "revoked_never_accepts",
    "recovery_requester_authorized",
    "recovery_helper_authorized",
    "recovery_same_epoch",
    "recovery_accept_has_rekey_origin",
    "epoch_key_secrecy_unless_compromised",
}


checks = {
    "docker_policy":
        policy.get("policy")
        == "DOCKER_ONLY_REPRODUCIBLE_EXECUTION",

    "host_python_forbidden":
        policy[
            "requirements"
        ][
            "host_python_forbidden"
        ]
        is True,

    "digest_pinned":
        lock[
            "homebrew_base"
        ].startswith(
            "ghcr.io/homebrew/brew@sha256:"
        ),

    "homebrew_api_disabled":
        lock[
            "homebrew_install_from_api"
        ]
        is False,

    "tamarin_1_12":
        lock[
            "tamarin"
        ][
            "version"
        ]
        == "1.12.0",

    "tamarin_bottle_sha":
        lock[
            "tamarin"
        ][
            "linux_x86_64_bottle_sha256"
        ]
        ==
        "936631c692ce9fd4c797400eff32e47d6d09e371ca251250cceac15b93f71d99",

    "maude_bottle_sha":
        lock[
            "maude"
        ][
            "linux_x86_64_bottle_sha256"
        ]
        ==
        "3a941ae6e9eaa567827959dcac44129166c87b020d238c742c32467980e99936",

    "offline_proof":
        lock[
            "proof_execution_network"
        ]
        == "none",

    "no_source_fallback":
        lock[
            "source_build_fallback"
        ]
        is False,

    "lemma_count_11":
        len(lemmas)
        == 11,

    "lemma_set_exact":
        set(lemmas)
        == expected,

    "three_nonvacuity":
        model.count(
            "exists-trace"
        )
        == 3,
}


for name, passed in checks.items():
    print(
        f"{name:34s}",
        "PASS"
        if passed
        else "FAIL",
    )


if not all(checks.values()):
    raise SystemExit(
        "DOCKER reproducibility contract failed"
    )


print()
print(
    "DOCKER_REPRODUCIBILITY_STATIC_CONTRACT=PASS"
)
PY


echo
echo "===== 10. HASH REPRODUCIBILITY INPUTS — INSIDE DOCKER ====="

ranger_exec \
    sha256sum \
    "$POLICY_DIR/docker-only-policy.json" \
    "$TAMARIN_DIR/toolchain.lock.json" \
    "$TAMARIN_DIR/Dockerfile" \
    "$TAP_DIR/tamarin-prover.rb" \
    "$TAP_DIR/maude.rb" \
    "$TAP_DIR/libbuddy.rb" \
    "$REPRO_COMPOSE" \
    "$MODEL" \
    > "$OUT/reproducibility-inputs.sha256"


echo "REPRODUCIBILITY_INPUT_HASHES=PASS"


echo
echo "===== 11. RECORD PROJECT REVISION — INSIDE DOCKER ====="

ranger_python - \
    "$OUT/repository-revision.json" <<'PYMETA'
from __future__ import annotations

import json
import sys
from pathlib import Path


git_dir = Path(
    "/workspace/.git"
)


if not git_dir.exists():
    raise SystemExit(
        "Missing /workspace/.git"
    )


head = (
    git_dir
    / "HEAD"
).read_text(
    encoding="utf-8"
).strip()


branch = None
commit = None


if head.startswith(
    "ref: "
):
    ref = head[5:]

    branch = ref.removeprefix(
        "refs/heads/"
    )


    loose_ref = (
        git_dir
        / ref
    )


    if loose_ref.exists():
        commit = loose_ref.read_text(
            encoding="utf-8"
        ).strip()

    else:
        packed_refs = (
            git_dir
            / "packed-refs"
        )


        if packed_refs.exists():
            for line in packed_refs.read_text(
                encoding="utf-8"
            ).splitlines():
                line = line.strip()


                if (
                    not line
                    or line.startswith("#")
                    or line.startswith("^")
                ):
                    continue


                sha, name = line.split(
                    " ",
                    1,
                )


                if name == ref:
                    commit = sha
                    break

else:
    commit = head


if (
    commit is None
    or len(commit) != 40
):
    raise SystemExit(
        f"Unable to resolve repository HEAD: {commit!r}"
    )


payload = {
    "schema_version":
        1,

    "head":
        commit,

    "branch":
        branch,

    "resolved_inside_docker":
        True,

    "host_git_used_for_scientific_evidence":
        False,
}


output = Path(
    sys.argv[1]
)


output.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


print(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
)
PYMETA


echo "REPOSITORY_REVISION_CAPTURED_IN_DOCKER=PASS"


echo "===== 12. RECORD RANGER IMAGE ID ====="

RANGER_IMAGE="$(
    docker compose \
        -f "$ROOT_COMPOSE" \
        images \
        -q \
        ranger \
        | head -n 1
)"


if [ -z "$RANGER_IMAGE" ]; then
    echo "ERROR: ranger image is not built"
    echo "Run the normal Docker project bootstrap first."
    exit 1
fi


docker image inspect \
    "$RANGER_IMAGE" \
    > "$OUT/ranger-image-inspect.json"


echo "RANGER_IMAGE=$RANGER_IMAGE"


echo
echo "===== 13. BUILD PINNED TAMARIN IMAGE ====="

set +e

docker compose \
    -f "$REPRO_COMPOSE" \
    build \
    --no-cache \
    tamarin \
    > "$OUT/tamarin-image-build.log" \
    2>&1

BUILD_RC=$?

set -e


echo "BUILD_RC=$BUILD_RC"


if [ "$BUILD_RC" -ne 0 ]; then
    echo
    echo "============================================================"
    echo "TAMARIN REPRODUCIBLE IMAGE BUILD: FAIL"
    echo
    echo "THIS IS TOOLCHAIN CONSTRUCTION FAILURE."
    echo "NO FORMAL SECURITY RESULT EXISTS."
    echo "============================================================"
    exit "$BUILD_RC"
fi


echo "TAMARIN_IMAGE_BUILD=PASS"


echo
echo "===== 14. RECORD FINAL TAMARIN IMAGE ID ====="

TAMARIN_IMAGE_ID="$(
    docker image inspect \
        "$IMAGE" \
        --format '{{.Id}}'
)"


echo "$TAMARIN_IMAGE_ID" \
    > "$OUT/tamarin-image-id.txt"


docker image inspect \
    "$IMAGE" \
    > "$OUT/tamarin-image-inspect.json"


echo "TAMARIN_IMAGE_ID=$TAMARIN_IMAGE_ID"


echo
echo "===== 15. OFFLINE TAMARIN RUNTIME CONTRACT ====="

set +e

tamarin_exec \
    bash -lc '
      set -euo pipefail

      echo "===== ENVIRONMENT ====="

      echo "architecture=$(uname -m)"

      echo "brew=$(command -v brew)"
      echo "tamarin=$(command -v tamarin-prover)"
      echo "maude=$(command -v maude)"
      echo "dot=$(command -v dot)"

      echo
      echo "===== VERSIONS ====="

      brew --version

      tamarin-prover --version

      maude --version 2>&1 \
        | head -n 5 \
        || true

      dot -V 2>&1

      echo
      echo "===== PINNED HOMEBREW CORE ====="

      CORE="$(brew --repository homebrew/core)"

      echo "core_repository=$CORE"

      git \
        -C "$CORE" \
        rev-parse HEAD

      echo
      echo "===== INSTALLED FORMULAE ====="

      brew list --versions \
        tamarin-prover \
        maude \
        libbuddy \
        graphviz

      echo
      echo "===== TAMARIN SELFTEST ====="

      tamarin-prover test

      echo
      echo "OFFLINE_TAMARIN_RUNTIME_CONTRACT=PASS"
    ' \
    > "$OUT/tamarin-runtime-offline.log" \
    2>&1

RUNTIME_RC=$?

set -e


echo "RUNTIME_RC=$RUNTIME_RC"


if [ "$RUNTIME_RC" -ne 0 ]; then
    echo
    echo "TAMARIN OFFLINE RUNTIME: FAIL"
    exit "$RUNTIME_RC"
fi


echo "OFFLINE_TAMARIN_RUNTIME=PASS"


echo
echo "===== 16. DOCKER-ONLY FORMAL MODEL STATIC AUDIT ====="

ranger_python - \
    "$MODEL" \
    "$OUT/model-static-audit.json" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


model_path = Path(
    sys.argv[1]
)

output = Path(
    sys.argv[2]
)


text = model_path.read_text(
    encoding="utf-8"
)


lemmas = re.findall(
    r"(?m)^\s*lemma\s+([A-Za-z0-9_.-]+)\s*:",
    text,
)


expected = [
    "executable_initial_accept",
    "executable_same_epoch_recovery",
    "revocation_reachable",
    "accept_has_rekey_origin",
    "accept_requires_authorization",
    "revoked_never_accepts",
    "recovery_requester_authorized",
    "recovery_helper_authorized",
    "recovery_same_epoch",
    "recovery_accept_has_rekey_origin",
    "epoch_key_secrecy_unless_compromised",
]


checks = {
    "theory":
        "theory RangerIoT_AuthorizationTransport"
        in text,

    "symmetric_encryption":
        "builtins: symmetric-encryption"
        in text,

    "dolev_yao_in":
        "In("
        in text,

    "dolev_yao_out":
        "Out("
        in text,

    "fresh_epoch":
        "Fr(~epoch)"
        in text,

    "fresh_groupkey":
        "Fr(~groupkey)"
        in text,

    "revocation":
        "RevokedAt($R,~epoch)"
        in text,

    "member_compromise":
        "Compromise_Authorized_Member"
        in text,

    "gm_compromise":
        "Compromise_Group_Manager"
        in text,

    "non_vacuity_three":
        text.count(
            "exists-trace"
        )
        == 3,

    "eleven_lemmas":
        lemmas
        == expected,

    "no_sorry":
        re.search(
            r"\bsorry\b",
            text,
            re.I,
        )
        is None,

    "no_admit":
        re.search(
            r"\badmit\b",
            text,
            re.I,
        )
        is None,
}


passed = all(
    checks.values()
)


payload = {
    "schema_version":
        1,

    "model":
        model_path.as_posix(),

    "checks":
        checks,

    "lemma_count":
        len(
            lemmas
        ),

    "lemmas":
        lemmas,

    "pass":
        passed,
}


output.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


print(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
)


if not passed:
    raise SystemExit(1)
PY


echo "DOCKER_MODEL_STATIC_AUDIT=PASS"


echo
echo "===== 17. OFFLINE TAMARIN PARSE / PRECOMPUTATION ====="

set +e

tamarin_exec \
    bash -lc \
    "timeout 300s \
     tamarin-prover \
     --precompute-only \
     '$MODEL'" \
    > "$OUT/tamarin-precompute.log" \
    2>&1

PRECOMPUTE_RC=$?

set -e


echo "PRECOMPUTE_RC=$PRECOMPUTE_RC"


if [ "$PRECOMPUTE_RC" -ne 0 ]; then
    echo
    echo "============================================================"
    echo "FORMAL MODEL PRECOMPUTATION: FAIL"
    echo "THIS IS MODEL/WELL-FORMEDNESS FAILURE."
    echo "NOT A SECURITY COUNTEREXAMPLE."
    echo "============================================================"
    exit "$PRECOMPUTE_RC"
fi


echo "TAMARIN_PRECOMPUTE=PASS"


echo
echo "===== 18. OFFLINE TAMARIN PROOF — ALL LEMMAS ====="

set +e

tamarin_exec \
    bash -lc \
    "timeout 900s \
     tamarin-prover \
     --prove \
     '$MODEL' \
     +RTS -N2 -RTS" \
    > "$PROVE_LOG" \
    2>&1

PROVE_RC=$?

set -e


echo "PROVE_RC=$PROVE_RC"


if [ "$PROVE_RC" -eq 124 ]; then
    echo "TAMARIN_PROOF_TIMEOUT=YES"
else
    echo "TAMARIN_PROOF_TIMEOUT=NO"
fi


echo
echo "===== 19. PARSE PROOF OUTPUT — PYTHON INSIDE DOCKER ====="

ranger_python - \
    "$PROVE_LOG" \
    "$PROOF_SUMMARY" \
    "$PROVE_RC" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


log_path = Path(
    sys.argv[1]
)

output = Path(
    sys.argv[2]
)

return_code = int(
    sys.argv[3]
)


expected = [
    "executable_initial_accept",
    "executable_same_epoch_recovery",
    "revocation_reachable",
    "accept_has_rekey_origin",
    "accept_requires_authorization",
    "revoked_never_accepts",
    "recovery_requester_authorized",
    "recovery_helper_authorized",
    "recovery_same_epoch",
    "recovery_accept_has_rekey_origin",
    "epoch_key_secrecy_unless_compromised",
]


text = log_path.read_text(
    encoding="utf-8",
    errors="replace",
)


summary_re = re.compile(
    r"(?m)^\s*"
    r"([A-Za-z_][A-Za-z0-9_.-]*)"
    r"\s+\(([^)]*)\):"
    r"\s+"
    r"(verified|falsified|"
    r"analysis incomplete|"
    r"unproven|unknown)"
    r"(?:\s+\(([^)]*)\))?"
)


results = {}


for match in summary_re.finditer(
    text
):
    results[
        match.group(1)
    ] = {
        "kind":
            match.group(2),

        "status":
            match.group(3),

        "details":
            match.group(4),
    }


missing = [
    lemma
    for lemma
    in expected
    if lemma not in results
]


verified = [
    lemma
    for lemma
    in expected
    if results.get(
        lemma,
        {},
    ).get(
        "status"
    )
    == "verified"
]


falsified = [
    lemma
    for lemma
    in expected
    if results.get(
        lemma,
        {},
    ).get(
        "status"
    )
    == "falsified"
]


incomplete = [
    lemma
    for lemma
    in expected
    if results.get(
        lemma,
        {},
    ).get(
        "status"
    )
    in {
        "analysis incomplete",
        "unproven",
        "unknown",
    }
]


all_verified = (
    return_code == 0
    and
    len(verified) == 11
    and
    not missing
    and
    not falsified
    and
    not incomplete
)


if return_code == 124:
    state = "TAMARIN_PROOF_TIMEOUT"

elif falsified:
    state = "TAMARIN_LEMMA_FALSIFIED"

elif incomplete:
    state = "TAMARIN_PROOF_INCOMPLETE"

elif missing:
    state = "TAMARIN_OUTPUT_MISSING_REQUIRED_LEMMAS"

elif all_verified:
    state = "ALL_STEP7D1_ABSTRACT_LEMMAS_VERIFIED"

else:
    state = "TAMARIN_EXECUTION_ANOMALY"


payload = {
    "schema_version":
        2,

    "step":
        "STEP7D1_DOCKER_REPRODUCIBLE_PROOF",

    "docker_only":
        True,

    "proof_network":
        "none",

    "return_code":
        return_code,

    "expected_lemma_count":
        11,

    "reported_lemma_count":
        len(
            results
        ),

    "verified_count":
        len(
            verified
        ),

    "falsified_count":
        len(
            falsified
        ),

    "incomplete_count":
        len(
            incomplete
        ),

    "verified_lemmas":
        verified,

    "falsified_lemmas":
        falsified,

    "incomplete_lemmas":
        incomplete,

    "missing_lemmas":
        missing,

    "results":
        results,

    "all_required_lemmas_verified":
        all_verified,

    "scientific_state":
        state,
}


output.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


print(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
)
PY


echo
echo "===== 20. CLASSIFY FORMAL RESULT ====="

ranger_python - \
    "$PROOF_SUMMARY" \
    "$READINESS" \
    "$OUT/tamarin-image-id.txt" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


proof = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

output = Path(
    sys.argv[2]
)

image_id = Path(
    sys.argv[3]
).read_text(
    encoding="utf-8"
).strip()


verified = (
    proof.get(
        "all_required_lemmas_verified"
    )
    is True
)


payload = {
    "schema_version":
        2,

    "step":
        "STEP7D1_DOCKER_REPRODUCIBLE_FORMAL_MODEL",

    "docker_only_execution":
        True,

    "host_scientific_execution":
        False,

    "proof_network_disabled":
        True,

    "tamarin_version":
        "1.12.0",

    "architecture":
        "linux/amd64",

    "tamarin_image_id":
        image_id,

    "formal_model":
        "formal/tamarin/ranger_authorization_transport.spthy",

    "model_class":
        "LKH_AUTHORIZATION_TRANSPORT_ABSTRACTION",

    "lemma_count":
        11,

    "verified_lemma_count":
        proof[
            "verified_count"
        ],

    "falsified_lemma_count":
        proof[
            "falsified_count"
        ],

    "incomplete_lemma_count":
        proof[
            "incomplete_count"
        ],

    "step7d1_pass":
        verified,

    "scientific_state": (
        "ABSTRACT_AUTHORIZATION_TRANSPORT_MODEL_VERIFIED"
        if verified
        else
        proof[
            "scientific_state"
        ]
    ),

    "full_ranger_formally_verified":
        False,

    "formal_security_claim_ready":
        False,

    "permitted_claim_if_pass": (
        "The STEP7D1 abstract authorization/transport "
        "model was machine-checked using the pinned "
        "offline Docker Tamarin environment under the "
        "explicit symbolic assumptions."
    ),

    "forbidden_claims": [
        "RANGER-IoT is formally verified.",
        "The complete LKH implementation is formally verified.",
        "Multi-epoch replay resistance is formally verified.",
        "Python/C/Cooja and Tamarin are formally equivalent."
    ],

    "remaining_gaps": [
        "Exact LKH tree semantics",
        "Sequential multi-epoch replay/freshness",
        "Tighter compromise timing",
        "Implementation-to-action correspondence"
    ],

    "next_step": (
        "STEP7D2_EXACT_LKH_AND_MULTI_EPOCH_REFINEMENT"
        if verified
        else
        "STEP7D1_ANALYZE_FORMAL_RESULT_BEFORE_MODEL_CHANGE"
    ),
}


output.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


print(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
)
PY


echo
echo "===== 21. VERIFY PREVIOUS IMPLEMENTED SEMANTICS UNCHANGED ====="

if [ -f "$OUT_FAILED/implemented-semantics-before.sha256" ]; then

    ranger_exec \
        sha256sum \
        -c \
        "$OUT_FAILED/implemented-semantics-before.sha256"

    echo "IMPLEMENTED_PROTOCOL_SOURCES_UNCHANGED=PASS"

else

    echo "WARNING:"
    echo "No STEP25 semantic baseline found."
    echo "Creating a new Docker-generated baseline."


    ranger_exec \
        sha256sum \
        src/ranger_iot/group.py \
        src/ranger_iot/protocols/lkh.py \
        src/ranger_iot/ranger/capsule.py \
        src/ranger_iot/ranger/static_protocol.py \
        src/ranger_iot/ranger/recovery_protocol.py \
        src/ranger_iot/ranger/adaptive_protocol.py \
        src/ranger_iot/ranger/adaptive_v2_protocol.py \
        src/ranger_iot/ranger/rs_codec.py \
        > "$OUT/implemented-semantics.sha256"

fi


echo
echo "===== 22. DOCKER-ONLY PROJECT CI ====="

#
# run.sh is permitted as a host orchestration entry point only because
# RANGER-IoT's standard workflow is Docker-first.
#
# We record its content hash using the ranger container before use.
#

ranger_exec \
    sha256sum \
    run.sh \
    > "$OUT/run-sh.sha256"


set +e

./run.sh check \
    > "$OUT/core-ci.log" \
    2>&1

CI_RC=$?

set -e


echo "CI_RC=$CI_RC"


if [ "$CI_RC" -ne 0 ]; then
    echo "CORE_CI=FAIL"
    exit "$CI_RC"
fi


echo "CORE_CI=PASS"


echo
echo "===== 23. FINAL DOCKER-ONLY POLICY AUDIT ====="

ranger_python - \
    "$READINESS" \
    "$TAMARIN_DIR/toolchain.lock.json" \
    "$OUT/tamarin-runtime-offline.log" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


readiness = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

lock = json.loads(
    Path(sys.argv[2]).read_text(
        encoding="utf-8"
    )
)

runtime = Path(
    sys.argv[3]
).read_text(
    encoding="utf-8",
    errors="replace",
)


checks = {
    "docker_only":
        readiness.get(
            "docker_only_execution"
        )
        is True,

    "no_host_science":
        readiness.get(
            "host_scientific_execution"
        )
        is False,

    "proof_offline":
        readiness.get(
            "proof_network_disabled"
        )
        is True,

    "lock_offline":
        lock.get(
            "proof_execution_network"
        )
        == "none",

    "runtime_contract":
        "OFFLINE_TAMARIN_RUNTIME_CONTRACT=PASS"
        in runtime,

    "tamarin_1_12":
        "1.12"
        in runtime,

    "source_fallback_forbidden":
        lock.get(
            "source_build_fallback"
        )
        is False,
}


for name, passed in checks.items():
    print(
        f"{name:32s}",
        "PASS"
        if passed
        else "FAIL",
    )


if not all(checks.values()):
    raise SystemExit(
        "Final Docker-only policy audit failed"
    )


print()
print(
    "FINAL_DOCKER_ONLY_POLICY_AUDIT=PASS"
)
PY


echo
echo "===== 24. FINAL EVIDENCE MANIFEST — INSIDE DOCKER ====="

ranger_exec \
    bash -lc "
      set -euo pipefail

      cd /workspace

      find '$OUT' \
        -type f \
        ! -name '*.tar.gz' \
        ! -name '*.tar.gz.sha256' \
        ! -name 'step7d1r-final-evidence.sha256' \
        ! -name 'step7d1r-final-evidence-verify.log' \
        -print0 \
      | sort -z \
      | xargs -0 sha256sum \
      > '$OUT/step7d1r-final-evidence.sha256'

      sha256sum \
        -c \
        '$OUT/step7d1r-final-evidence.sha256' \
        > '$OUT/step7d1r-final-evidence-verify.log'
    "


echo "EVIDENCE_MANIFEST=PASS"


echo
echo "===== 25. PACKAGE EVIDENCE — INSIDE DOCKER ====="

ranger_exec \
    bash -lc "
      set -euo pipefail

      cd /workspace

      rm -f \
        '$OUT/step7d1r-final-evidence.tar.gz' \
        '$OUT/step7d1r-final-evidence.tar.gz.sha256'

      tar \
        --exclude='*.tar.gz' \
        --exclude='*.tar.gz.sha256' \
        -czf /tmp/step7d1r-final-evidence.tar.gz \
        '$OUT'

      tar \
        -tzf \
        /tmp/step7d1r-final-evidence.tar.gz \
        >/dev/null

      cp \
        /tmp/step7d1r-final-evidence.tar.gz \
        '$OUT/step7d1r-final-evidence.tar.gz'

      sha256sum \
        '$OUT/step7d1r-final-evidence.tar.gz' \
        > '$OUT/step7d1r-final-evidence.tar.gz.sha256'

      sha256sum \
        -c \
        '$OUT/step7d1r-final-evidence.tar.gz.sha256'

      tar \
        -tzf \
        '$OUT/step7d1r-final-evidence.tar.gz' \
        >/dev/null
    "


echo "EVIDENCE_PACKAGE=PASS"


echo
echo "===== 26. FINAL STATUS ====="

ranger_python - \
    "$READINESS" \
    "$PROOF_SUMMARY" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


readiness = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

proof = json.loads(
    Path(sys.argv[2]).read_text(
        encoding="utf-8"
    )
)


print(
    json.dumps(
        readiness,
        indent=2,
        sort_keys=True,
    )
)


print()


if readiness.get(
    "step7d1_pass"
):
    print(
        "STEP7D1R_FINAL=PASS"
    )
else:
    print(
        "STEP7D1R_FINAL=FORMAL_RESULT_REQUIRES_ANALYSIS"
    )


print(
    "VERIFIED_LEMMAS="
    f"{proof['verified_count']}/11"
)

print(
    "FALSIFIED_LEMMAS="
    f"{proof['falsified_count']}"
)

print(
    "INCOMPLETE_LEMMAS="
    f"{proof['incomplete_count']}"
)
PY


echo
echo "===================================================================="
echo "STEP 7D.1-R EXECUTION COMPLETE"
echo
echo "INFRASTRUCTURE:"
echo "  scientific execution           = DOCKER ONLY"
echo "  host Python                    = FORBIDDEN"
echo "  host compiler                  = FORBIDDEN"
echo "  host Tamarin/Maude             = FORBIDDEN"
echo "  Tamarin base image             = OCI DIGEST PINNED"
echo "  Tamarin                        = 1.12.0 BOTTLE PINNED"
echo "  Maude                          = 3.5.1 BOTTLE PINNED"
echo "  Homebrew API resolution        = DISABLED"
echo "  source fallback                = FORBIDDEN"
echo "  proof network                  = NONE"
echo
echo "SCIENTIFIC RESULT:"
echo "  see:"
echo "    $READINESS"
echo
echo "IMPORTANT:"
echo "  full RANGER formal verification remains NOT CLAIMED"
echo
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
