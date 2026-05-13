from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class CaptureBase(ABC):
    """
    Abstract base class for platform-specific screen capture and window management.
    """

    @abstractmethod
    def get_monitor_geometries(self) -> List[Dict[str, int]]:
        """
        Returns a list of dictionaries containing geometry for all active monitors.
        
        Expected keys: 'left', 'top', 'width', 'height'.
        Coordinates should be in the OS's global coordinate system.
        """
        pass

    @abstractmethod
    def is_any_app_visible(self, app_names: List[str]) -> bool:
        """
        Checks if any application in the provided list has at least one 
        visible, non-minimized window on any screen.
        
        Args:
            app_names: A list of application names/titles to check for.
            
        Returns:
            True if at least one matching application window is visible.
        """
        pass

    @abstractmethod
    def get_monitor_at_point(self, x: float, y: float) -> Optional[Dict[str, int]]:
        """
        Returns the geometry dictionary of the monitor containing the given global coordinates.
        
        Args:
            x: The horizontal global coordinate.
            y: The vertical global coordinate.
            
        Returns:
            A dictionary with 'left', 'top', 'width', 'height' keys, or None if the point 
            is off-screen.
        """
        pass

    @abstractmethod
    def get_window_list(self) -> List[Dict]:
        """
        Returns a raw list of metadata for all currently onscreen windows.
        
        Used primarily for debugging and advanced filtering.
        Expected keys: 'owner_name', 'title', 'bounds', 'is_visible'.
        """
        pass
