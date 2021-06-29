#!/bin/bash

set -e

#set -x

kubectl delete -f job.yaml || true
kubectl apply -f job.yaml

namespace=testjob
jobName=testjob
timeoutMinuteStartContainer=30s

# this crancky implementation is because '--pod-running-timeout' is not working...

[[ "${jobName}" == "" ]] && exit 0

function yellAndExit1(){
  echo "     Namespace ${namespace} will not be deleted to allow debugging"
  echo "     Attempting to get as much info as possible before exiting 1"
  set -x
  kubectl -n ${namespace} get job/${jobName} -o yaml || true
  kubectl -n ${namespace} describe job/${jobName}  || true
  kubectl -n ${namespace} describe pod -l "job-name=${jobName}" || true
  exit 1
}

# unique identifier for that Job, so we can query ressources for that specific Job without worrying about eventual previous run
jobUid=$(kubectl -n ${namespace} get job/${jobName} -o jsonpath='{.spec.selector.matchLabels.controller-uid}')

echo "     Keep trying to get logs until backoffLimit has been reached (or Job succeed)"
while true; do

  echo "     Wait for the most recently created Pod to not be 'Pending' so logs can be fetched without errors"
  finaldate=$(date -d " ${timeoutMinuteStartContainer} minutes" +'%m/%d %H:%M')
  ready=false
  while [[ $ready != "true" ]]; do
      if [[ "$(date +'%m/%d %H:%M')" > "${finaldate}" ]]; then
          echo "     Err: Timeout waiting for pod to start"
          yellAndExit1
      fi
      echo "... waiting"
      sleep 1
      # check if the Job is finally active, or maybe already done
      jobPodPhases=$(kubectl -n ${namespace} get pod -l controller-uid=${jobUid} --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].status.phase}')
      # pods phase can be 'Pending' 'Running' 'Failed' 'Succeeded'
      [[ ${jobPodPhases} != 'Pending' ]] && ready=true
  done
  echo "     Job is either 'Running' 'Failed' 'Succeeded'"

  echo "     Attempt to fetch logs"
  echo "-----------------------------"
  echo ""
  kubectl -n ${namespace} logs --timestamps=true --follow pod/"$(kubectl -n ${namespace} get pod -l controller-uid=${jobUid} --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].metadata.name}')" || true
  echo ""
  echo "-----------------------------"

  echo "     Job replica is done, checking Job status"
  # not elegant but the safest way to get the overall Job status as .failed and conditions start to get tricky
  # to look into as long as more than backofflimit is not 0
  # give 5s to Kubernetes to have time to update the job status
  #kubectl -n ${namespace} wait --for=condition=complete --timeout=60s job/${jobName} && complete=true || true
  kubectl -n ${namespace} wait --for=condition=complete --timeout=1s job/${jobName} 2> /dev/null && complete=true || true
  if [[ "${complete}" == "true" ]]; then
    echo "     Job final state is 'complete', it ended with sucess"
    exit 0
  else
    if [[ $(kubectl -n ${namespace} get job/${jobName} -o jsonpath='{.spec.backoffLimit}') != $(kubectl -n ${namespace} get job/${jobName} -o jsonpath='{.status.failed}') ]]; then
      echo "     Job replica failed, loop to wait for the next replica"
    else
      echo "     Job has reach its backoffLimit and its final state is not 'complete', it ended with failures"
      yellAndExit1
    fi
  fi
done

