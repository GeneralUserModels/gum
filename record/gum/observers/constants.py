from __future__ import annotations

# Shared defaults used by observer backends and platform integrations

# Screen capture and housekeeping
CAPTURE_FPS_DEFAULT: int = 5
MEMORY_CLEANUP_INTERVAL_DEFAULT: int = 30
MON_START_INDEX: int = 1

# Keyboard activity sampling
KEYBOARD_TIMEOUT_DEFAULT: float = 2.0
KEYBOARD_SAMPLE_INTERVAL_DEFAULT: float = 0.25

# Scroll filtering
SCROLL_DEBOUNCE_SEC_DEFAULT: float = 0.5
SCROLL_MIN_DISTANCE_DEFAULT: float = 5.0
SCROLL_MAX_FREQUENCY_DEFAULT: int = 10
SCROLL_SESSION_TIMEOUT_DEFAULT: float = 2.0

# macOS app UI intervals (milliseconds)
KEYBOARD_PUMP_INTERVAL_MS: int = 50
PERMISSION_REFRESH_INTERVAL_MS: int = 3000


