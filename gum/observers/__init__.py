"""
Observer module for GUM - General User Models.

This module provides observer classes for different types of user interactions.
"""

from .observer import Observer
from .screen import Screen
# TODO: Calendar observer disabled due to ics/tatsu incompatibility with Python 3.10+
# See: tatsu 4.4.0 uses `from collections import Mapping` (removed in 3.10)
# Fix: upgrade ics to >=0.8 and update calendar.py for the new API.
# from .calendar import Calendar

__all__ = ["Observer", "Screen"] 