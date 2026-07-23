"""
Service container for Project Jarvis.
"""

from jarvis.core.config_loader import ConfigLoader
from jarvis.core.event_bus import EventBus
from jarvis.core.logger import JarvisLogger


class ServiceContainer:
    """
    Holds shared services used throughout the application.
    """

    def __init__(self):
        self.logger = JarvisLogger()
        self.config_loader = ConfigLoader()
        self.event_bus = EventBus()