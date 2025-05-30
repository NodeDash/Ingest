"""
Flow engine module for executing flow-based data processing.
Handles the core flow execution logic, following node connections and executing nodes.
"""

import json
import logging
import time
from typing import Any, Dict, Set, Optional

from sqlalchemy.orm import Session

from app.models.flow import Flow
from app.services.flow_processor.function_processor import process_function_node
from app.services.flow_processor.integration_processor import process_integration_node

logger = logging.getLogger(__name__)


async def process_flow(
    db: Session,
    flow: Flow,
    node_id: str,
    payload: Dict[str, Any],
    flow_history_id: Optional[int] = None,
    processed_nodes: Optional[Set[str]] = None,
    is_root_call: bool = True,
) -> Dict[str, Any]:
    """
    Process a flow starting from a specific node, following the edges and executing
    functions or sending data to integrations. Records execution history.

    Args:
        db: Database session
        flow: Flow object to process
        node_id: Starting node ID
        payload: The data payload to process
        flow_history_id: ID of the flow history record if this is part of a larger flow execution
        processed_nodes: Set of already processed nodes to prevent infinite loops
        is_root_call: Whether this is the root/initial call in the recursion chain

    Returns:
        Dict containing processing results
    """
    print(f"FLOW PROCESSOR: Processing node {node_id} in flow {flow.id} ({flow.name})")

    if processed_nodes is None:
        processed_nodes = set()
        print(f"FLOW PROCESSOR: Initializing new processed_nodes set")
    else:
        print(
            f"FLOW PROCESSOR: Using existing processed_nodes set with {len(processed_nodes)} items"
        )
        # If we have existing processed nodes, this isn't the root call
        is_root_call = False

    # Prevent infinite loops by tracking processed nodes
    if node_id in processed_nodes:
        print(
            f"FLOW PROCESSOR: Node {node_id} already processed, skipping to prevent loop"
        )
        return {"status": "skipped", "reason": "already_processed"}

    processed_nodes.add(node_id)
    print(f"FLOW PROCESSOR: Added node {node_id} to processed set")

    # Find the current node in the flow
    current_node = None
    for node in flow.nodes:
        if node.get("id") == node_id:
            current_node = node
            break

    if not current_node:
        print(f"FLOW PROCESSOR: ERROR - Node {node_id} not found in flow {flow.id}")
        return {"status": "error", "reason": f"Node {node_id} not found in flow"}

    node_type = current_node.get("type")
    print(f"FLOW PROCESSOR: Found node {node_id}, type: {node_type}")

    if node_type == "function":
        # Look for multiple possible ID field names
        function_id = None
        for id_field in ["functionId", "entityId", "id"]:
            if id_field in current_node.get("data", {}):
                function_id = current_node.get("data", {}).get(id_field)
                break
        print(f"FLOW PROCESSOR: Node is function type with function ID: {function_id}")
    elif node_type == "integration":
        # Look for multiple possible ID field names
        integration_id = None
        for id_field in ["integrationId", "entityId", "id"]:
            if id_field in current_node.get("data", {}):
                integration_id = current_node.get("data", {}).get(id_field)
                break
        print(
            f"FLOW PROCESSOR: Node is integration type with integration ID: {integration_id}"
        )
    elif node_type == "device":
        device_id = current_node.get("data", {}).get("deviceId") or current_node.get(
            "data", {}
        ).get("entityId")
        print(f"FLOW PROCESSOR: Node is device type with device ID: {device_id}")
    elif node_type == "label":
        label_id = current_node.get("data", {}).get("labelId") or current_node.get(
            "data", {}
        ).get("entityId")
        print(f"FLOW PROCESSOR: Node is label type with label ID: {label_id}")

    results = {"node_id": node_id, "type": node_type, "status": "processed"}

    try:
        # Process node based on its type
        if node_type == "function":
            print(f"FLOW PROCESSOR: Executing function node {node_id}")
            try:
                function_result = await process_function_node(
                    db, current_node, payload, flow_id=flow.id
                )
                results.update(function_result)

                # Set node status to error if function result is error
                if function_result.get("function_result") == "error":
                    results["status"] = "error"
                    results["error"] = function_result.get(
                        "function_error", "Function execution failed"
                    )

                print(
                    f"FLOW PROCESSOR: Function execution result: {results.get('function_result', 'unknown')}"
                )
            except Exception as function_error:
                print(
                    f"FLOW PROCESSOR: Error in function execution: {str(function_error)}"
                )
                # Make sure the database isn't left in a bad state
                try:
                    db.rollback()
                except:
                    pass
                results.update(
                    {
                        "function_result": "error",
                        "function_error": str(function_error),
                        "status": "error",
                    }
                )

        elif node_type == "integration":
            print(f"FLOW PROCESSOR: Executing integration node {node_id}")
            try:
                integration_result = await process_integration_node(
                    db, current_node, payload, flow_id=flow.id
                )
                results.update(integration_result)

                # Safely extract status from result
                integration_status = "unknown"
                if isinstance(results.get("integration_result"), dict):
                    integration_status = results.get("integration_result", {}).get(
                        "status", "unknown"
                    )
                elif isinstance(results.get("integration_result"), str):
                    integration_status = "completed"

                # Set node status to error if integration result has error status
                if integration_status == "error":
                    results["status"] = "error"
                    results["error"] = results.get("integration_result", {}).get(
                        "error",
                        "Integration execution failed",
                    )
                    print(
                        f"FLOW PROCESSOR: Integration returned error, setting node status to error"
                    )

                print(
                    f"FLOW PROCESSOR: Integration execution result: {integration_status}"
                )
            except Exception as integration_error:
                print(
                    f"FLOW PROCESSOR: Error in integration execution: {str(integration_error)}"
                )
                # Make sure the database isn't left in a bad state
                try:
                    db.rollback()
                except:
                    pass
                results.update(
                    {
                        "integration_result": {
                            "status": "error",
                            "error": str(integration_error),
                        },
                        "status": "error",
                        "error": str(integration_error),
                    }
                )

        # Find outgoing edges from this node
        outgoing_edges = []
        for edge in flow.edges:
            if edge.get("source") == node_id:
                outgoing_edges.append(edge)

        print(
            f"FLOW PROCESSOR: Found {len(outgoing_edges)} outgoing edges from node {node_id}"
        )

        # Check if we need to use modified payload for next nodes
        # For function nodes, use the modified payload if available
        next_payload = payload
        if node_type == "function" and "modified_payload" in results:
            print(
                f"FLOW PROCESSOR: Using modified payload from function for next nodes"
            )
            next_payload = results["modified_payload"]

        # Process all target nodes recursively
        next_results = []
        for i, edge in enumerate(outgoing_edges):
            target_node_id = edge.get("target")
            print(
                f"FLOW PROCESSOR: Processing edge {i+1}/{len(outgoing_edges)} to target node {target_node_id}"
            )
            try:
                edge_result = await process_flow(
                    db,
                    flow,
                    target_node_id,
                    next_payload,  # Pass the modified payload forward
                    flow_history_id=flow_history_id,
                    processed_nodes=processed_nodes,
                    is_root_call=False,  # Mark recursive calls as non-root
                )
                next_results.append(edge_result)
                # Check if downstream node had an error and propagate it up
                if edge_result.get("status") == "error":
                    if (
                        results.get("status") != "error"
                    ):  # Don't overwrite existing error
                        results["status"] = "error"
                        results["error"] = (
                            f"Error in downstream node {target_node_id}: {edge_result.get('error', 'Unknown error')}"
                        )
                        print(
                            f"FLOW PROCESSOR: Propagating error from downstream node {target_node_id}"
                        )

                print(
                    f"FLOW PROCESSOR: Completed processing of target node {target_node_id}"
                )
            except Exception as edge_error:
                print(
                    f"FLOW PROCESSOR: Error processing target node {target_node_id}: {str(edge_error)}"
                )
                next_results.append(
                    {
                        "status": "error",
                        "node_id": target_node_id,
                        "error": str(edge_error),
                    }
                )
                results["status"] = "error"
                results["error"] = (
                    f"Error processing target node {target_node_id}: {str(edge_error)}"
                )

        if next_results:
            results["next_nodes"] = next_results
            print(
                f"FLOW PROCESSOR: Added {len(next_results)} next node results to output"
            )

        # Update flow status only at the root level of recursion
        if is_root_call:
            try:
                if results.get("status") == "error":
                    flow.status = "error"
                else:
                    flow.status = "success"
                db.commit()
                print(f"FLOW PROCESSOR: Updated flow status to {flow.status}")
            except Exception as e:
                print(
                    f"FLOW PROCESSOR: ERROR - Exception while updating flow status: {str(e)}"
                )
                logger.exception(f"Error updating flow status: {str(e)}")
                db.rollback()
                # Don't return error here, just log it

        print(f"FLOW PROCESSOR: Completed processing of node {node_id}")
        return results

    except Exception as e:
        print(
            f"FLOW PROCESSOR: ERROR - Exception while processing node {node_id}: {str(e)}"
        )
        logger.exception(f"Error processing flow node {node_id}: {str(e)}")

        # If this is a database error, try to rollback the transaction
        try:
            db.rollback()
            print(f"FLOW PROCESSOR: Rolled back database transaction after error")
        except:
            pass

        # Update flow status on error at the root level
        if is_root_call:
            try:
                flow.status = "error"
                db.commit()
                print(f"FLOW PROCESSOR: Updated flow status to error due to exception")
            except Exception as status_error:
                print(
                    f"FLOW PROCESSOR: ERROR - Exception while updating flow status: {str(status_error)}"
                )
                logger.exception(f"Error updating flow status: {str(status_error)}")
                try:
                    db.rollback()
                except:
                    pass

        return {"status": "error", "node_id": node_id, "error": str(e)}
