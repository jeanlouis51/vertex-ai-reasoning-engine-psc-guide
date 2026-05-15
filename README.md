# Guide: Deploying Vertex AI Reasoning Engine with PSC and DNS Peering

This guide summarizes the steps required to successfully deploy a Vertex AI Reasoning Engine (Agent Runtime) with Private Service Connect (PSC) interfaces and DNS peering.

## The Problem

When deploying a Reasoning Engine with `psc_interface_config`, you may encounter generic `500 Internal Server Error` or `403 Permission Denied` errors due to missing service agents or permissions. This guide explains how to set up networking, DNS, and proxy configurations to avoid these issues.

---

## Section 1: Networking (Flavor 1 and Flavor 2)

### Flavor 1: Network Attachment in Guest Project (Same-Project)

This is the simpler case where the Network Attachment resides in the same project where you are deploying the Reasoning Engine.

#### Step 1: Enable APIs
Ensure `aiplatform.googleapis.com` and `cloudbuild.googleapis.com` are enabled in your project.

#### Step 2: Grant Permissions to Vertex AI Service Agent
The general Vertex AI service agent needs permission to get the network attachment.

1.  Identify your project number.
2.  Grant `roles/compute.networkUser` to the service agent: `service-PROJECT_NUMBER@gcp-sa-aiplatform.iam.gserviceaccount.com`.

```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:service-PROJECT_NUMBER@gcp-sa-aiplatform.iam.gserviceaccount.com" \
    --role="roles/compute.networkUser"
```

#### Step 3: Deployment Code
```python
import vertexai
from vertexai import agent_engines
from vertexai.agent_engines import aip_types

vertexai.init(project="PROJECT_ID", location="REGION")

deployed_agent = agent_engines.create(
    agent_engine=your_agent,
    requirements="requirements.txt",
    psc_interface_config=aip_types.PscInterfaceConfig(
        network_attachment="projects/PROJECT_ID/regions/REGION/networkAttachments/ATTACHMENT_NAME"
    )
)
```

### Flavor 2: Network Attachment in Host Project (Cross-Project)

This is the case where the Network Attachment resides in a separate Host project (e.g., Shared VPC setup).

#### Step 1: Configure the Host Project
These steps must be performed in the **Host project**.

1.  **Enable the Vertex AI API**:
    ```bash
    gcloud services enable aiplatform.googleapis.com --project=HOST_PROJECT_ID
    ```

2.  **Create the Service Identity** for Vertex AI:
    ```bash
    gcloud beta services identity create --service=aiplatform.googleapis.com --project=HOST_PROJECT_ID
    ```
    This creates: `service-HOST_PROJECT_NUMBER@gcp-sa-aiplatform.iam.gserviceaccount.com`.

3.  **Grant Permissions to the Host Service Agent:**
    Grant it `Compute Network Admin` or a custom role with `compute.networkAttachments.get`, `compute.networkAttachments.update`, and `compute.regionOperations.get`.

    ```bash
    gcloud projects add-iam-policy-binding HOST_PROJECT_ID \
        --member="serviceAccount:service-HOST_PROJECT_NUMBER@gcp-sa-aiplatform.iam.gserviceaccount.com" \
        --role="roles/compute.networkAdmin"
    ```

#### Step 2: Configure Permissions for the Guest Service Agent
In the **Host project**, grant the Guest project's service agent permission to use the network attachment.

1.  Grant `roles/compute.networkUser` to the Guest project's service agent: `service-GUEST_PROJECT_NUMBER@gcp-sa-aiplatform.iam.gserviceaccount.com`.

    ```bash
    gcloud projects add-iam-policy-binding HOST_PROJECT_ID \
        --member="serviceAccount:service-GUEST_PROJECT_NUMBER@gcp-sa-aiplatform.iam.gserviceaccount.com" \
        --role="roles/compute.networkUser"
    ```

#### Step 3: Deployment Code
Same as Flavor 1, but the `network_attachment` URI points to the Host project.

---

## Section 2: DNS Configuration & Limitations

To enable the Reasoning Engine to resolve domains hosted in your target network's Cloud DNS, you must configure DNS peering.

### Deployment Code with DNS Peering

Add `dns_peering_configs` to your `PscInterfaceConfig`:

```python
        psc_interface_config=aip_types.PscInterfaceConfig(
            network_attachment="projects/HOST_PROJECT_ID/regions/REGION/networkAttachments/ATTACHMENT_NAME",
            dns_peering_configs=[
                aip_types.DnsPeeringConfig(
                    domain="your-domain.com.", # Must end with a dot
                    target_project="HOST_PROJECT_ID",
                    target_network="HOST_VPC_NAME"
                )
            ]
        )
```

### Critical Limitation

> [!IMPORTANT]
> When PSC and DNS peering are enabled for a Reasoning Engine, **only domains that resolve to an RFC 1918 private IP address will work**.
>
> RFC 1918 ranges are:
> *   `10.0.0.0/8`
> *   `172.16.0.0/12`
> *   `192.168.0.0/16`
>
> If a domain resolves to a public IP address, the Reasoning Engine will fail to reach it because traffic is forced through the PSC interface which only routes to the private network.

To bypass this limitation and allow the agent to reach public internet URLs, you must use a proxy.

---

## Section 3: Proxy Configuration (Bypassing Limitations)

If your agent needs to access the public internet but is restricted by the PSC interface, you can route traffic through a proxy running within your private network (on an RFC 1918 IP).

### Step 1: Add a Proxy Tool to your Agent

Add a tool like this to your agent's code to route specific requests through the proxy:

```python
def test_proxy_connectivity(target_url: str, proxy_ip: str = "10.1.0.2", port: int = 8080):
    """Test connectivity to a URL via a proxy."""
    proxies = {
        "http": f"http://{proxy_ip}:{port}",
        "https": f"http://{proxy_ip}:{port}",
    }
    try:
        r = requests.get(target_url, proxies=proxies, timeout=5)
        return f"SUCCESS: Reached {target_url} via proxy. Status: {r.status_code}"
    except Exception as e:
        return f"FAILED: Unable to reach {target_url} via proxy. Error: {e}"
```

---

## Troubleshooting

*   **Error 500:** Often implies a failure in validating the PSC configuration or missing API enablement in the host project.
*   **NameResolutionError:** The agent cannot resolve the domain name. Check DNS peering configs and records.
*   **Connection refused vs. Timeout (after resolution):**
    *   **Timeout:** Packets are lost, indicating the network path is not established or no response from target. If it happens after resolving a domain (no NameResolutionError), it means DNS resolution worked but the IP is unreachable.
    *   **Connection refused:** Packets reached the target IP but were rejected. This means the PSC tunnel **is working**.
