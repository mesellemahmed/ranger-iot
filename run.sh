#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_ROOT}"

case "$(uname -s)" in
  Linux*)
    default_uid="$(id -u)"
    default_gid="$(id -g)"
    ;;
  *)
    default_uid="1000"
    default_gid="1000"
    ;;
esac

export HOST_UID="${HOST_UID:-${default_uid}}"
export HOST_GID="${HOST_GID:-${default_gid}}"

COOJA_DIR="${PROJECT_ROOT}/experiments/cooja"
COOJA_COMPOSE="${COOJA_DIR}/compose.yaml"
EVIDENCE_DIR="${PROJECT_ROOT}/experiments/evidence"


compose() {
  docker compose "$@"
}


host_python() {
  if command -v python >/dev/null 2>&1; then
    python "$@"
  elif command -v python3 >/dev/null 2>&1; then
    python3 "$@"
  else
    echo "ERROR: Python is required for the current Cooja orchestration helpers." >&2
    return 127
  fi
}


cooja_script() {
  local script="$1"
  shift
  host_python "${COOJA_DIR}/scripts/${script}" "$@"
}


build() {
  echo "[run] Building ranger-iot:dev"
  compose build --pull
}


run_ci() {
  echo "[run] Running CI checks in Docker"
  compose run --rm ranger bash ./scripts/ci.sh
}


doctor() {
  local failed=0

  echo "============================================================"
  echo "RANGER-IoT environment doctor"
  echo "============================================================"

  printf "%-24s" "Git"
  if git --version; then
    :
  else
    failed=1
  fi

  printf "%-24s" "Docker"
  if docker --version; then
    :
  else
    failed=1
  fi

  printf "%-24s" "Docker Compose"
  if docker compose version; then
    :
  else
    failed=1
  fi

  printf "%-24s" "Docker daemon"
  if docker info >/dev/null 2>&1; then
    echo "PASS"
  else
    echo "FAIL"
    failed=1
  fi

  printf "%-24s" "Host Python"
  if command -v python >/dev/null 2>&1; then
    python --version
  elif command -v python3 >/dev/null 2>&1; then
    python3 --version
  else
    echo "NOT FOUND — simulator CI still works; Cooja helper commands need Python"
  fi

  printf "%-24s" "Main Compose"
  if docker compose config >/dev/null 2>&1; then
    echo "PASS"
  else
    echo "FAIL"
    failed=1
  fi

  printf "%-24s" "Cooja Compose"
  if docker compose -f "${COOJA_COMPOSE}" config >/dev/null 2>&1; then
    echo "PASS"
  else
    echo "FAIL"
    failed=1
  fi

  printf "%-24s" "Contiki-NG submodule"
  if [ -d third_party/contiki-ng/.git ] || \
     git ls-files --stage third_party/contiki-ng | grep -q '^160000 '; then
    echo "PRESENT"
  else
    echo "MISSING"
    failed=1
  fi

  echo
  echo "Contiki-NG status:"
  git -C third_party/contiki-ng status --short 2>/dev/null || true

  echo
  if [ "${failed}" -eq 0 ]; then
    echo "DOCTOR: PASS"
  else
    echo "DOCTOR: FAIL"
    return 1
  fi
}


show_results() {
  echo "============================================================"
  echo "RANGER-IoT scientific artifacts"
  echo "============================================================"

  echo
  echo "Simulator campaigns:"
  if [ -d experiments/results ]; then
    find experiments/results \
      -mindepth 1 \
      -maxdepth 1 \
      -type d \
      -printf '  %f\n' \
      | sort
  fi

  echo
  echo "Cooja campaigns:"
  if [ -d experiments/cooja/results ]; then
    find experiments/cooja/results \
      -mindepth 1 \
      -maxdepth 1 \
      -type d \
      -printf '  %f\n' \
      | sort
  fi

  echo
  echo "Reproducibility evidence:"
  if [ -d "${EVIDENCE_DIR}" ]; then
    ls -1 "${EVIDENCE_DIR}" | sed 's/^/  /'
  else
    echo "  not found"
  fi
}


evidence_command() {
  local action="${1:-help}"

  case "${action}" in
    list)
      ls -la "${EVIDENCE_DIR}"
      ;;

    sample)
      echo "[evidence] Verifying first 20 registered artifacts"
      head -20 "${EVIDENCE_DIR}/CHECKSUMS.sha256" | sha256sum -c -
      ;;

    verify)
      echo "[evidence] Verifying complete checksum registry"
      echo "[evidence] This may take some time."
      sha256sum -c "${EVIDENCE_DIR}/CHECKSUMS.sha256"
      ;;

    manifest)
      cat "${EVIDENCE_DIR}/evidence-manifest.json"
      ;;

    *)
      echo "Usage:"
      echo "  ./run.sh evidence list"
      echo "  ./run.sh evidence sample"
      echo "  ./run.sh evidence verify"
      echo "  ./run.sh evidence manifest"
      return 2
      ;;
  esac
}


cooja_command() {
  local area="${1:-help}"
  local action="${2:-}"

  case "${area}" in
    check)
      cooja_script run_compose_smoke.py
      ;;

    gui)
      case "${action:-start}" in
        start)
          cooja_script gui_control.py start
          ;;
        stop)
          cooja_script gui_control.py stop
          ;;
        status)
          cooja_script gui_control.py status
          ;;
        logs)
          cooja_script gui_control.py logs
          ;;
        *)
          echo "Usage: ./run.sh cooja gui [start|stop|status|logs]"
          return 2
          ;;
      esac
      ;;

    core)
      case "${action}" in
        build)
          cooja_script build_ranger_core.py
          ;;
        prepare)
          cooja_script prepare_ranger_core_scenario.py
          ;;
        run)
          cooja_script run_ranger_core_headless.py
          ;;
        gui)
          cooja_script run_ranger_gui.py
          ;;
        *)
          echo "Usage: ./run.sh cooja core [build|prepare|run|gui]"
          return 2
          ;;
      esac
      ;;

    rpl)
      case "${action}" in
        generate)
          cooja_script generate_ranger_rpl_line_scenario.py
          ;;
        build)
          cooja_script build_ranger_rpl_core.py
          ;;
        run)
          cooja_script run_ranger_rpl_line_headless.py
          ;;
        gui)
          cooja_script run_ranger_rpl_line_gui.py
          ;;
        *)
          echo "Usage: ./run.sh cooja rpl [generate|build|run|gui]"
          return 2
          ;;
      esac
      ;;

    *)
      cat <<'HELP'
Cooja commands:

  ./run.sh cooja check

  ./run.sh cooja gui start
  ./run.sh cooja gui stop
  ./run.sh cooja gui status
  ./run.sh cooja gui logs

  ./run.sh cooja core build
  ./run.sh cooja core prepare
  ./run.sh cooja core run
  ./run.sh cooja core gui

  ./run.sh cooja rpl generate
  ./run.sh cooja rpl build
  ./run.sh cooja rpl run
  ./run.sh cooja rpl gui
HELP
      ;;
  esac
}


usage() {
  cat <<'HELP'
RANGER-IoT
Resilient Adaptive Network Group Epoch Rekeying

Usage:
  ./run.sh <command>

Core:
  help                  Show this help
  doctor                Validate the execution environment
  build                 Build the Python research image
  check                 Run the complete Python CI gate
  test                  Run tests with branch coverage
  lint                  Run Ruff lint and formatting checks
  typecheck             Run MyPy strict checking
  shell                 Open the Python research container
  ps                    Show project containers
  down                  Stop project containers
  clean                 Remove disposable Docker runtime resources

Scientific artifacts:
  results               Show available result campaigns
  evidence list         Show reproducibility evidence
  evidence sample       Verify first 20 registered checksums
  evidence verify       Verify the complete checksum registry
  evidence manifest     Display the evidence manifest

Cooja:
  cooja check
  cooja gui <start|stop|status|logs>
  cooja core <build|prepare|run|gui>
  cooja rpl <generate|build|run|gui>

Compatibility aliases:
  cooja-check
  cooja-gui
  cooja-gui-stop
  cooja-gui-status
  cooja-gui-logs
  cooja-core-build
  cooja-ranger-prepare
  cooja-ranger-core
  cooja-ranger-gui
  cooja-rpl-line-generate
  cooja-rpl-line-build
  cooja-rpl-line
  cooja-rpl-line-gui

Running ./run.sh without arguments executes the complete Python CI gate.
HELP
}


command="${1:-all}"

case "${command}" in
  help|-h|--help)
    usage
    ;;

  doctor)
    doctor
    ;;

  all)
    build
    run_ci
    ;;

  build)
    build
    ;;

  test)
    compose run --rm ranger \
      pytest \
      --cov=ranger_iot \
      --cov-branch \
      --cov-report=term-missing
    ;;

  lint)
    compose run --rm ranger \
      bash -lc 'ruff check src tests && ruff format --check src tests'
    ;;

  typecheck)
    compose run --rm ranger mypy src
    ;;

  check)
    run_ci
    ;;

  shell)
    compose run --rm ranger bash
    ;;

  ps)
    compose ps -a
    ;;

  down)
    compose down --remove-orphans
    ;;

  clean)
    echo "[run] Removing disposable Docker runtime resources."
    echo "[run] Scientific result directories are not deleted."
    compose down --remove-orphans --volumes
    docker image rm ranger-iot:dev >/dev/null 2>&1 || true
    ;;

  results)
    show_results
    ;;

  evidence)
    evidence_command "${2:-help}"
    ;;

  cooja)
    cooja_command "${2:-help}" "${3:-}"
    ;;


  # -----------------------------------------------------------------
  # Compatibility aliases
  # -----------------------------------------------------------------

  cooja-check)
    cooja_script run_compose_smoke.py
    ;;

  cooja-gui)
    cooja_script gui_control.py start
    ;;

  cooja-gui-stop)
    cooja_script gui_control.py stop
    ;;

  cooja-gui-status)
    cooja_script gui_control.py status
    ;;

  cooja-gui-logs)
    cooja_script gui_control.py logs
    ;;

  cooja-core-build)
    cooja_script build_ranger_core.py
    ;;

  cooja-ranger-prepare)
    cooja_script prepare_ranger_core_scenario.py
    ;;

  cooja-ranger-core)
    cooja_script run_ranger_core_headless.py
    ;;

  cooja-ranger-gui)
    cooja_script run_ranger_gui.py
    ;;

  cooja-rpl-line-generate)
    cooja_script generate_ranger_rpl_line_scenario.py
    ;;

  cooja-rpl-line-build)
    cooja_script build_ranger_rpl_core.py
    ;;

  cooja-rpl-line)
    cooja_script run_ranger_rpl_line_headless.py
    ;;

  cooja-rpl-line-gui)
    cooja_script run_ranger_rpl_line_gui.py
    ;;

  *)
    echo "Unknown command: ${command}" >&2
    echo >&2
    usage >&2
    return 2 2>/dev/null || exit 2
    ;;
esac
