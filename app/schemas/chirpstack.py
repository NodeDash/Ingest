"""
Schema definitions for ChirpStack API interactions.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class UplinkChirpstack(BaseModel):
    deduplicationId: Optional[str] = None
    phy_payload: Optional[Dict[str, Any]] = {}
    metadata: Optional[Dict[str, Any]] = {}
    time: Optional[str] = None
    deviceInfo: Optional[Dict[str, Any]] = {}
    object: Optional[Dict[str, Any]] = {}
    devAddr: Optional[str] = None
    adr: Optional[bool] = None
    dr: Optional[int] = None
    fCnt: Optional[int] = None
    fPort: Optional[int] = None
    confirmed: Optional[bool] = None
    data: Optional[str] = None
    rxInfo: Optional[List[Dict[str, Any]]] = []
    txInfo: Optional[Dict[str, Any]] = {}
