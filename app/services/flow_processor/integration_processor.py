"""
Integration processor module for handling integration nodes in flows.
Processes HTTP and MQTT integrations and records execution history.
"""

import json
import logging
import time
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.integration import Integration
from app.models.integration_history import IntegrationHistory
from app.services.integrations import send_http_request, send_mqtt_message

logger = logging.getLogger(__name__)


async def process_integration_node(
    db: Session,
    node: Dict[str, Any],
    payload: Dict[str, Any],
    flow_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process an integration node in a flow.

    Args:
        db: Database session
        node: The integration node configuration
        payload: The data payload to process
        flow_id: Optional ID of the parent flow for tracking history

    Returns:
        Dict containing the integration processing results
    """
    # Initialize status to handle cases where it might not get set later
    status = "error"  # Default to error, will be overwritten on success

    # Try to get the integration ID from multiple possible field names
    integration_id = None
    node_data = node.get("data", {})

    # Check different possible field names for integration ID
    for id_field in ["integrationId", "entityId", "id"]:
        if id_field in node_data:
            integration_id = node_data.get(id_field)
            print(
                f"INTEGRATION PROCESSOR: Found integration ID {integration_id} via field {id_field}"
            )
            break

    if not integration_id:
        print("INTEGRATION PROCESSOR: Error - Missing integration ID in node data")
        return {
            "integration_result": {"status": "error", "error": "missing_integration_id"}
        }

    # Convert to int if it's a string number
    try:
        if isinstance(integration_id, str) and integration_id.isdigit():
            integration_id = int(integration_id)
    except (ValueError, TypeError):
        pass

    print(f"INTEGRATION PROCESSOR: Looking up integration with ID {integration_id}")
    integration = db.query(Integration).filter(Integration.id == integration_id).first()

    if not integration:
        print(
            f"INTEGRATION PROCESSOR: Error - Integration with ID {integration_id} not found"
        )
        logger.error(f"Integration with ID {integration_id} not found")
        return {
            "integration_result": {"status": "error", "error": "integration_not_found"}
        }

    print(
        f"INTEGRATION PROCESSOR: Found integration '{integration.name}' with ID {integration_id}"
    )

    # Create integration history record
    start_time = time.time()
    integration_history = IntegrationHistory(
        integration_id=integration_id,
        flow_id=flow_id,  # Add the flow_id to track which flow executed this integration
        status="running",
        input_data=payload,
    )
    db.add(integration_history)
    db.flush()  # Get the history ID without committing

    try:
        integration_result = None
        print(
            f"INTEGRATION PROCESSOR: Processing integration of type '{integration.type}'"
        )

        if integration.type == "http":
            integration_result = await process_http_integration(integration, payload)
        elif integration.type == "mqtt":
            integration_result = process_mqtt_integration(integration, payload)
        else:
            raise ValueError(f"Unknown integration type: {integration.type}")

        # Calculate execution time
        execution_time = int((time.time() - start_time) * 1000)

        # Ensure integration_result is a dictionary and JSON serializable
        try:
            if integration_result is None:
                integration_result = {"status": "success", "data": None}
            elif not isinstance(integration_result, dict):
                integration_result = {"status": "success", "data": integration_result}

            # Validate by JSON serializing
            json.dumps(integration_result)
        except (TypeError, ValueError, OverflowError) as e:
            print(
                f"INTEGRATION PROCESSOR: Warning - Integration result not serializable: {e}"
            )
            # Convert to a safe format
            integration_result = {
                "status": "success",
                "data": str(integration_result),
                "serialization_warning": f"Original result was converted to string: {e}",
            }

        # Determine status based on result
        if integration_result.get("status") == "error":
            status = "error"

            # For HTTP errors, include the response content in the error message
            if integration.type == "http" and "response_content" in integration_result:
                error_message = integration_result.get("error", "Integration error")
                response_content = integration_result.get("response_content", "")

                # Create a detailed error message with the response content
                error_message = f"{error_message}\nResponse content: {response_content}"

                # Add status code if available
                if "status_code" in integration_result:
                    error_message = f"HTTP Status: {integration_result['status_code']}\n{error_message}"

                print(
                    f"INTEGRATION PROCESSOR: HTTP error in integration: {error_message}"
                )
            else:
                # For non-HTTP errors
                error_message = integration_result.get("error", "Integration error")
                print(f"INTEGRATION PROCESSOR: Error in integration: {error_message}")

            logger.error(f"Error in integration {integration.name}: {error_message}")
        else:
            status = "success"
            error_message = None
            print(
                f"INTEGRATION PROCESSOR: Integration executed successfully in {execution_time}ms"
            )
            logger.info(
                f"Integration {integration.name} executed successfully in {execution_time}ms"
            )

        # Update integration history
        integration_history.status = status
        integration_history.response_data = integration_result
        integration_history.error_message = error_message
        integration_history.execution_time = execution_time

        # check if json is valid
        try:
            json.dumps(integration_history.response_data)
        except (TypeError, ValueError, OverflowError) as e:
            print(
                f"INTEGRATION PROCESSOR: Warning - Integration history response data not serializable: {e}"
            )
            # Convert to a safe format
            integration_history.response_data = {
                "status": "error",
                "data": str("error in response_data"),
                "serialization_warning": f"Original result was converted to string: {e}",
            }

        # Try to save the result
        try:
            db.add(integration_history)
            db.flush()
            print(
                f"INTEGRATION PROCESSOR: Successfully saved integration execution history"
            )
        except Exception as db_error:
            print(f"INTEGRATION PROCESSOR: Could not save to database: {db_error}")
            # Roll back this transaction to avoid cascading errors
            db.rollback()

            # Simplified result that doesn't require database commit
            return {
                "integration_result": {
                    "status": "success",
                    "data": "Executed but result not saved",
                },
                "integration_history_id": integration_history.id,
            }

        return {
            "integration_result": integration_result,
            "integration_history_id": integration_history.id,
        }
    except Exception as e:
        # Calculate execution time
        execution_time = int((time.time() - start_time) * 1000)

        # Update integration history with error
        integration_history.status = "error"
        integration_history.error_message = str(e)
        integration_history.execution_time = execution_time

        status = "error"  # Ensure status is set for the finally block

        print(f"INTEGRATION PROCESSOR: Exception in integration: {str(e)}")
        logger.error(f"Exception in integration {integration.name}: {str(e)}")

        try:
            db.add(integration_history)
            db.flush()
            print(f"INTEGRATION PROCESSOR: Saved error information to history")
        except Exception as db_error:
            print(
                f"INTEGRATION PROCESSOR: Could not save error to database: {db_error}"
            )
            # Roll back to avoid cascading errors
            db.rollback()

        return {
            "integration_result": {"status": "error", "error": str(e)},
            "integration_history_id": integration_history.id,
        }
    finally:
        # update the integration status based on the integration result
        try:
            # Update the integration's status based on this execution
            # Note: This updates the integration's overall status every time it runs
            integration.status = "success" if status == "success" else "error"
            db.commit()
            db.flush()
        except Exception as e:
            print(f"INTEGRATION PROCESSOR: Could not update integration status: {e}")
            db.rollback()


async def process_http_integration(
    integration: Integration, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process an HTTP integration.

    Args:
        integration: The Integration object with HTTP configuration
        payload: The data payload to send

    Returns:
        Dict containing the HTTP request result
    """
    url = integration.config.get("url")
    method = integration.config.get("method", "POST")
    headers = integration.config.get("headers", {})

    return await send_http_request(url, method, payload, headers)


def process_mqtt_integration(
    integration: Integration, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process an MQTT integration.

    Args:
        integration: The Integration object with MQTT configuration
        payload: The data payload to publish

    Returns:
        Dict containing the MQTT publish result
    """
    host = integration.config.get("host")
    port = integration.config.get("port", 1883)
    topic = integration.config.get("topic")
    username = integration.config.get("username")
    password = integration.config.get("password")
    use_ssl = integration.config.get("use_ssl", False)
    ca_cert = integration.config.get("ca_cert")
    client_cert = integration.config.get("client_cert")
    client_key = integration.config.get("client_key")

    return send_mqtt_message(
        host,
        topic,
        payload,
        port,
        username,
        password,
        use_ssl,
        ca_cert,
        client_cert,
        client_key,
    )
