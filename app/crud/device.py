"""
CRUD operations for device management.
Provides functions to retrieve, update, and manage devices.
"""

from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.device_history import DeviceHistory
from datetime import datetime


def get_device(db: Session, device_id: int) -> Optional[Device]:
    """
    Get a device by ID.

    Args:
        db: Database session
        device_id: Device ID to look up

    Returns:
        Device object or None if not found
    """
    return db.query(Device).filter(Device.id == device_id).first()


def get_device_by_dev_eui(db: Session, dev_eui: str) -> Optional[Device]:
    """
    Get a device by DevEUI.

    Args:
        db: Database session
        dev_eui: Device EUI to look up

    Returns:
        Device object or None if not found
    """
    return db.query(Device).filter(Device.dev_eui == dev_eui).first()


def update_device_status(db: Session, device_id: int, status: str) -> Optional[Device]:
    """
    Update a device's status information.

    Args:
        db: Database session
        device_id: Device ID to update
        status_data: Dictionary with status information

    Returns:
        Updated device object or None if not found
    """
    device = get_device(db, device_id)

    device.status = status
    db.commit()
    db.refresh(device)

    current_status = device.status
    new_status = status

    # create a history entry for the status change
    latest_history = (
        db.query(DeviceHistory)
        .filter(DeviceHistory.device_id == device_id)
        .order_by(DeviceHistory.timestamp.desc())
        .first()
    )

    timestamp = datetime.utcnow()
    if latest_history:
        timestamp = latest_history.timestamp

    # convert time to a string
    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

    db_history = DeviceHistory(
        device_id=device_id,
        event="status_change",
        data={
            "status": new_status,
            "previous_status": current_status,
            "msg": "Device status changed to " + new_status,
            "last_transmission": timestamp_str,
        },
        timestamp=datetime.utcnow(),
    )
    db.add(db_history)
    db.commit()
    db.refresh(db_history)

    return True
