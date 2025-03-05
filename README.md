# k8s-mcp
## Kubernetes Monitor

A Python-based Model Context Protocol (MCP) tool for Kubernetes clusters that exposes a comprehensive API to retrieve cluster information and diagnose issues.

## Installation

### Prerequisites

- Python 3.8+
- Access to a Kubernetes cluster (via kubeconfig or in-cluster configuration)
- Required Python packages (see `dependencies` in `pyproject.toml`)
- uv - https://github.com/astral-sh/uv

```bash
# To install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
# Clone the repository
git clone git@github.com:vlttnv/k8s-mcp.git
cd k8s-mcp

# Install dependencies
uv venv
source .venv/bin/activate
uv sync
```

If using Claude configure open your Claude for Desktop App configuration at ~/Library/Application Support/Claude/claude_desktop_config.json in a text editor. Make sure to create the file if it doesn’t exist.

```bash
code ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

```json
{
    "mcpServers": {
        "k8s-mcp": {
            "command": "uv",
            "args": [
                "--directory",
                "/ABSOLUTE/PATH/TO/PARENT/FOLDER/k8s-mcp",
                "run",
                "server.py"
            ]
        }
    }
}
```

> You may need to put the full path to the uv executable in the command field. You can get this by running which uv on MacOS/Linux or where uv on Windows.

## Configuration

The application automatically tries two methods to connect to your Kubernetes cluster:

1. **Kubeconfig File**: Uses your local kubeconfig file (typically located at `~/.kube/config`)
2. **In-Cluster Configuration**: If running inside a Kubernetes pod, uses the service account token

No additional configuration is required if your kubeconfig is properly set up or if you're running inside a cluster with appropriate RBAC permissions.

## Usage

### Examples
Here are some useful example prompts you can ask Claude about your Kubernetes cluster and its resources:

#### General Cluster Status
- "What's the overall health of my cluster?"
- "Show me all namespaces in my cluster"
- "What nodes are available in my cluster and what's their status?"
- "How is resource utilization across my nodes?"

#### Pods and Deployments
- "List all pods in the production namespace"
- "Are there any pods in CrashLoopBackOff state?"
- "Show me pods with high restart counts"
- "List all deployments across all namespaces"
- "What deployments are failing to progress?"

#### Debugging Issues
- "Why is my pod in the staging namespace failing?"
- "Get the YAML configuration for the service in the production namespace"
- "Show me recent events in the default namespace"
- "Are there any pods stuck in Pending state?"
- "What's causing ImagePullBackOff errors in my cluster?"

#### Resource Management
- "Show me the resource consumption of nodes in my cluster"
- "Are there any orphaned resources I should clean up?"
- "List all services in the production namespace"
- "Compare resource requests between staging and production"

#### Specific Resource Inspection
- "Show me the config for the coredns deployment in kube-system"
- "Get details of the reverse-proxy service in staging"
- "What containers are running in the pod xyz?"
- "Show me the logs for the failing pod"

## API Reference

### Namespaces

- `get_namespaces()`: List all available namespaces in the cluster

### Pods

- `list_pods(namespace=None)`: List all pods, optionally filtered by namespace
- `failed_pods()`: List all pods in Failed or Error state
- `pending_pods()`: List all pods in Pending state with reasons
- `high_restart_pods(restart_threshold=5)`: Find pods with restart counts above threshold

### Nodes

- `list_nodes()`: List all nodes and their status
- `node_capacity()`: Show available capacity on all nodes

### Deployments & Services

- `list_deployments(namespace=None)`: List all deployments
- `list_services(namespace=None)`: List all services
- `list_events(namespace=None)`: List all events

### Resource Management

- `orphaned_resources()`: List resources without owner references
- `get_resource_yaml(namespace, resource_type, resource_name)`: Get YAML configuration for a specific resource

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
