#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
source_directory="${1:-$project_root/upstream/report}"
build_directory="$project_root/.cache/original-report-build"
output_directory="$project_root/output/pdf"
mkdir -p "$build_directory" "$output_directory"
tectonic --untrusted --outdir "$build_directory" "$source_directory/index.tex"
cp "$build_directory/index.pdf" "$output_directory/original-f1tenth-report.pdf"
