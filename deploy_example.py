# deploy_example.py
import vertexai
from vertexai import agent_engines
from vertexai.agent_engines import ModuleAgent
from vertexai.agent_engines import aip_types

# Initialize targeting your environment layout
vertexai.init(
    project="YOUR_GUEST_PROJECT_ID",
    location="YOUR_REGION",
    staging_bucket="gs://YOUR_STAGING_BUCKET"
)

print("Deploying via ModuleAgent pointing to AdkApp agent_runtime...")

try:
    # Configure ModuleAgent to point to your agent instance
    module_pointer_agent = ModuleAgent(
        module_name="app.agent_runtime_app",
        agent_name="agent_runtime",
        register_operations={
            "": ["get_session", "list_sessions", "create_session", "delete_session", "register_feedback"],
            "async": ["async_get_session", "async_list_sessions", "async_create_session", "async_delete_session", "async_add_session_to_memory", "async_search_memory"],
            "stream": ["stream_query"],
            "async_stream": ["async_stream_query", "streaming_agent_run_with_events"]
        }
    )

    # Trigger deployment using the direct module file system pipeline configuration
    deployed_agent = agent_engines.create(
        agent_engine=module_pointer_agent,
        extra_packages=["./app"],
        requirements="./app/app_utils/.requirements.txt", # Path to your requirements
        psc_interface_config=aip_types.PscInterfaceConfig(
            network_attachment="projects/YOUR_HOST_PROJECT_ID/regions/YOUR_REGION/networkAttachments/YOUR_NETWORK_ATTACHMENT_NAME",
            dns_peering_configs=[
                aip_types.DnsPeeringConfig(
                    domain="your-domain.com.", # Must end with a dot
                    target_project="YOUR_HOST_PROJECT_ID",
                    target_network="YOUR_HOST_VPC_NAME"
                )
            ]
        )
    )
    
    print("\n[SUCCESS] Enterprise Agent Deployed!")
    print(f"New Resource Path: {deployed_agent.resource_name}")
    print(f"NEW ID TO COPY: {deployed_agent.name}")

except Exception as e:
    print(f"\n[ERROR] Enterprise deployment failed: {e}")
