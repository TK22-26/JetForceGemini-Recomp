#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "usage: $0 OLD_CASE LOOKUP_TABLE PRODUCER UPGRADER" >&2
    exit 2
fi

old_case=$1
lookup_table=$2
producer=$3
upgrader=$4
scan_root=$(mktemp -d /var/tmp/jfg-phase4-plan-scan.XXXXXX)
case "$scan_root" in
    /var/tmp/jfg-phase4-plan-scan.*) ;;
    *) exit 3 ;;
esac
trap 'rm -rf -- "$scan_root"' EXIT

nonce=$(printf '56%.0s' {1..32})
passes=0
for second_ordinal in $(seq 1 64); do
    for second_seed in 0 1 2; do
        run_root="$scan_root/${second_ordinal}-${second_seed}"
        mkdir "$run_root"
        if ! python3 "$upgrader" \
            --input "$old_case" \
            --lookup "$lookup_table" \
            --candidate-ordinals "2,${second_ordinal}" \
            --context-seeds "1,${second_seed}" \
            --output "$run_root/case-input.bin" \
            --plan "$run_root/function-plan.json" >/dev/null 2>&1; then
            continue
        fi
        digest=$(sha256sum "$run_root/case-input.bin" | awk '{print $1}')
        case_id="g2-custom-${digest:0:16}"
        accepted=1
        for repetition in 1 2 3; do
            if ! (cd "$run_root" && "$producer" \
                --g2-evidence-probe "$nonce" overlay-lifecycle \
                private-native-execution --case-id "$case_id" \
                --subject-sha256 "$digest" >/dev/null 2>/dev/null); then
                accepted=0
                break
            fi
        done
        if [[ $accepted -eq 1 ]]; then
            printf 'passing_candidate=%s seed=%s\n' \
                "$second_ordinal" "$second_seed"
            passes=$((passes + 1))
        fi
    done
done
printf 'passing_plan_count=%s\n' "$passes"
