#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-flash555588/ai-probe-router}"
WORKFLOW="${WORKFLOW:-ci.yml}"
REF="${REF:-main}"
OUTPUT_DIR="${OUTPUT_DIR:-.artifacts/baseline-capture}"
ARTIFACT="${ARTIFACT:-native-validation-reports}"
REPORT_SUBDIR="${REPORT_SUBDIR:-validation/reports/audio}"
BASELINE_OUTPUT="${BASELINE_OUTPUT:-validation/native-baseline.json}"
RUN_ID="${RUN_ID:-}"

need_tool() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required tool: $1" >&2
    exit 1
  fi
}

need_tool gh
need_tool jq

gh auth status --hostname github.com >/dev/null

mkdir -p "$OUTPUT_DIR"

if [[ -z "$RUN_ID" ]]; then
  before="$(gh run list --repo "$REPO" --workflow "$WORKFLOW" --branch "$REF" --limit 1 --json databaseId --jq '.[0].databaseId // ""')"
  gh workflow run "$WORKFLOW" --repo "$REPO" --ref "$REF"
  echo "triggered $WORKFLOW on $REPO@$REF; waiting for run id..."
  for _ in {1..30}; do
    sleep 5
    RUN_ID="$(
      gh run list --repo "$REPO" --workflow "$WORKFLOW" --branch "$REF" --limit 5 --json databaseId |
        jq -r --arg before "$before" '[.[] | select((.databaseId | tostring) != $before)][0].databaseId // ""'
    )"
    if [[ -n "$RUN_ID" ]]; then
      break
    fi
  done
fi

if [[ -z "$RUN_ID" ]]; then
  echo "failed to find workflow run id" >&2
  exit 1
fi

echo "watching workflow run $RUN_ID"
gh run watch "$RUN_ID" --repo "$REPO" || true

run_json="$(gh run view "$RUN_ID" --repo "$REPO" --json conclusion,databaseId,headSha,status,url)"
status="$(jq -r '.status' <<<"$run_json")"
conclusion="$(jq -r '.conclusion // ""' <<<"$run_json")"
commit_sha="$(jq -r '.headSha' <<<"$run_json")"
run_url="$(jq -r '.url' <<<"$run_json")"

if [[ "$status" != "completed" ]]; then
  echo "workflow run $RUN_ID is not completed (status=$status conclusion=$conclusion)" >&2
  exit 1
fi
if [[ "$conclusion" != "success" ]]; then
  echo "workflow run $RUN_ID did not succeed (status=$status conclusion=$conclusion)" >&2
  exit 1
fi

rm -rf "$OUTPUT_DIR/$ARTIFACT"
gh run download "$RUN_ID" --repo "$REPO" --name "$ARTIFACT" --dir "$OUTPUT_DIR/$ARTIFACT"

summary="$OUTPUT_DIR/$ARTIFACT/$REPORT_SUBDIR/summary.json"
if [[ ! -f "$summary" ]]; then
  artifact_subdir="${REPORT_SUBDIR#validation/reports/}"
  summary="$OUTPUT_DIR/$ARTIFACT/$artifact_subdir/summary.json"
fi
if [[ ! -f "$summary" ]]; then
  echo "downloaded artifact is missing expected summary: $summary" >&2
  exit 1
fi

generated_at_utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

cat <<EOF
Baseline capture downloaded.

Run:
  $run_url

Next step:
  python scripts/kicad_native_baseline_create.py \\
    --summary "$summary" \\
    --output "$BASELINE_OUTPUT" \\
    --repo "$REPO" \\
    --workflow "$WORKFLOW" \\
    --job native-kicad \\
    --artifact "$ARTIFACT" \\
    --report-subdir "$REPORT_SUBDIR" \\
    --commit-sha "$commit_sha" \\
    --run-url "$run_url" \\
    --generated-at-utc "$generated_at_utc"
EOF
