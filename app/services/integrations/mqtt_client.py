"""
MQTT client for publishing messages to message brokers.
Provides methods for secure MQTT communication with error handling.
"""

import json
import logging
import time
from typing import Any, Dict, Optional, Union

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


def send_mqtt_message(
    host: str,
    topic: str,
    payload: Dict[str, Any],
    port: int = 1883,
    username: Optional[str] = None,
    password: Optional[str] = None,
    use_ssl: bool = False,
    ca_cert: Optional[str] = None,
    client_cert: Optional[str] = None,
    client_key: Optional[str] = None,
    qos: int = 0,
    timeout: int = 10,
) -> Dict[str, Any]:
    """
    Publish a message to an MQTT broker.

    Args:
        host: MQTT broker host
        topic: MQTT topic to publish on
        payload: Message payload (will be converted to JSON)
        port: MQTT broker port
        username: Optional username for authentication
        password: Optional password for authentication
        use_ssl: Whether to use SSL/TLS
        ca_cert: CA certificate for SSL/TLS
        client_cert: Client certificate for SSL/TLS
        client_key: Client key for SSL/TLS
        qos: Quality of Service (0, 1, or 2)
        timeout: Connection timeout in seconds

    Returns:
        Dict containing publish status and information
    """
    if not host:
        return {"status": "error", "error": "No MQTT host specified"}

    if not topic:
        return {"status": "error", "error": "No MQTT topic specified"}

    # Define MQTT client connection status
    connected = False
    connection_error = None

    # Define on_connect callback
    def on_connect(client, userdata, flags, rc):
        nonlocal connected, connection_error
        if rc == 0:
            logger.info(f"Connected to MQTT broker {host}:{port}")
            connected = True
        else:
            connection_error = f"Connection failed with code {rc}"
            logger.error(f"Failed to connect to MQTT broker: {connection_error}")

    # Define on_publish callback
    publish_complete = False
    publish_mid = None

    def on_publish(client, userdata, mid):
        nonlocal publish_complete, publish_mid
        publish_complete = True
        publish_mid = mid
        logger.info(f"Message published with message ID: {mid}")

    # Create MQTT client
    client_id = f"device-manager-ingest-{int(time.time())}"
    client = mqtt.Client(client_id=client_id)
    client.on_connect = on_connect
    client.on_publish = on_publish

    # Set up authentication if provided
    if username and password:
        client.username_pw_set(username, password)

    # Set up SSL/TLS if enabled
    if use_ssl:
        try:
            if ca_cert:
                cert_reqs = mqtt.ssl.CERT_REQUIRED
            else:
                cert_reqs = mqtt.ssl.CERT_NONE

            client.tls_set(
                ca_certs=ca_cert,
                certfile=client_cert,
                keyfile=client_key,
                cert_reqs=cert_reqs,
            )
            logger.info("TLS configuration set")
        except Exception as e:
            logger.error(f"Error setting up TLS: {str(e)}")
            return {"status": "error", "error": f"TLS setup failed: {str(e)}"}

    try:
        # Connect to the broker
        logger.info(f"Connecting to MQTT broker {host}:{port}")
        client.connect(host, port, keepalive=timeout)

        # Start the loop to process network events
        client.loop_start()

        # Wait for connection
        start_time = time.time()
        while (
            not connected
            and not connection_error
            and time.time() - start_time < timeout
        ):
            time.sleep(0.1)

        if not connected:
            client.loop_stop()
            error_msg = (
                connection_error or f"Connection timed out after {timeout} seconds"
            )
            return {"status": "error", "error": error_msg}

        # Encode payload as JSON string
        try:
            if isinstance(payload, dict) or isinstance(payload, list):
                payload_str = json.dumps(payload)
            else:
                payload_str = str(payload)
        except Exception as e:
            client.loop_stop()
            logger.error(f"Error encoding MQTT payload: {str(e)}")
            return {"status": "error", "error": f"Payload encoding failed: {str(e)}"}

        # Publish message
        logger.info(f"Publishing message to {topic}")
        result = client.publish(topic, payload_str, qos=qos)
        msg_id = result[1]

        # Wait for publish to complete (for QoS 1 or 2)
        if qos > 0:
            start_time = time.time()
            while not publish_complete and time.time() - start_time < timeout:
                time.sleep(0.1)

            if not publish_complete:
                client.loop_stop()
                return {
                    "status": "error",
                    "error": f"Publish timed out after {timeout} seconds",
                }

        # Stop the network loop
        client.loop_stop()

        # Return success
        return {
            "status": "success",
            "message_id": msg_id,
            "topic": topic,
            "qos": qos,
        }

    except Exception as e:
        # Clean up
        try:
            client.loop_stop()
        except:
            pass

        logger.exception(f"Error publishing MQTT message: {str(e)}")
        return {
            "status": "error",
            "error": f"MQTT error: {str(e)}",
            "exception": str(e),
        }
