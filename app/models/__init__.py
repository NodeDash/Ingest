"""
Import all models to ensure they're registered with SQLAlchemy
"""

# First import the base models without circular dependencies
from app.models.user import User
from app.models.team import Team

# Then import models that depend on the base models
from app.models.device import Device
from app.models.label import Label

# Finally import models that depend on the previous ones
from app.models.device_history import DeviceHistory
from app.models.flow import Flow
from app.models.flow_history import FlowHistory
from app.models.function import Function
from app.models.function_history import FunctionHistory
from app.models.integration import Integration
from app.models.integration_history import IntegrationHistory
from app.models.label_history import LabelHistory
from app.models.provider import Provider
