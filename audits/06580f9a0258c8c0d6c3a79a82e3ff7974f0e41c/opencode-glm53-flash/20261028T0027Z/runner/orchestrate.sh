#!/bin/zsh
# Orchestrate full audit run: wait for phase A pid, run phase B, merge summary.
set -u
RUNDIR=/tmp/opencode/pg-audit-work/audits/06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c/opencode-glm53-flash
export AUDIT_REPO_ROOT=/tmp/opencode/pg-audit-work
export AUDIT_SEED=2714620565

# wait for phase A (pid from logs) with sanity cap
DEADLINE=$(( $(date +%s) + 7200 ))
while kill -0 "${1:-196744}" 2>/dev/null; do
  if [ "$(date +%s)" -gt "$DEADLINE" ]; then echo "TIMEOUT_WAITING_PHASE_A"; exit 3; fi
  sleep 20
done
tail -6 "$RUNDIR/logs/run_A.log"
grep -q 'results_A.json' "$RUNDIR/logs/run_A.log" || true
ls -la "$RUNDIR/results" || exit 4
python3 - <<'PYEOF'
import json
d = json.load(open("/tmp/opencode/pg-audit-work/audits/06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c/opencode-glm53-flash/results/results_A.json"))
print("phaseA executed", d["executed_total"], "planned", d["planned_total"])
assert d["executed_total"] == d["planned_total"], "phase A incomplete"
PYEOF
if [ $? -ne 0 ]; then echo "PHASE_A_INCOMPLETE"; exit 5; fi

echo "--- phase B ---"
AUDIT_OUT="$RUNDIR/results" AUDIT_PHASE=B python3 "$RUNDIR/runner/run_audit.py" > "$RUNDIR/logs/run_B.log" 2>&1
echo "phaseB exit=$?"
tail -4 "$RUNDIR/logs/run_B.log"

python3 "$RUNDIR/runner/make_summary.py" \
  "$RUNDIR/results/results_A.json" "$RUNDIR/results/results_B.json" \
  "$RUNDIR/results/results.json"
echo "ALL_DONE"
