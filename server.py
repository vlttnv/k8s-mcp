"""
Kubernetes Monitoring API Server

This module provides a FastMCP server that exposes Kubernetes monitoring APIs.
It connects to a Kubernetes cluster and provides endpoints to query various
cluster resources including pods, services, deployments, nodes, and events.

Dependencies:
    - kubernetes: Python client for Kubernetes
    - yaml: For YAML serialization
    - FastMCP: Server framework for API endpoints
"""
import yaml
import json
from datetime import datetime
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from mcp.server.fastmcp import FastMCP


# Initialize FastMCP server
mcp = FastMCP("k8s")

# Kubernetes client configuration
try:
    # Try to load from default kubeconfig
    config.load_kube_config()
except Exception:
    # If running inside a pod
    try:
        config.load_incluster_config()
    except Exception as e:
        print(f"Failed to configure Kubernetes client: {e}")
        exit(1)

# Initialize API clients
core_v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()
batch_v1 = client.BatchV1Api()
custom_objects = client.CustomObjectsApi()


@mcp.tool()
async def get_namespaces():
    """
    List all namespaces in the Kubernetes cluster.

    Returns:
        str: JSON string containing an array of namespace objects with fields:
            - name (str): Name of the namespace
            - status (str): Phase of the namespace (Active, Terminating)
            - creation_time (str): Timestamp when namespace was created

    Raises:
        ApiException: If there is an error communicating with the Kubernetes API
    """
    try:
        namespaces = core_v1.list_namespace()
        result = []
        for ns in namespaces.items:
            result.append(
                {
                    "name": ns.metadata.name,
                    "status": ns.status.phase,
                    "creation_time": ns.metadata.creation_timestamp.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if ns.metadata.creation_timestamp
                    else None,
                }
            )
        return json.dumps(result)
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


@mcp.tool()
def list_pods(namespace=None):
    """
    Lists all pods in the specified Kubernetes namespace or across all namespaces.

    Retrieves detailed information about pods including their status, containers,
    and hosting node.

    Args:
        namespace (str, optional): The namespace to filter pods by.
            If None, pods from all namespaces will be returned. Defaults to None.

    Returns:
        str: JSON string containing an array of pod objects with fields:
            - name (str): Name of the pod
            - namespace (str): Namespace where the pod is running
            - phase (str): Current phase of the pod (Running, Pending, etc.)
            - ip (str): Pod IP address
            - node (str): Name of the node running this pod
            - containers (list): List of containers in the pod with their status
            - creation_time (str): Timestamp when pod was created

    Raises:
        ApiException: If there is an error communicating with the Kubernetes API
    """

    try:
        if namespace:
            pods = core_v1.list_namespaced_pod(namespace)
        else:
            pods = core_v1.list_pod_for_all_namespaces()

        result = []
        for pod in pods.items:
            containers = []
            for container in pod.spec.containers:
                containers.append(
                    {
                        "name": container.name,
                        "image": container.image,
                        "ready": any(
                            s.container_id is not None and s.name == container.name
                            for s in pod.status.container_statuses
                        )
                        if pod.status.container_statuses
                        else False,
                    }
                )

            result.append(
                {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "phase": pod.status.phase,
                    "ip": pod.status.pod_ip,
                    "node": pod.spec.node_name,
                    "containers": containers,
                    "creation_time": pod.metadata.creation_timestamp.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if pod.metadata.creation_timestamp
                    else None,
                }
            )
        return json.dumps(result)
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


@mcp.tool()
def list_nodes():
    """List all nodes and their status"""
    try:
        nodes = core_v1.list_node()
        result = []
        for node in nodes.items:
            conditions = {}
            for condition in node.status.conditions:
                conditions[condition.type] = condition.status

            addresses = {}
            for address in node.status.addresses:
                addresses[address.type] = address.address

            # Get capacity and allocatable resources
            capacity = {
                "cpu": node.status.capacity.get("cpu"),
                "memory": node.status.capacity.get("memory"),
                "pods": node.status.capacity.get("pods"),
            }

            allocatable = {
                "cpu": node.status.allocatable.get("cpu"),
                "memory": node.status.allocatable.get("memory"),
                "pods": node.status.allocatable.get("pods"),
            }

            result.append(
                {
                    "name": node.metadata.name,
                    "conditions": conditions,
                    "addresses": addresses,
                    "capacity": capacity,
                    "allocatable": allocatable,
                    "kubelet_version": node.status.node_info.kubelet_version
                    if node.status.node_info
                    else None,
                }
            )
        return json.dumps(result)
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


@mcp.tool()
def list_deployments(namespace=None):
    """
    List deployments with optional namespace filter

    Args:
        namespaces (list, optional): A list of namespace names to filter pods by.
            If None, pods from all namespaces will be returned. Defaults to None.
    """
    try:
        if namespace:
            deployments = apps_v1.list_namespaced_deployment(namespace)
        else:
            deployments = apps_v1.list_deployment_for_all_namespaces()

        result = []
        for deployment in deployments.items:
            result.append(
                {
                    "name": deployment.metadata.name,
                    "namespace": deployment.metadata.namespace,
                    "replicas": deployment.spec.replicas,
                    "available_replicas": deployment.status.available_replicas,
                    "ready_replicas": deployment.status.ready_replicas,
                    "strategy": deployment.spec.strategy.type,
                    "creation_time": deployment.metadata.creation_timestamp.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if deployment.metadata.creation_timestamp
                    else None,
                }
            )
        return json.dumps(result)
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


@mcp.tool()
def list_services(namespace=None):
    """
    List services with optional namespace filter

    Args:
        namespaces (list, optional): A list of namespace names to filter pods by.
            If None, pods from all namespaces will be returned. Defaults to None.
    """
    try:
        if namespace:
            services = core_v1.list_namespaced_service(namespace)
        else:
            services = core_v1.list_service_for_all_namespaces()

        result = []
        for service in services.items:
            ports = []
            for port in service.spec.ports:
                ports.append(
                    {
                        "name": port.name,
                        "port": port.port,
                        "target_port": port.target_port,
                        "protocol": port.protocol,
                        "node_port": port.node_port
                        if hasattr(port, "node_port")
                        else None,
                    }
                )

            result.append(
                {
                    "name": service.metadata.name,
                    "namespace": service.metadata.namespace,
                    "type": service.spec.type,
                    "cluster_ip": service.spec.cluster_ip,
                    "external_ip": service.spec.external_i_ps
                    if hasattr(service.spec, "external_i_ps")
                    else None,
                    "ports": ports,
                    "selector": service.spec.selector,
                    "creation_time": service.metadata.creation_timestamp.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if service.metadata.creation_timestamp
                    else None,
                }
            )
        return json.dumps(result)
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


@mcp.tool()
def list_events(namespace=None):
    """
    List events with optional namespace filter

    Args:
        namespaces (list, optional): A list of namespace names to filter pods by.
            If None, pods from all namespaces will be returned. Defaults to None.
    """
    try:
        if namespace:
            events = core_v1.list_namespaced_event(namespace)
        else:
            events = core_v1.list_event_for_all_namespaces()

        result = []
        for event in events.items:
            result.append(
                {
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "object": f"{event.involved_object.kind}/{event.involved_object.name}",
                    "namespace": event.metadata.namespace,
                    "count": event.count,
                    "first_time": event.first_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    if event.first_timestamp
                    else None,
                    "last_time": event.last_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    if event.last_timestamp
                    else None,
                }
            )
        # Sort by last_time (newest first)
        # TODO: fix issue with sorting
        # result.sort(key=lambda x: x.get("last_time", ""), reverse=True)
        return json.dumps(result)
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


@mcp.tool()
def failed_pods():
    """
    List all pods in Failed or Error state across all namespaces.

    Identifies pods that are in a failed state, including those in CrashLoopBackOff,
    ImagePullBackOff, or other error states. Provides detailed container status
    information to aid in troubleshooting.

    Returns:
        str: JSON string containing an array of failed pod objects with fields:
            - name (str): Name of the pod
            - namespace (str): Namespace where the pod is running
            - phase (str): Current phase of the pod
            - container_statuses (list): Detailed status of each container
              including state, reason, exit codes, and restart counts
            - node (str): Name of the node running this pod
            - message (str): Status message from the pod, if any
            - reason (str): Reason for the current status, if any

    Raises:
        ApiException: If there is an error communicating with the Kubernetes API
    """
    try:
        pods = core_v1.list_pod_for_all_namespaces()
        failed = []

        for pod in pods.items:
            if pod.status.phase in ["Failed", "Error"] or any(
                s.state
                and s.state.waiting
                and s.state.waiting.reason
                in ["CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"]
                for s in pod.status.container_statuses
                if s.state and s.state.waiting
            ):
                container_statuses = []
                if pod.status.container_statuses:
                    for s in pod.status.container_statuses:
                        state = {}
                        if s.state.waiting:
                            state = {
                                "status": "waiting",
                                "reason": s.state.waiting.reason,
                                "message": s.state.waiting.message,
                            }
                        elif s.state.terminated:
                            state = {
                                "status": "terminated",
                                "reason": s.state.terminated.reason,
                                "exit_code": s.state.terminated.exit_code,
                                "message": s.state.terminated.message,
                            }
                        container_statuses.append(
                            {
                                "name": s.name,
                                "state": state,
                                "restart_count": s.restart_count,
                            }
                        )

                failed.append(
                    {
                        "name": pod.metadata.name,
                        "namespace": pod.metadata.namespace,
                        "phase": pod.status.phase,
                        "container_statuses": container_statuses,
                        "node": pod.spec.node_name,
                        "message": pod.status.message if pod.status.message else None,
                        "reason": pod.status.reason if pod.status.reason else None,
                    }
                )

        return json.dumps(failed)
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


@mcp.tool()
def pending_pods():
    """List all pods in Pending state and why they're pending"""
    try:
        pods = core_v1.list_pod_for_all_namespaces()
        pending = []

        for pod in pods.items:
            if pod.status.phase == "Pending":
                # Check for events related to this pod
                events = core_v1.list_namespaced_event(
                    pod.metadata.namespace,
                    field_selector=f"involvedObject.name={pod.metadata.name},involvedObject.kind=Pod",
                )

                pending_reason = "Unknown"
                pending_message = None

                # Get the latest event that might explain why it's pending
                if events.items:
                    latest_event = max(
                        events.items,
                        key=lambda e: e.last_timestamp
                        if e.last_timestamp
                        else datetime.min,
                    )
                    pending_reason = latest_event.reason
                    pending_message = latest_event.message

                pending.append(
                    {
                        "name": pod.metadata.name,
                        "namespace": pod.metadata.namespace,
                        "node": pod.spec.node_name,
                        "reason": pending_reason,
                        "message": pending_message,
                        "creation_time": pod.metadata.creation_timestamp.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        if pod.metadata.creation_timestamp
                        else None,
                    }
                )

        return json.dumps(pending)
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


@mcp.tool()
def high_restart_pods(restart_threshold=5):
    """
    Find pods with high restart counts (>5)

    Args:
        restart_threshold (int, optional): The minimum number of restarts
            required to include a pod in the results. Defaults to 5.
    """

    try:
        pods = core_v1.list_pod_for_all_namespaces()
        high_restart = []

        for pod in pods.items:
            high_restart_containers = []

            if pod.status.container_statuses:
                for status in pod.status.container_statuses:
                    if status.restart_count > restart_threshold:
                        high_restart_containers.append(
                            {
                                "name": status.name,
                                "restart_count": status.restart_count,
                                "ready": status.ready,
                                "image": status.image,
                            }
                        )

            if high_restart_containers:
                high_restart.append(
                    {
                        "name": pod.metadata.name,
                        "namespace": pod.metadata.namespace,
                        "node": pod.spec.node_name,
                        "containers": high_restart_containers,
                    }
                )

        return json.dumps(high_restart)
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


@mcp.tool()
def node_capacity():
    """
    Show available capacity and resource utilization on all nodes.

    Calculates the current resource usage across all nodes, including:
    - Pod count vs. maximum pods per node
    - CPU requests vs. allocatable CPU
    - Memory requests vs. allocatable memory

    The function provides both raw values and percentage utilization to help
    identify nodes approaching resource limits.

    Returns:
        str: JSON string containing an array of node capacity objects with fields:
            - name (str): Name of the node
            - pods (dict): Pod capacity information
              - used (int): Number of pods running on the node
              - capacity (int): Maximum number of pods the node can run
              - percent_used (float): Percentage of pod capacity in use
            - cpu (dict): CPU resource information
              - requested (float): CPU cores requested by pods
              - allocatable (float): CPU cores available on the node
              - percent_used (float): Percentage of CPU capacity in use
            - memory (dict): Memory resource information
              - requested (int): Memory requested by pods in bytes
              - requested_human (str): Human-readable memory requested
              - allocatable (int): Memory available on the node in bytes
              - allocatable_human (str): Human-readable allocatable memory
              - percent_used (float): Percentage of memory capacity in use
            - conditions (dict): Node condition statuses

    Raises:
        ApiException: If there is an error communicating with the Kubernetes API
    """
    try:
        nodes = core_v1.list_node()
        pods = core_v1.list_pod_for_all_namespaces()

        # Group pods by node
        node_pods = {}
        for pod in pods.items:
            if pod.spec.node_name:
                if pod.spec.node_name not in node_pods:
                    node_pods[pod.spec.node_name] = []
                node_pods[pod.spec.node_name].append(pod)

        results = []
        for node in nodes.items:
            # Calculate pod count
            pod_count = len(node_pods.get(node.metadata.name, []))
            max_pods = int(node.status.allocatable.get("pods", 0))

            # Calculate CPU and memory utilization (rough estimate)
            node_pods_list = node_pods.get(node.metadata.name, [])
            cpu_request = 0
            memory_request = 0

            for pod in node_pods_list:
                for container in pod.spec.containers:
                    if container.resources and container.resources.requests:
                        if container.resources.requests.get("cpu"):
                            cpu_str = container.resources.requests.get("cpu")
                            if cpu_str.endswith("m"):
                                cpu_request += int(cpu_str[:-1]) / 1000
                            else:
                                cpu_request += float(cpu_str)

                        if container.resources.requests.get("memory"):
                            mem_str = container.resources.requests.get("memory")
                            # Convert to bytes (rough approximation)
                            if mem_str.endswith("Ki"):
                                memory_request += int(mem_str[:-2]) * 1024
                            elif mem_str.endswith("Mi"):
                                memory_request += int(mem_str[:-2]) * 1024 * 1024
                            elif mem_str.endswith("Gi"):
                                memory_request += int(mem_str[:-2]) * 1024 * 1024 * 1024
                            else:
                                memory_request += int(mem_str)

            # Convert allocatable CPU to cores
            cpu_allocatable = node.status.allocatable.get("cpu", "0")
            if cpu_allocatable.endswith("m"):
                cpu_allocatable = int(cpu_allocatable[:-1]) / 1000
            else:
                cpu_allocatable = float(cpu_allocatable)

            # Convert allocatable memory to bytes
            mem_allocatable = node.status.allocatable.get("memory", "0")
            mem_bytes = 0
            if mem_allocatable.endswith("Ki"):
                mem_bytes = int(mem_allocatable[:-2]) * 1024
            elif mem_allocatable.endswith("Mi"):
                mem_bytes = int(mem_allocatable[:-2]) * 1024 * 1024
            elif mem_allocatable.endswith("Gi"):
                mem_bytes = int(mem_allocatable[:-2]) * 1024 * 1024 * 1024
            else:
                mem_bytes = int(mem_allocatable)

            results.append(
                {
                    "name": node.metadata.name,
                    "pods": {
                        "used": pod_count,
                        "capacity": max_pods,
                        "percent_used": round((pod_count / max_pods) * 100, 2)
                        if max_pods > 0
                        else 0,
                    },
                    "cpu": {
                        "requested": round(cpu_request, 2),
                        "allocatable": round(cpu_allocatable, 2),
                        "percent_used": round((cpu_request / cpu_allocatable) * 100, 2)
                        if cpu_allocatable > 0
                        else 0,
                    },
                    "memory": {
                        "requested": memory_request,
                        "requested_human": format_bytes(memory_request),
                        "allocatable": mem_bytes,
                        "allocatable_human": format_bytes(mem_bytes),
                        "percent_used": round((memory_request / mem_bytes) * 100, 2)
                        if mem_bytes > 0
                        else 0,
                    },
                    "conditions": {
                        cond.type: cond.status for cond in node.status.conditions
                    },
                }
            )

        return json.dumps(results)
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


@mcp.tool()
def orphaned_resources():
    """List resources that might be orphaned (no owner references)"""
    try:
        results = {
            "pods": [],
            "services": [],
            "persistent_volume_claims": [],
            "config_maps": [],
            "secrets": [],
        }

        # Check for orphaned pods
        pods = core_v1.list_pod_for_all_namespaces()
        for pod in pods.items:
            if (
                not pod.metadata.owner_references
                and not pod.metadata.name.startswith("kube-")
                and pod.metadata.namespace != "kube-system"
            ):
                results["pods"].append(
                    {
                        "name": pod.metadata.name,
                        "namespace": pod.metadata.namespace,
                        "creation_time": pod.metadata.creation_timestamp.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        if pod.metadata.creation_timestamp
                        else None,
                    }
                )

        # Check for orphaned services
        services = core_v1.list_service_for_all_namespaces()
        for service in services.items:
            if (
                not service.metadata.owner_references
                and not service.metadata.name.startswith("kube-")
                and service.metadata.namespace != "kube-system"
                and service.metadata.name != "kubernetes"
            ):
                results["services"].append(
                    {
                        "name": service.metadata.name,
                        "namespace": service.metadata.namespace,
                        "creation_time": service.metadata.creation_timestamp.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        if service.metadata.creation_timestamp
                        else None,
                    }
                )

        # Check for orphaned PVCs
        pvcs = core_v1.list_persistent_volume_claim_for_all_namespaces()
        for pvc in pvcs.items:
            if not pvc.metadata.owner_references:
                results["persistent_volume_claims"].append(
                    {
                        "name": pvc.metadata.name,
                        "namespace": pvc.metadata.namespace,
                        "creation_time": pvc.metadata.creation_timestamp.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        if pvc.metadata.creation_timestamp
                        else None,
                    }
                )

        # Check for orphaned ConfigMaps
        config_maps = core_v1.list_config_map_for_all_namespaces()
        for cm in config_maps.items:
            if (
                not cm.metadata.owner_references
                and not cm.metadata.name.startswith("kube-")
                and cm.metadata.namespace != "kube-system"
            ):
                results["config_maps"].append(
                    {
                        "name": cm.metadata.name,
                        "namespace": cm.metadata.namespace,
                        "creation_time": cm.metadata.creation_timestamp.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        if cm.metadata.creation_timestamp
                        else None,
                    }
                )

        # Check for orphaned Secrets
        secrets = core_v1.list_secret_for_all_namespaces()
        for secret in secrets.items:
            if (
                not secret.metadata.owner_references
                and not secret.metadata.name.startswith("kube-")
                and secret.metadata.namespace != "kube-system"
                and not secret.type.startswith("kubernetes.io/")
            ):
                results["secrets"].append(
                    {
                        "name": secret.metadata.name,
                        "namespace": secret.metadata.namespace,
                        "type": secret.type,
                        "creation_time": secret.metadata.creation_timestamp.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        if secret.metadata.creation_timestamp
                        else None,
                    }
                )

        return json.dumps(results)
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


@mcp.tool()
def get_resource_yaml(namespace, resource_type, resource_name):
    """
    Retrieves the YAML configuration for a specified Kubernetes resource.

    Fetches the complete configuration of a resource, which can be useful for
    debugging, documentation, or backup purposes.

    Args:
        namespace (str): The Kubernetes namespace containing the resource.
        resource_type (str): The type of resource to retrieve.
            Supported types: 'pod', 'deployment', 'service', 'configmap',
            'secret', 'job'
        resource_name (str): The name of the specific resource to retrieve.

    Returns:
        str: YAML string representation of the resource configuration.

    Raises:
        ApiException: If there is an error communicating with the Kubernetes API
        ValueError: If an unsupported resource type is specified
    """
    try:
        resource_data = None

        if resource_type == "pod":
            resource_data = core_v1.read_namespaced_pod(resource_name, namespace)
        elif resource_type == "deployment":
            resource_data = apps_v1.read_namespaced_deployment(resource_name, namespace)
        elif resource_type == "service":
            resource_data = core_v1.read_namespaced_service(resource_name, namespace)
        elif resource_type == "configmap":
            resource_data = core_v1.read_namespaced_config_map(resource_name, namespace)
        elif resource_type == "secret":
            resource_data = core_v1.read_namespaced_secret(resource_name, namespace)
        elif resource_type == "job":
            resource_data = batch_v1.read_namespaced_job(resource_name, namespace)
        else:
            return json.dumps(
                {"error": f"Unsupported resource type: {resource_type}"}
            ), 400

        # Convert to dict and then to YAML
        resource_dict = client.ApiClient().sanitize_for_serialization(resource_data)
        yaml_str = yaml.dump(resource_dict, default_flow_style=False)

        return yaml_str
    except ApiException as e:
        return json.dumps({"error": str(e)}), 500


# Helper function to format bytes into human-readable format
def format_bytes(size):
    """
    Format bytes to human readable string.

    Converts a byte value to a human-readable string with appropriate
    units (B, KiB, MiB, GiB, TiB).

    Args:
        size (int): Size in bytes

    Returns:
        str: Human-readable string representation of the size
            (e.g., "2.5 MiB")
    """
    power = 2**10
    n = 0
    power_labels = {0: "B", 1: "KiB", 2: "MiB", 3: "GiB", 4: "TiB"}
    while size > power:
        size /= power
        n += 1
    return f"{round(size, 2)} {power_labels[n]}"


if __name__ == "__main__":
    # # Initialize and run the server
    mcp.run(transport="stdio")
