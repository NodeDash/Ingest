import enum


class OwnerType(str, enum.Enum):
    """
    Enum representing the type of owner for resources.
    This allows for both user and team ownership in the future.
    """

    USER = "user"
    TEAM = "team"


class IntegrationStatus(str, enum.Enum):
    """
    Enum representing the status of an integration.
    """

    INACTIVE = "inactive"
    SUCCESS = "success"
    ERROR = "error"


class IntegrationType(str, enum.Enum):
    """
    Enum representing the type of integration.
    """

    HTTP = "http"
    MQTT = "mqtt"


class DeviceStatus(str, enum.Enum):
    """
    Enum representing the status of a device.
    """

    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    NEVER_SEEN = "never_seen"


class Region(str, enum.Enum):
    """
    Enum representing the region for device configuration.
    """

    EU868 = "EU868"
    US915 = "US915"
    AU915 = "AU915"
    AS923 = "AS923"


class ProviderType(str, enum.Enum):
    """
    Enum representing the type of provider.
    """

    chirpstack = "chirpstack"
    email = "email"
    sms = "sms"


class EmailMode(str, enum.Enum):
    """
    Enum representing the email provider mode.
    """

    SMTP = "SMTP"
    MAILGUN = "MAILGUN"
