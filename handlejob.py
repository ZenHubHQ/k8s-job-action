import os
import time
from kubernetes import client, watch, config
from kubernetes.client.rest import ApiException


def main():
    job_name = os.environ["JOB_NAME"]
    namespace = os.environ["NAMESPACE"]
    timeout_minute_start_container = int(os.environ["TIMEOUT_MINUTE_START_CONTAINER"])

    print(f"infuts are: \n jobname: {job_name} \n namespace: {namespace} \n timeout: {timeout_minute_start_container}")

    timeout = time.time() + 60 * timeout_minute_start_container

    v1, batch_api = init_k8s_configs()

    job_uid = get_job_uid(batch_api, namespace, job_name)

    print("Keep trying to get logs until backoffLimit has been reached (or Job succeed)")
    while True:
        print("Wait for the most recently created Pod to not be 'Pending' so logs can be fetched without errors")
        pod = client.V1Pod()
        pod_is_ready = False
        # wait until pod switched from 'pending' to one of 'Running' 'Failed' 'Succeeded' states
        while not pod_is_ready or time.time() < timeout:
            pod = get_pod_by_controller_uid(v1, namespace, job_uid)
            if get_pod_phase(pod) != "Pending":
                pod_is_ready = True
            time.sleep(10)
        if not pod_is_ready:
            print("timed out to start pod")
            print("yeild_and_exit....")

        print("""
          Job is either 'Running' 'Failed' 'Succeeded'"
          Attempt to fetch logs
          -----------------------------
        """)

        tail_pod_log(v1, pod.metadata.name, pod.metadata.namespace, job_name)

        print("Job replica is done. checking Job status")

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

if __name__ == "__main__":
    main()