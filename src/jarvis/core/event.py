"""
Event model for Project Jarvis.
"""

from dataclasses import dataclass


@dataclass
class Event:
    """
    Represents an application event.
    """

    name: str