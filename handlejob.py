import os
import sys
import time
from kubernetes import client, watch, config
from kubernetes.client.rest import ApiException
from subprocess import run

from kubernetes.stream import stream


def main():
    job_name = os.environ["JOB_NAME"]
    namespace = os.environ["NAMESPACE"]
    timeout_minute_start_container = int(os.environ["TIMEOUT_MINUTE_START_CONTAINER"])

    print(f"inputs are: \n jobname: {job_name} \n namespace: {namespace} \n timeout: {timeout_minute_start_container}")

    timeout = time.time() + 60 * timeout_minute_start_container

    v1, batch_api = init_k8s_configs()

    job_uid = get_job_uid(batch_api, namespace, job_name)

    print("Keep trying to get logs until backoffLimit has been reached (or Job succeed)")
    while True:
        print("Wait for the most recently created Pod to not be 'Pending' so logs can be fetched without errors")
        pod = client.V1Pod()
        pod_is_ready = False
        # wait until pod switched from 'pending' to one of 'Running' 'Failed' 'Succeeded' states
        while not pod_is_ready and time.time() < timeout:
            pod = get_pod_by_controller_uid(v1, namespace, job_uid)
            if get_pod_phase(pod) != "Pending":
                print("pod is ready")
                pod_is_ready = True
            time.sleep(10)
        if not pod_is_ready:
            print("timed out to start pod")
            yell_and_exit_1()

        print("""
          Job is either 'Running' 'Failed' 'Succeeded'"
          Attempt to fetch logs
          -----------------------------
        """)

        tail_pod_log(v1, pod.metadata.name, pod.metadata.namespace, job_name)

        print("Job replica is done. checking Job status")
        terminate_status = get_pod_terminate_status(pod, job_name)
        pod_name = pod.metadata.name

        if terminate_status == "Completed":
            print("great! we are done")
            copy_output_from_extractor(namespace, pod_name)
            trigger_extractor_container_termination(v1, namespace, pod_name)
            sys.exit(0)
        elif terminate_status == "Error":
            # job is failed, so stopping extractor to bring pod to finalised state
            trigger_extractor_container_termination(v1, namespace, pod_name)
            time.sleep(10)
            # check if we reached limit of failed attempts and now just give up:
            if backoff_limit_is_reached(batch_api, namespace, job_name):
                print("Job has reach its backoffLimit and its final state is not 'complete', it ended with failures")



def init_k8s_configs():
    # config.load_kube_config()  # for local environment
    config.load_incluster_config()

    batch_api = client.BatchV1Api()
    v1 = client.CoreV1Api()
    return v1, batch_api


def get_job_uid(batch_api, namespace, jobname):
    try:
        job = batch_api.read_namespaced_job(jobname, namespace)
        job_uid = job.metadata.labels["controller-uid"]
        print(f"job_uid is {job_uid}")
        return job_uid
    except ApiException as e:
        print("Exception when calling BatchV1Api->read_namespaced_job: %s\n" % e)

def get_pod_by_controller_uid(v1, namespace, job_uid):
    pods = v1.list_namespaced_pod(namespace, label_selector=f'controller-uid={job_uid}')
    newest_pod = sorted(pods.items, key=lambda d: d.metadata.creation_timestamp)[-1]

    return newest_pod

def get_pod_phase(pod):
    return pod.status.phase

def tail_pod_log(v1, pod_name, namespace, container_name=""):
    w = watch.Watch()
    for line in w.stream(v1.read_namespaced_pod_log, name=pod_name, namespace=namespace, container=container_name):
        print(line)

def get_pod_terminate_status(pod, container_matcher):
    container_statuses = pod.status.container_statuses
    for container in container_statuses:
        if container_matcher in container.name:
            job_container_status = container.state.terminated.reason
            print(f"job container status is: {job_container_status}")
            return job_container_status

def copy_output_from_extractor(namespace, pod_name):
    """
    fallback to run with cli, since there is no good ready python client lib for this
    """
    copy_command = f'kubectl23 cp {namespace}/{pod_name}:/job_outputs ./ -c extractor --retries=5'
    run(copy_command)

def trigger_extractor_container_termination(v1, namespace, pod_name):
    exec_command = "rm -rf /tmp/runfile".split()
    resp = stream(v1.connect_get_namespaced_pod_exec,
                  pod_name,
                  namespace,
                  command=exec_command,
                  container='extractor',
                  stderr=True, stdin=False,
                  stdout=True, tty=False)
    print("Response: " + resp)

def backoff_limit_is_reached(batch_api, namespace, job_name):
    job = batch_api.read_namespaced_job(job_name, namespace)
    backoff_limit = job.spec.backoff_limit
    failed_pods = job.status.failed
    return failed_pods > backoff_limit

def yell_and_exit_1(namespace, job_name):
    print("\033[38;5;202mK8S Debug Information:\033[0m")
    print('::group:: [expand]')

    res = run(f'kubectl -n {namespace} get job/{job_name} -o yaml'.split())
    res = run(f'kubectl -n {namespace} describe job/{job_name}'.split())
    res = run(f'kubectl -n {namespace} describe pod -l "job-name={job_name}"')

    print('::endgroup::')
    sys.exit(1)


if __name__ == "__main__":
    main()