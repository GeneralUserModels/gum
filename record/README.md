# Human Activity Recording Tool

## Installation

Install from source for now. As of now, we've only tested MacOS:

```bash
pip install -e .
```

For memory monitoring capabilities:
```bash
pip install -e .[monitoring]
```

Make sure to enable recording on your Mac: go to System Preferences -> Privacy & Security -> Accessibility, allow recording for the app that you use to edit the code, e.g., vscode.

## Standalone App (currently only on MacOS)

We provide a build script that creates a `.app` you can double‑click.

1) Build (developer step):

```bash
# From record/ directory
./gum/app/macos/build-macos.sh record
```

This produces `gum/app/macos/dist/Gum Recorder.app`.

2) First run permissions (user step):
- Open `gum/app/macos/dist/Gum Recorder.app` (right‑click → Open the first time if Gatekeeper warns)
- Grant permissions when prompted:
  - Privacy & Security → Screen Recording → enable “Gum Recorder”
  - Privacy & Security → Accessibility → enable “Gum Recorder”
  - Privacy & Security → Input Monitoring → enable “Gum Recorder”

The app saves data under `~/Downloads/records`.

## Usage

### CLI (Terminal)

1. Grant your terminal application (Terminal, iTerm2, etc.) Accessibility and Input Monitoring permissions in **System Settings → Privacy & Security**.
2. Activate the environment where you installed the package and run:

```bash
gum --user-name "your-name"
```

   The CLI defaults to the pynput keyboard backend so it works inside a terminal window without a Cocoa run loop. Data and screenshots go to `~/Downloads/records` unless you override `--data-directory` / `--screenshots-dir`.

3. You can also invoke the entrypoint directly:

```bash
python -m gum.cli.main --debug
```

   Use `GUM_DISABLE_KEYBOARD=1` if you need to launch without keyboard logging (for example while debugging permissions).

### Scroll Filtering Options
### macOS note: GUM_DISABLE_KEYBOARD

On macOS, AppKit requires keyboard event monitors to be registered from the main thread. Our GUI app (Tk-based) sets up a main-thread shim that captures AppKit key events and forwards them into the background recorder thread. To avoid registering a second keyboard listener in the background thread (which can fail due to macOS security constraints), the GUI sets the environment variable `GUM_DISABLE_KEYBOARD=1` before starting the background recorder. The observer (`Screen`) checks this variable and skips starting its keyboard backend when the shim is active.

- When running the GUI app: the main-thread shim is used; `GUM_DISABLE_KEYBOARD=1` is set automatically.
- When running the CLI: no shim is present; leave the variable unset so the keyboard backend runs normally.

Only set `GUM_DISABLE_KEYBOARD=1` if you explicitly want to disable the keyboard backend (e.g., to debug permissions) and rely on the GUI shim, or run without keyboard capture.


To reduce unnecessary scroll logging, you can configure scroll filtering parameters:

```bash
# More aggressive filtering (fewer scroll events logged)
gum --scroll-debounce 1.0 \
    --scroll-min-distance 10.0 \
    --scroll-max-frequency 5 \
    --scroll-session-timeout 3.0

# Less filtering (more scroll events logged)
gum --scroll-debounce 0.2 \
    --scroll-min-distance 2.0 \
    --scroll-max-frequency 20 \
    --scroll-session-timeout 1.0
```

**Scroll filtering parameters:**
- `--scroll-debounce`: Minimum time between scroll events (default: 0.5 seconds)
- `--scroll-min-distance`: Minimum scroll distance to log (default: 5.0 pixels)
- `--scroll-max-frequency`: Maximum scroll events per second (default: 10)
- `--scroll-session-timeout`: Scroll session timeout (default: 2.0 seconds)

## Troubleshooting

### Process Killed After 30 Screenshots (Mac M3)

If the process gets killed after approximately 30 screenshots on Mac M3, this is likely due to memory pressure. The tool has been optimized to address this issue:

**Recent fixes include:**
- Reduced capture frequency from 10 FPS to 5 FPS (3 FPS on high-DPI displays)
- Lower JPEG quality (70% instead of 90%) to reduce file sizes
- Explicit memory cleanup every 30 frames (20 frames on high-DPI displays)
- Proper disposal of old frame objects
- Custom thread pool to prevent thread pool exhaustion
- Better error handling for MSS operations
- Automatic detection of high-DPI displays with conservative settings
- **Scroll filtering**: Reduces unnecessary scroll event logging with configurable debouncing, distance thresholds, and frequency limits

**Additional issues addressed:**
- **Thread pool exhaustion**: Limited thread pool size to 4 workers
- **MSS memory leaks**: Added proper resource cleanup and error handling
- **High-DPI display pressure**: Automatic detection and reduced capture frequency
- **Concurrent file I/O**: Better coordination of file operations
- **Apple Silicon optimization**: Specific handling for ARM64 architecture

**To diagnose system issues:**
```bash
# Run diagnostic tool before starting gum
python diagnose_memory.py
```

**To monitor memory usage:**
```bash
# In a separate terminal
python memory_monitor.py
```

**Additional recommendations:**
1. Close unnecessary applications while recording
2. Ensure you have at least 4GB of free RAM
3. If issues persist, try running with debug mode:
   ```bash
   gum --debug
   ```
4. For high-DPI displays, the tool automatically uses more conservative settings
5. Consider running on a single monitor if using multiple high-resolution displays

### Memory Monitoring

To track memory usage during recording, install the monitoring dependencies and run the memory monitor in a separate terminal:

```bash
# Terminal 1: Run the recording tool
gum

# Terminal 2: Monitor memory usage
python memory_monitor.py
```
