#!/usr/bin/env bash
# Walk through a MARC to BIBFRAME job with the Toolbox API: upload, preview,
# download, submit a dry run, check on it, fetch its import report, and list
# recent jobs.
#
#   TOOLBOX_TOKEN=... ./examples/marc-bibframe.sh records.mrc
#
# TOOLBOX_URL is where the Toolbox is mounted, by default
# http://localhost:8080/graph-toolbox (use .../workflows/graph-toolbox behind
# the bluecore-stack proxy). TOOLBOX_TOKEN is an Airflow JWT for the user to
# act as, from Airflow's POST /auth/token. Needs curl and jq.

set -euo pipefail

file=${1:?usage: $0 records.mrc|records.xml}
url=${TOOLBOX_URL:-http://localhost:8080/graph-toolbox}/marc-bibframe-operations
auth="Authorization: Bearer ${TOOLBOX_TOKEN:?set TOOLBOX_TOKEN to an Airflow JWT}"

api() {
  curl --silent --show-error --fail-with-body --header "$auth" "$@"
}

echo "== Upload $file"
upload=$(api --form "file=@$file" "$url/uploads")
jq 'del(.preview_marcxml)' <<<"$upload"
upload_id=$(jq -r .upload_id <<<"$upload")

echo "== Preview (first records as MARC XML)"
jq -r .preview_marcxml <<<"$upload" | head -20

echo "== Full file as MARC XML"
api "$url/uploads/$upload_id/marcxml" --output "$upload_id.xml"
echo "saved $upload_id.xml"

echo "== Submit a dry run"
job=$(api --header "Content-Type: application/json" --data @- "$url/jobs" <<EOF
{
  "upload_id": "$upload_id",
  "duplicate_policy": "skip_report",
  "confirmed_policy": "skip_report",
  "duplicate_report": true,
  "export_to_lsp": false,
  "dry_run": true
}
EOF
)
jq . <<<"$job"
job_id=$(jq -r .job_id <<<"$job")

echo "== Wait for the run to finish"
while :; do
  status=$(api "$url/jobs/$job_id")
  state=$(jq -r .state <<<"$status")
  echo "state: $state"
  [[ $state == queued || $state == running ]] || break
  sleep 5
done
jq . <<<"$status"

if jq -e '.reports | index("import")' <<<"$status" >/dev/null; then
  echo "== Import report"
  api "$url/jobs/$job_id/reports/import"
else
  echo "no import report (the DAG may not write one yet)"
fi

echo "== Most recent jobs"
api "$url/jobs?limit=5" | jq '.jobs[] | {job_id, user_uid, state}'

# To stop a run that hasn't finished:
#   api --request POST "$url/jobs/$job_id/cancel"
# To drop an upload you won't submit:
#   api --request DELETE "$url/uploads/$upload_id"
