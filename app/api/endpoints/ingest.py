"""
Ingestion endpoints for device data from various platforms.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends, status, Body, Security
from sqlalchemy.orm import Session
from app import crud, schemas
from app.core.auth import api_key_header
from app.db.database import get_db
from app.models.device_history import DeviceHistory
from app.models.flow import Flow
from app.models.label import Label
from app.services.flow_processor.device_processor import execute_flow_for_device
from app.redis.client import RedisClient
from app.crud.device import update_device_status
from app.core.config import settings
from app.crud.provider import get_provider_by_owner

redis_client = RedisClient.get_instance()

router = APIRouter()

logger = logging.getLogger(__name__)

# Configure logging to show more detailed output
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@router.post(
    "/chirpstack",
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_chirpstack_uplink(
    *,
    db: Session = Depends(get_db),
    api_key: str = Security(api_key_header),
    uplink_data: schemas.chirpstack.UplinkChirpstack = Body(...),
    event: str = None,  # Add query parameter for event type
) -> Dict[str, Any]:
    """
    Receive uplink data from ChirpStack and process it.

    Authentication:
        Requires a valid API key in the X-API-Key header

    Query Parameters:
        event: Optional event type from ChirpStack (e.g., "up", "join")
    """
    # first get the dev_eui from the payload
    # then get the device from the database, find out its owner and look to see if they have a provider type of chripstack setup

    dev_eui = None
    if (
        uplink_data.deviceInfo
        and isinstance(uplink_data.deviceInfo, dict)
        and "devEui" in uplink_data.deviceInfo
    ):
        dev_eui = uplink_data.deviceInfo["devEui"]
        # uppercase the dev_eui
        dev_eui = dev_eui.upper()

    # lookup the device by dev_eui
    device = crud.device.get_device_by_dev_eui(db, dev_eui=dev_eui)
    if not device:
        # if we can't find the device, we can't process the uplink
        return {
            "success": False,
            "error": f"Device with devEui {dev_eui} not found in database",
            "received_at": datetime.utcnow().isoformat(),
        }

    # now lookup the owner type and id, and look for any providers that are of type chirpstack
    provider_config = get_provider_by_owner(
        db=db,
        owner_id=device.owner_id,
        owner_type=device.owner_type,
        provider_type="chirpstack",
    )
    if not provider_config:
        # check the key matches the one in the settings
        if api_key != settings.SECRET_KEY:
            return {
                "success": False,
                "error": "Invalid API key",
                "received_at": datetime.utcnow().isoformat(),
            }
            # return 403 forbidden

    else:
        # check the key matches the one in the provider config
        if provider_config.config and "X-API-KEY" in provider_config.config:
            if provider_config.config["X-API-KEY"] != api_key:
                return {
                    "success": False,
                    "error": "Invalid API key",
                    "received_at": datetime.utcnow().isoformat(),
                }
                # return 403 forbidden

    print("======================================================")
    print("STAGE 0: CHIRPSTACK INGESTION STARTING")
    print("======================================================")

    try:
        print(
            f"STAGE 1: RECEIVED DATA - Deduplication ID: {uplink_data.deduplicationId}"
        )
        logger.info(f"Received ChirpStack data: {uplink_data.deduplicationId}")

        # Extract device EUI from the payload
        dev_eui = None
        if (
            uplink_data.deviceInfo
            and isinstance(uplink_data.deviceInfo, dict)
            and "devEui" in uplink_data.deviceInfo
        ):
            dev_eui = uplink_data.deviceInfo["devEui"]
            # uppercase the dev_eui
            dev_eui = dev_eui.upper()

            print(f"STAGE 2: EXTRACTED DEVICE EUI - {dev_eui}")
        else:
            print("STAGE 2: FAILED - No device EUI found in payload")

        # If we couldn't find the device EUI, log an error and return
        if not dev_eui:
            print("STAGE 2: ERROR - No device EUI found in ChirpStack data")
            logger.error("No devEui found in ChirpStack data")
            return {
                "success": False,
                "error": "No devEui found in payload",
                "received_at": datetime.utcnow().isoformat(),
            }

        # Find the device in the database
        print(f"STAGE 3: SEARCHING FOR DEVICE - DevEUI: {dev_eui}")
        device = crud.device.get_device_by_dev_eui(db, dev_eui=dev_eui)

        if not device:
            print(
                f"STAGE 3: ERROR - Device with DevEUI {dev_eui} not found in database"
            )
            logger.warning(f"Device with devEui {dev_eui} not found in database")
            return {
                "success": False,
                "error": f"Device with devEui {dev_eui} not found",
                "received_at": datetime.utcnow().isoformat(),
            }

        print(f"STAGE 3: SUCCESS - Found device ID: {device.id}, Name: {device.name}")

        # Create device history entry with full Chirpstack data
        print("STAGE 4: CREATING DEVICE HISTORY ENTRY")

        # TODO: we should also add support for
        # status - Margin and battery status
        # ack - Confirmed downlink (n)ack
        # txack - Downlink transmission ack
        # log - Log (or error) event
        # location - Location event
        # integration - Integration event

        # Determine event type from query parameter first, then from payload analysis
        event_type = "uplink"  # Default event type

        # Check if event type is provided in query parameter
        if event:
            print(f"STAGE 4: INFO - Event type provided in query parameter: {event}")
            # Map ChirpStack event types to our internal types
            if event.lower() == "join":
                event_type = "join"
            elif event.lower() in ["up", "uplink"]:
                event_type = "uplink"
            # Add more event types as needed
        else:
            # Fallback to payload analysis for event type detection
            # check to see if the uplink is not null for fCnt and data
            if uplink_data.fCnt is None and uplink_data.data is None:
                # if both are null, we assume this is a join event
                event_type = "join"
                print(
                    "STAGE 4: INFO - Uplink data payload analysis indicates a join event"
                )

        print(f"STAGE 4: INFO - Determined event type: {event_type}")

        data = {
            "deduplicationId": uplink_data.deduplicationId,
            "time": uplink_data.time,
            "deviceInfo": uplink_data.deviceInfo,
            "devAddr": uplink_data.devAddr,
            "adr": uplink_data.adr,
            "dr": uplink_data.dr,
            "fCnt": uplink_data.fCnt,
            "fPort": uplink_data.fPort,
            "confirmed": uplink_data.confirmed,
            "data": uplink_data.data,
            "rxInfo": uplink_data.rxInfo,
            "txInfo": uplink_data.txInfo,
            "phy_payload": uplink_data.phy_payload,
            "metadata": uplink_data.metadata,
            "object": uplink_data.object,
        }

        # For join events, we use a simplified data structure
        if event_type == "join":
            data = {
                "deduplicationId": uplink_data.deduplicationId,
                "time": uplink_data.time,
                "deviceInfo": uplink_data.deviceInfo,
                "devAddr": uplink_data.devAddr,
            }

        history_data = {
            "device_id": device.id,
            "event": event_type,
            "data": data,
        }

        # check if there is an existing history item based on deduplicationId
        existing_history = (
            db.query(DeviceHistory)
            .filter(
                DeviceHistory.device_id == device.id,
                DeviceHistory.event == event_type,
            )
            .order_by(
                DeviceHistory.timestamp.desc()  # Order by timestamp descending, most recent first
            )
            .limit(10)
            .all()
        )

        if existing_history:
            # Check if the deduplicationId already exists in the history
            for history in existing_history:
                if history.data.get("deduplicationId") == uplink_data.deduplicationId:
                    print(
                        f"STAGE 4: SKIPPING - Deduplication ID {uplink_data.deduplicationId} already exists in history"
                    )
                    return {
                        "success": False,
                        "error": "Deduplication ID already exists in history",
                        "received_at": datetime.utcnow().isoformat(),
                    }

        # Create device history entry
        device_history = DeviceHistory(
            device_id=history_data["device_id"],
            event=history_data["event"],
            data=history_data["data"],
        )
        db.add(device_history)
        print(f"STAGE 4: SUCCESS - Created history entry for device {device.id}")

        # Update device status to online
        print("STAGE 5: UPDATING DEVICE STATUS TO ONLINE")

        if device and device.expected_transmit_time:
            # Convert minutes to seconds
            ttl_seconds = device.expected_transmit_time * 60
        else:
            # Default to 5 minutes if not set
            ttl_seconds = 5 * 60
        print(f"STAGE 5: INFO - Setting TTL to {ttl_seconds} seconds")
        # Update device status in the database
        redis_client.set_device_online(int(device.id), int(ttl_seconds))

        # if the old status was offline, update the status in the database
        if device.status != "online":
            update_device_status(db=db, device_id=device.id, status="online")
        print(f"STAGE 5: SUCCESS - Device {device.id} status updated to online")
        # You might also want to update your database status here
        # depending on your existing code structure

        # Commit the transaction
        print("STAGE 6: COMMITTING DATABASE TRANSACTION")
        db.commit()
        print("STAGE 6: SUCCESS - Database transaction committed")

        # if its a join, we dont want to process any flows
        if event_type == "join":
            print(
                "STAGE 6: INFO - Uplink data indicates a join event, skipping flow processing"
            )
            return {
                "success": True,
                "device_id": device.id,
                "dev_eui": dev_eui,
                "flows_processed": 0,
                "received_at": datetime.utcnow().isoformat(),
            }

        # Prepare payload for flow processing
        print("STAGE 7: PREPARING PAYLOAD FOR FLOW PROCESSING")
        payload = {
            "deduplicationId": uplink_data.deduplicationId,
            "time": uplink_data.time,
            "deviceInfo": uplink_data.deviceInfo,
            "devAddr": uplink_data.devAddr,
            "adr": uplink_data.adr,
            "dr": uplink_data.dr,
            "fCnt": uplink_data.fCnt,
            "fPort": uplink_data.fPort,
            "confirmed": uplink_data.confirmed,
            "data": uplink_data.data,
            "rxInfo": uplink_data.rxInfo,
            "txInfo": uplink_data.txInfo,
            "phy_payload": uplink_data.phy_payload,
            "metadata": uplink_data.metadata,
            "object": uplink_data.object,
        }

        # Get all labels associated with this device
        print("STAGE 8: GETTING DEVICE LABELS")
        label_ids = [label.id for label in device.labels]
        print(f"STAGE 7: SUCCESS - Found {len(label_ids)} labels: {label_ids}")

        # Find flows that use this device or its labels
        print("STAGE 9: SEARCHING FOR RELEVANT FLOWS")
        flows = []
        added_flow_ids = set()  # Keep track of flow IDs we've already added
        all_flows = db.query(Flow).all()
        print(f"STAGE 9: INFO - Checking {len(all_flows)} total flows")

        for flow in all_flows:
            print(f"STAGE 9: EXAMINING FLOW ID {flow.id} - '{flow.name}'")

            # Skip if we've already added this flow
            if flow.id in added_flow_ids:
                print(f"STAGE 9: SKIPPING - Flow ID {flow.id} already added to matches")
                continue

            # Check if flow has nodes
            if not flow.nodes:
                print(f"STAGE 9: SKIPPING - Flow ID {flow.id} has no nodes")
                continue

            flow_matched = False

            # Examine each node in the flow
            for node in flow.nodes:
                node_id = node.get("id", "unknown")
                node_type = node.get("type")
                node_data = node.get("data", {})

                print(f"STAGE 9: EXAMINING NODE {node_id} - Type: {node_type}")
                print(f"STAGE 9: NODE DATA: {json.dumps(node_data)}")

                # Check for device node matching our device
                if node_type == "device":
                    # Get all possible ID values from the node
                    possible_ids = []
                    for id_field in ["deviceId", "entityId", "id"]:
                        if id_field in node_data:
                            possible_ids.append((id_field, node_data[id_field]))

                    print(f"STAGE 9: DEVICE NODE - Found ID fields: {possible_ids}")
                    print(
                        f"STAGE 9: COMPARING WITH Device ID: {device.id} (type: {type(device.id).__name__})"
                    )

                    # Check each possible ID field
                    for id_field, value in possible_ids:
                        # Convert both to strings for comparison to avoid type mismatches
                        if str(value) == str(device.id):
                            print(
                                f"STAGE 9: MATCH FOUND! Flow ID {flow.id} - Node {node_id} - Field {id_field}={value} matches device {device.id}"
                            )
                            flows.append(flow)
                            added_flow_ids.add(flow.id)  # Mark this flow as added
                            flow_matched = True
                            break

                # Also check if the node might reference the device by dev_eui
                if node_type == "device" and "label" in node_data:
                    node_label = str(node_data.get("label", "")).strip()
                    if node_label == dev_eui:
                        print(
                            f"STAGE 9: MATCH FOUND! Flow ID {flow.id} - Node {node_id} - label={node_label} matches device EUI {dev_eui}"
                        )
                        flows.append(flow)
                        added_flow_ids.add(flow.id)  # Mark this flow as added
                        flow_matched = True
                        break

                # Check for label nodes matching our device's labels
                if node_type == "label" and label_ids:
                    # Get all possible label ID values from the node
                    possible_ids = []
                    for id_field in ["labelId", "entityId", "id"]:
                        if id_field in node_data:
                            possible_ids.append((id_field, node_data[id_field]))

                    print(f"STAGE 9: LABEL NODE - Found ID fields: {possible_ids}")
                    print(f"STAGE 9: COMPARING WITH Device's label IDs: {label_ids}")

                    # Check each possible ID field
                    for id_field, value in possible_ids:
                        # Try to convert to int, but if it fails, use string comparison
                        try:
                            node_label_id = int(value)
                            if node_label_id in label_ids:
                                print(
                                    f"STAGE 9: MATCH FOUND! Flow ID {flow.id} - Node {node_id} - Field {id_field}={node_label_id} matches device label"
                                )
                                flows.append(flow)
                                added_flow_ids.add(flow.id)  # Mark this flow as added
                                flow_matched = True
                                break
                        except (ValueError, TypeError):
                            # String comparison fallback
                            if str(value) in [str(lid) for lid in label_ids]:
                                print(
                                    f"STAGE 9: MATCH FOUND! Flow ID {flow.id} - Node {node_id} - Field {id_field}={value} matches device label (string comparison)"
                                )
                                flows.append(flow)
                                added_flow_ids.add(flow.id)  # Mark this flow as added
                                flow_matched = True
                                break

                if flow_matched:
                    break

            if not flow_matched:
                print(
                    f"STAGE 9: NO MATCH - Flow ID {flow.id} does not reference device {device.id} or its labels"
                )

        # dedupe flows
        flows = list({flow.id: flow for flow in flows}.values())

        print(
            f"STAGE 9: SUCCESS - Found {len(flows)} matching flows: {[flow.id for flow in flows]}"
        )

        # Process each matching flow
        print("STAGE 10: PROCESSING MATCHING FLOWS")
        flow_results = []
        for i, flow in enumerate(flows):
            print(
                f"STAGE 10: PROCESSING FLOW {i+1}/{len(flows)} - Flow ID: {flow.id}, Name: {flow.name}"
            )
            result = await execute_flow_for_device(
                db=db,
                flow=flow,
                device_id=device.id,
                device_eui=dev_eui,
                payload=payload,
                label_ids=label_ids,
            )
            flow_results.append(result)
            print(f"STAGE 10: COMPLETED FLOW {i+1}/{len(flows)} - Result: {result}")

        print("======================================================")
        print(f"STAGE 11: COMPLETED - Processed uplink for device {dev_eui}")
        print(f"             Processed {len(flow_results)} flows")
        print("======================================================")

        logger.info(
            f"Successfully processed uplink for device {dev_eui} through {len(flow_results)} flow paths"
        )
        return {
            "success": True,
            "device_id": device.id,
            "dev_eui": dev_eui,
            "flows_processed": len(flow_results),
            "received_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"STAGE ERROR: EXCEPTION OCCURRED - {str(e)}")
        logger.exception(f"Error processing ChirpStack data: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "received_at": datetime.utcnow().isoformat(),
        }
