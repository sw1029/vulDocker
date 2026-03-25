#!/usr/bin/env bash

write_permission_artifact_summary() {
  local summary_path="$1"
  local permission_artifact_name="$2"
  shift 2
  local cases=("$@")
  local count="${#cases[@]}"
  local runtime_equivalent="true"
  local recommended_action="none"

  if (( count > 0 )); then
    runtime_equivalent="false"
    recommended_action="unrestricted_docker_rerun"
  fi

  mkdir -p "$(dirname "${summary_path}")"
  {
    printf '{\n'
    printf '  "schema_version": "permission_artifact_summary@0.1",\n'
    printf '  "permission_artifact_name": "%s",\n' "${permission_artifact_name}"
    printf '  "permission_artifact_count": %s,\n' "${count}"
    printf '  "runtime_equivalent_helper_truth_available": %s,\n' "${runtime_equivalent}"
    printf '  "recommended_action": "%s",\n' "${recommended_action}"
    printf '  "permission_artifact_cases": ['
    if (( count > 0 )); then
      for i in "${!cases[@]}"; do
        if (( i > 0 )); then
          printf ', '
        fi
        printf '"%s"' "${cases[$i]}"
      done
    fi
    printf ']\n'
    printf '}\n'
  } > "${summary_path}"
}
