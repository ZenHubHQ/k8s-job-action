import os
from kubernetes import client, config


def main():
    job_name = os.environ["JOB_NAME"]
    namespace = os.environ["INPUT_NAMESPACE"]
    timeout_minute_start_container = os.environ["TIMEOUT_MINUTE_START_CONTAINER"]
    print(f"infuts are: \n jobname: {job_name} \n namespace: {namespace} \n timeout: {timeout_minute_start_container}")

    v1, batch_api = init_k8s_configs()

    my_output = f"Hello {job_name}"
    print(f"::set-output name=myOutput::{my_output}")

# batch_api = client.BatchV1Api()
# v1 = client.CoreV1Api()



def init_k8s_configs():
    # config.load_kube_config()  # for local environment
    config.load_incluster_config()

    batch_api = client.BatchV1Api()
    v1 = client.CoreV1Api()
    return v1, batch_api

def get_job_uid(batch_api, namespace, jobname):
    print("megaID")

if __name__ == "__main__":
    main()