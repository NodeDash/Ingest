"""
Device processor module for handling device-triggered flow execution.
Manages execution of flows for specific devices and records execution history.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.flow import Flow
from app.models.flow_history import FlowHistory
from app.models.label_history import LabelHistory
from app.services.flow_processor.flow_engine import process_flow

logger = logging.getLogger(__name__)


async def execute_flow_for_device(
    db: Session,
    flow: Flow,
    device_id: int,
    device_eui: str,
    payload: Dict[str, Any],
    label_ids: List[int],
) -> Dict[str, Any]:
    """
    Execute a flow for a specific device.

    Args:
        db: Database session
        flow: The Flow object to execute
        device_id: Device ID
        device_eui: Device EUI
        payload: Data payload
        label_ids: List of label IDs associated with the device

    Returns:
        Dict containing the flow execution results
    """
    print(
        f"FLOW PROCESSOR: Starting execution for device {device_id} ({device_eui}) in flow {flow.id}"
    )

    # Create flow history record
    flow_start_time = time.time()
    flow_history = FlowHistory(
        flow_id=flow.id,
        status="running",
        trigger_source="device_uplink",
        source_id=device_id,
        start_time=datetime.utcnow(),
    )
    db.add(flow_history)
    db.flush()  # Get ID without committing

    # Process labels if needed
    if label_ids:
        try:
            # Create label history records for labels involved in this flow
            for label_id in label_ids:
                label_history = LabelHistory(
                    label_id=label_id,
                    flow_id=flow.id,  # Add flow_id to track which flow used this label
                    event="flow_execution",
                    status="success",
                    data={
                        "flow_id": flow.id,
                        "flow_name": flow.name,
                        "device_id": device_id,
                        "device_eui": device_eui,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
                db.add(label_history)
            db.flush()
            print(
                f"FLOW PROCESSOR: Created {len(label_ids)} label history records for flow execution"
            )
        except Exception as e:
            print(f"FLOW PROCESSOR: Failed to create label history records: {str(e)}")
            # Continue execution despite label history errors
            pass

    # Find trigger nodes (typically device or label nodes that initiate the flow)
    trigger_nodes = []
    print(
        f"FLOW PROCESSOR: Looking for trigger nodes matching device ID {device_id} or labels {label_ids}"
    )

    for node in flow.nodes:
        node_id = node.get("id", "unknown")
        node_type = node.get("type")
        node_data = node.get("data", {})

        print(f"FLOW PROCESSOR: Examining node {node_id} of type {node_type}")
        print(f"FLOW PROCESSOR: Node data: {json.dumps(node_data)}")

        if node_type in ["device", "label"]:
            # For device nodes, check various ID fields and EUI
            if node_type == "device":
                # Check possible device ID fields
                device_matched = False
                for id_field in ["deviceId", "entityId", "id"]:
                    if id_field in node_data:
                        node_device_id = node_data.get(id_field)
                        # Convert to string for comparison
                        if str(node_device_id) == str(device_id):
                            print(
                                f"FLOW PROCESSOR: Found trigger node {node_id} matching device ID {device_id} via {id_field}"
                            )
                            trigger_nodes.append(node_id)
                            device_matched = True
                            break

                # Also check for device EUI in label field
                if not device_matched and "label" in node_data:
                    node_label = str(node_data.get("label", "")).strip()
                    if node_label == device_eui:
                        print(
                            f"FLOW PROCESSOR: Found trigger node {node_id} matching device EUI {device_eui}"
                        )
                        trigger_nodes.append(node_id)

            # For label nodes, check various ID fields
            elif node_type == "label" and label_ids:
                for id_field in ["labelId", "entityId", "id"]:
                    if id_field in node_data:
                        node_label_id = node_data.get(id_field)
                        # Try to convert to int, but fallback to string comparison
                        try:
                            if int(node_label_id) in label_ids:
                                print(
                                    f"FLOW PROCESSOR: Found trigger node {node_id} matching label ID {node_label_id}"
                                )
                                trigger_nodes.append(node_id)
                                break
                        except (ValueError, TypeError):
                            # String comparison fallback
                            if str(node_label_id) in [str(lid) for lid in label_ids]:
                                print(
                                    f"FLOW PROCESSOR: Found trigger node {node_id} matching label ID {node_label_id} (string comparison)"
                                )
                                trigger_nodes.append(node_id)
                                break

    print(f"FLOW PROCESSOR: Found {len(trigger_nodes)} trigger nodes: {trigger_nodes}")

    # Track execution path
    execution_path = []
    errors = []
    flow_results = []
    last_node_payload = None  # Store only the last payload across all paths

    # Process flow from each trigger node
    for trigger_node_id in trigger_nodes:
        print(f"FLOW PROCESSOR: Processing trigger node {trigger_node_id}")

        # Find outgoing edges from trigger node
        outgoing_edges = []
        for edge in flow.edges:
            if edge.get("source") == trigger_node_id:
                outgoing_edges.append(edge)

        print(
            f"FLOW PROCESSOR: Found {len(outgoing_edges)} outgoing edges from trigger node {trigger_node_id}"
        )

        # Process each outgoing path
        for i, edge in enumerate(outgoing_edges):
            target_node_id = edge.get("target")
            print(
                f"FLOW PROCESSOR: Processing edge {i+1}/{len(outgoing_edges)} to target node {target_node_id}"
            )

            try:
                result = await process_flow(
                    db, flow, target_node_id, payload, flow_history_id=flow_history.id
                )

                # Extract the last node payload - store the most recent one
                path_payload = extract_last_node_payload(result, payload)
                last_node_payload = path_payload  # Just keep the last one processed

                # Add to execution path
                execution_path.append(
                    {
                        "trigger_node": trigger_node_id,
                        "target_node": target_node_id,
                        "result": result,
                    }
                )

                # Check for errors
                if result.get("status") == "error":
                    errors.append(
                        {"node_id": target_node_id, "error": result.get("error")}
                    )
                    print(
                        f"FLOW PROCESSOR: Error processing node {target_node_id}: {result.get('error')}"
                    )

                flow_results.append(
                    {
                        "flow_id": flow.id,
                        "flow_name": flow.name,
                        "flow_history_id": flow_history.id,
                        "trigger_node": trigger_node_id,
                        "result": result,
                    }
                )
                print(
                    f"FLOW PROCESSOR: Successfully processed target node {target_node_id}"
                )

            except Exception as e:
                # Track errors
                errors.append({"node_id": target_node_id, "error": str(e)})
                print(
                    f"FLOW PROCESSOR: Exception while processing node {target_node_id}: {str(e)}"
                )
                logger.exception(
                    f"Error processing flow node {target_node_id}: {str(e)}"
                )

    # Update flow history record
    flow_end_time = time.time()
    execution_time_ms = int((flow_end_time - flow_start_time) * 1000)

    # Determine final status
    if errors:
        if len(errors) == len(execution_path):
            flow_status = "error"  # All paths failed
        else:
            flow_status = "partial_success"  # Some paths succeeded
    else:
        flow_status = "success"  # All paths succeeded

    # JSON serialize all dictionary data before storing in database
    # First convert execution_path to JSON string
    try:
        serialized_execution_path = json.dumps(execution_path)
    except (TypeError, ValueError, OverflowError) as e:
        print(f"FLOW PROCESSOR: Error serializing execution_path: {str(e)}")
        serialized_execution_path = json.dumps(
            {
                "status": "error",
                "error": f"Failed to serialize execution_path: {str(e)}",
                "truncated_data": str(execution_path)[:500],
            }
        )

    # Convert error_details to JSON string if it exists
    serialized_error_details = None
    if errors:
        try:
            serialized_error_details = json.dumps(errors)
        except (TypeError, ValueError, OverflowError) as e:
            print(f"FLOW PROCESSOR: Error serializing error_details: {str(e)}")
            serialized_error_details = json.dumps(
                {
                    "status": "error",
                    "error": f"Failed to serialize error_details: {str(e)}",
                    "truncated_data": str(errors)[:500],
                }
            )

    # Convert payload data to JSON string
    try:
        serialized_input_data = json.dumps(payload)
    except (TypeError, ValueError, OverflowError) as e:
        print(f"FLOW PROCESSOR: Error serializing input_data: {str(e)}")
        serialized_input_data = json.dumps(
            {
                "status": "error",
                "error": f"Failed to serialize input_data: {str(e)}",
                "truncated_data": str(payload)[:500],
            }
        )

    # Convert output data to JSON string
    try:
        serialized_output_data = (
            json.dumps(last_node_payload) if last_node_payload else None
        )
    except (TypeError, ValueError, OverflowError) as e:
        print(f"FLOW PROCESSOR: Error serializing output_data: {str(e)}")
        serialized_output_data = json.dumps(
            {
                "status": "error",
                "error": f"Failed to serialize output_data: {str(e)}",
                "truncated_data": (
                    str(last_node_payload)[:500] if last_node_payload else "None"
                ),
            }
        )

    # Update flow history
    flow_history.status = flow_status
    flow_history.execution_path = serialized_execution_path
    flow_history.error_details = serialized_error_details
    flow_history.end_time = datetime.utcnow()
    flow_history.execution_time = execution_time_ms
    flow_history.timestamp = datetime.utcnow()
    flow_history.input_data = serialized_input_data
    flow_history.output_data = serialized_output_data

    db.add(flow_history)
    db.commit()

    print(f"FLOW PROCESSOR: Flow execution completed with status: {flow_status}")
    print(
        f"FLOW PROCESSOR: Processed {len(flow_results)} flow paths in {execution_time_ms}ms"
    )

    # Log flow execution result
    if flow_status == "success":
        logger.info(
            f"Flow {flow.name} (ID: {flow.id}) executed successfully in {execution_time_ms}ms"
        )
    elif flow_status == "partial_success":
        logger.warning(
            f"Flow {flow.name} (ID: {flow.id}) partially succeeded in {execution_time_ms}ms with {len(errors)} errors"
        )
    else:
        logger.error(
            f"Flow {flow.name} (ID: {flow.id}) failed in {execution_time_ms}ms"
        )

    return {
        "status": flow_status,
        "flow_id": flow.id,
        "flow_name": flow.name,
        "flow_history_id": flow_history.id,
        "execution_time_ms": execution_time_ms,
        "results": flow_results,
        "errors": errors if errors else None,
        "last_node_payload": last_node_payload,  # Store just the final payload directly
    }


def extract_last_node_payload(
    result: Dict[str, Any], original_payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract the payload that was sent to the last node in a flow path.
    Recursively traverses the result tree to find the deepest node.

    Args:
        result: The result dictionary from process_flow
        original_payload: The original payload sent to the flow

    Returns:
        Dict containing the payload sent to the last node
    """
    # Start with the original payload or the modified payload if available
    current_payload = result.get("modified_payload", original_payload)

    # If this node is a function that modified the payload, use that
    if "modified_payload" in result:
        current_payload = result["modified_payload"]

    # Check if there are any next nodes
    if "next_nodes" in result and result["next_nodes"]:
        # For each downstream node, extract its last node payload
        last_payloads = []
        for next_node in result["next_nodes"]:
            # Recursively get payload from downstream node
            last_node_payload = extract_last_node_payload(next_node, current_payload)
            last_payloads.append(last_node_payload)

        # Return the last payload in the tree (if multiple branches, return the last one)
        if last_payloads:
            return last_payloads[-1]

    # Return current payload if this is a leaf node or has no valid next nodes
    return current_payload
