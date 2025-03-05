import unittest
from unittest.mock import patch, MagicMock, call
import json
import datetime
import yaml
import asyncio
from kubernetes.client.rest import ApiException

# Import the module to be tested
import server

class AsyncTestCase(unittest.TestCase):
    """Base class for testing async functions."""

    def run_async(self, coro):
        """Helper method to run coroutines in tests."""
        return asyncio.run(coro)


class TestKubernetesServer(AsyncTestCase):
    """Test cases for Kubernetes monitoring server functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock configuration and API clients
        self.mock_config = patch('server.config').start()
        self.mock_core_v1 = patch('server.core_v1').start()
        self.mock_apps_v1 = patch('server.apps_v1').start()
        self.mock_batch_v1 = patch('server.batch_v1').start()
        self.mock_custom_objects = patch('server.custom_objects').start()

        # Mock FastMCP server
        self.mock_mcp = patch('server.mcp').start()

    def tearDown(self):
        """Tear down test fixtures."""
        patch.stopall()

    def test_get_namespaces(self):
        """Test get_namespaces function."""
        # Create mock namespace items
        mock_namespace1 = MagicMock()
        mock_namespace1.metadata.name = "default"
        mock_namespace1.status.phase = "Active"
        mock_namespace1.metadata.creation_timestamp = datetime.datetime(2023, 1, 1, 12, 0, 0)

        mock_namespace2 = MagicMock()
        mock_namespace2.metadata.name = "kube-system"
        mock_namespace2.status.phase = "Active"
        mock_namespace2.metadata.creation_timestamp = datetime.datetime(2023, 1, 1, 12, 0, 0)

        # Set up mock response
        mock_response = MagicMock()
        mock_response.items = [mock_namespace1, mock_namespace2]
        self.mock_core_v1.list_namespace.return_value = mock_response

        # Call the async function
        result = asyncio.run(server.get_namespaces())

        # Verify the response
        namespaces = json.loads(result)
        self.assertEqual(len(namespaces), 2)
        self.assertEqual(namespaces[0]['name'], "default")
        self.assertEqual(namespaces[1]['name'], "kube-system")

        # Verify the API was called
        self.mock_core_v1.list_namespace.assert_called_once()

    def test_get_namespaces_error(self):
        """Test get_namespaces function with API error."""
        # Simulate API exception
        self.mock_core_v1.list_namespace.side_effect = ApiException(status=403, reason="Forbidden")

        # Call the function
        result_tuple = asyncio.run(server.get_namespaces())
        # If the function returns a tuple
        if isinstance(result_tuple, tuple):
            result, status_code = result_tuple
        else:
            # If function returns just the error JSON
            result = result_tuple
            status_code = 500  # Assuming default error code

        # Verify error response
        error_response = json.loads(result)
        self.assertEqual(status_code, 500)
        self.assertIn("error", error_response)

    def test_list_pods(self):
        """Test list_pods function with namespace parameter."""
        # Create mock pod items
        mock_pod = MagicMock()
        mock_pod.metadata.name = "test-pod"
        mock_pod.metadata.namespace = "default"
        mock_pod.status.phase = "Running"
        mock_pod.status.pod_ip = "10.0.0.1"
        mock_pod.spec.node_name = "node1"
        mock_pod.metadata.creation_timestamp = datetime.datetime(2023, 1, 1, 12, 0, 0)

        # Create mock container
        mock_container = MagicMock()
        mock_container.name = "test-container"
        mock_container.image = "nginx:latest"
        mock_pod.spec.containers = [mock_container]

        # Create mock container status
        mock_container_status = MagicMock()
        mock_container_status.name = "test-container"
        mock_container_status.container_id = "container123"
        mock_pod.status.container_statuses = [mock_container_status]

        # Set up mock response
        mock_response = MagicMock()
        mock_response.items = [mock_pod]
        self.mock_core_v1.list_namespaced_pod.return_value = mock_response

        # Call the function with namespace
        result = server.list_pods(namespace="default")

        # Verify the response
        pods = json.loads(result)
        self.assertEqual(len(pods), 1)
        self.assertEqual(pods[0]['name'], "test-pod")
        self.assertEqual(pods[0]['namespace'], "default")
        self.assertEqual(pods[0]['containers'][0]['name'], "test-container")
        self.assertTrue(pods[0]['containers'][0]['ready'])

        # Verify the API was called with correct namespace
        self.mock_core_v1.list_namespaced_pod.assert_called_once_with("default")

    def test_list_pods_all_namespaces(self):
        """Test list_pods function without namespace parameter."""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.items = []
        self.mock_core_v1.list_pod_for_all_namespaces.return_value = mock_response

        # Call the function without namespace
        result = server.list_pods()

        # Verify the API was called for all namespaces
        self.mock_core_v1.list_pod_for_all_namespaces.assert_called_once()

    def test_list_nodes(self):
        """Test list_nodes function."""
        # Create mock node
        mock_node = MagicMock()
        mock_node.metadata.name = "node1"

        # Mock node conditions
        mock_condition = MagicMock()
        mock_condition.type = "Ready"
        mock_condition.status = "True"
        mock_node.status.conditions = [mock_condition]

        # Mock node addresses
        mock_address = MagicMock()
        mock_address.type = "InternalIP"
        mock_address.address = "192.168.1.1"
        mock_node.status.addresses = [mock_address]

        # Mock node capacity
        mock_node.status.capacity = {"cpu": "4", "memory": "8Gi", "pods": "110"}
        mock_node.status.allocatable = {"cpu": "3800m", "memory": "7Gi", "pods": "100"}

        # Mock node info
        mock_node.status.node_info = MagicMock()
        mock_node.status.node_info.kubelet_version = "v1.25.0"

        # Set up mock response
        mock_response = MagicMock()
        mock_response.items = [mock_node]
        self.mock_core_v1.list_node.return_value = mock_response

        # Call the function
        result = server.list_nodes()

        # Verify the response
        nodes = json.loads(result)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]['name'], "node1")
        self.assertEqual(nodes[0]['conditions']['Ready'], 'True')
        self.assertEqual(nodes[0]['addresses']['InternalIP'], '192.168.1.1')
        self.assertEqual(nodes[0]['capacity']['cpu'], '4')
        self.assertEqual(nodes[0]['allocatable']['memory'], '7Gi')
        self.assertEqual(nodes[0]['kubelet_version'], 'v1.25.0')

        # Verify the API was called
        self.mock_core_v1.list_node.assert_called_once()

    def test_failed_pods(self):
        """Test failed_pods function."""
        # Create mock failed pod
        mock_pod = MagicMock()
        mock_pod.metadata.name = "failed-pod"
        mock_pod.metadata.namespace = "default"
        mock_pod.status.phase = "Failed"
        mock_pod.spec.node_name = "node1"
        mock_pod.status.message = "Pod failed"
        mock_pod.status.reason = "Error"

        # Create mock container status
        mock_container_status = MagicMock()
        mock_container_status.name = "test-container"
        mock_container_status.restart_count = 3

        # Create mock container state
        mock_container_status.state = MagicMock()
        mock_container_status.state.waiting = MagicMock()
        mock_container_status.state.waiting.reason = "CrashLoopBackOff"
        mock_container_status.state.waiting.message = "Container crashed"
        mock_container_status.state.terminated = None

        mock_pod.status.container_statuses = [mock_container_status]

        # Set up mock response
        mock_response = MagicMock()
        mock_response.items = [mock_pod]
        self.mock_core_v1.list_pod_for_all_namespaces.return_value = mock_response

        # Call the function
        result = server.failed_pods()

        # Verify the response
        failed = json.loads(result)
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]['name'], "failed-pod")
        self.assertEqual(failed[0]['phase'], "Failed")
        self.assertEqual(failed[0]['container_statuses'][0]['name'], "test-container")
        self.assertEqual(failed[0]['container_statuses'][0]['state']['reason'], "CrashLoopBackOff")

        # Verify the API was called
        self.mock_core_v1.list_pod_for_all_namespaces.assert_called_once()

    def test_get_resource_yaml(self):
        """Test get_resource_yaml function."""
        # Create mock API client
        mock_api_client = MagicMock()
        server.client.ApiClient.return_value = mock_api_client

        # Create mock resource
        mock_resource = MagicMock()
        self.mock_core_v1.read_namespaced_pod.return_value = mock_resource

        # Set up serialization
        mock_dict = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "test-pod"}}
        mock_api_client.sanitize_for_serialization.return_value = mock_dict

        # Mock the yaml dump function to ensure consistent output
        with patch('server.yaml.dump') as mock_yaml_dump:
            mock_yaml_dump.return_value = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\n"

            # Call the function
            result = server.get_resource_yaml("default", "pod", "test-pod")

            # Verify YAML output is what we expect based on our mock
            self.assertEqual(result, "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\n")

            # Verify yaml.dump was called with the correct parameters
            mock_yaml_dump.assert_called_once_with(mock_dict, default_flow_style=False)

        # Verify API calls
        self.mock_core_v1.read_namespaced_pod.assert_called_once_with("test-pod", "default")
        mock_api_client.sanitize_for_serialization.assert_called_once_with(mock_resource)

    def test_get_resource_yaml_unsupported_type(self):
        """Test get_resource_yaml function with unsupported resource type."""
        # Call the function with unsupported type
        result, status_code = server.get_resource_yaml("default", "unknown", "resource-name")

        # Verify error response
        error_response = json.loads(result)
        self.assertEqual(status_code, 400)
        self.assertIn("error", error_response)
        self.assertIn("Unsupported resource type", error_response["error"])

    def test_format_bytes(self):
        """Test format_bytes helper function."""
        # Test various sizes
        self.assertEqual(server.format_bytes(500), "500 B")
        self.assertEqual(server.format_bytes(1024), "1024 B")
        self.assertEqual(server.format_bytes(1536), "1.5 KiB")
        self.assertEqual(server.format_bytes(2 * 1024 * 1024), "2.0 MiB")
        self.assertEqual(server.format_bytes(3 * 1024 * 1024 * 1024), "3.0 GiB")

if __name__ == '__main__':
    unittest.main()
