from __future__ import annotations

import os
import sys
import plistlib
import threading
import logging

# Ensure package is importable when frozen
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(sys.executable))

if __package__ in (None, ""):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

try:
    from ...cli import main
    from ...cli import BackgroundRecorder
except ImportError:
    from gum.cli import main
    from gum.cli import BackgroundRecorder

def _detect_app_version() -> str:
    # Priority: env override, Info.plist in bundled app, fallback
    env_v = os.environ.get("GUM_APP_VERSION")
    if env_v:
        return env_v
    try:
        if getattr(sys, "frozen", False):
            plist_path = os.path.abspath(os.path.join(os.path.dirname(sys.executable), "..", "Info.plist"))
            if os.path.exists(plist_path):
                with open(plist_path, "rb") as f:
                    data = plistlib.load(f)
                    v = data.get("CFBundleShortVersionString") or data.get("CFBundleVersion")
                    if isinstance(v, str) and v.strip():
                        return v.strip()
    except Exception:  # Catches any error during version detection from Info.plist
        pass
    return "0.0"

APP_VERSION = _detect_app_version()


def run():
    try:
        import tkinter as tk
        from tkinter import messagebox
        from tkinter import filedialog
    except Exception:  # Catches tkinter import failures (fallback to CLI mode)
        os.environ.setdefault("PYTHONASYNCIODEBUG", "0")
        try:
            main()
        except KeyboardInterrupt:  # Catches Ctrl+C interruption during CLI fallback
            pass
        return

    try:
        from . import app_entry_utils as ui  # type: ignore
    except ImportError:  # Catches relative import failures (fallback to absolute import)
        from gum.app.macos import app_entry_utils as ui  # type: ignore

    # ------- Settings and defaults -------
    app_support_root = os.path.expanduser("~/Library/Application Support")
    default_output_dir = os.path.join(app_support_root, "Gum Recorder")

    settings_path = os.path.join(default_output_dir, "settings.json")

    settings = ui.load_settings(settings_path, default_output_dir)
    output_dir = settings.get("output_dir", default_output_dir)
    screenshots_dir = os.path.join(output_dir, "screenshots")
    kb_recorder = ui.MainThreadKeyboardRecorderShim()
    output_dir_display_var = None
    output_path_tooltip = None

    def open_output_folder() -> None:
        os.makedirs(output_dir, exist_ok=True)
        ui.open_uri(output_dir)

    def choose_output_folder() -> None:
        nonlocal output_dir, screenshots_dir, output_dir_display_var, output_path_tooltip
        if recording_active["value"]:
            messagebox.showinfo("Recording active", "Stop recording before changing the output folder.")
            return
        selected = filedialog.askdirectory(title="Choose Output Folder", initialdir=output_dir)
        if not selected:
            return
        new_dir = os.path.abspath(os.path.expanduser(selected))
        try:
            os.makedirs(new_dir, exist_ok=True)
            # Preflight write
            test_path = os.path.join(new_dir, ".write_test")
            with open(test_path, "w") as f:
                f.write("ok")
            os.remove(test_path)
        except Exception as e:  # Catches directory creation/write permission failures
            messagebox.showerror("Cannot use folder", f"{new_dir}\nError: {e}")
            return
        output_dir = new_dir
        screenshots_dir = os.path.join(output_dir, "screenshots")
        settings["output_dir"] = output_dir
        ui.save_settings(settings_path, settings)
        status_var.set(f"Output folder set to: {output_dir}")
        if output_dir_display_var is not None:
            output_dir_display_var.set(ui.format_output_dir(output_dir))
        if output_path_tooltip is not None:
            output_path_tooltip.text = os.path.abspath(output_dir)

    start_after_ui = {"value": False}
    recording_active = {"value": False}
    keyboard_enabled = {"value": False}

    # ------- Permission checks (onboarding) -------
    def show_onboarding_if_needed(root_window) -> None:
        if settings.get("onboarding_done", False):
            return

        import tkinter as tk

        top = tk.Toplevel(root_window)
        top.title("Setup Permissions")
        top.grab_set()
        top.transient(root_window)

        def status_to_text(flag: bool | None) -> str:
            if flag is True:
                return "✅ Granted"
            if flag is False:
                return "❌ Not granted"
            return "ℹ️ Unknown"

        sr_status = tk.StringVar(value=status_to_text(ui.check_screen_recording_granted()))
        ax_status = tk.StringVar(value=status_to_text(ui.check_accessibility_granted()))
        im_status = tk.StringVar(value=status_to_text(ui.check_input_monitoring_granted()))
        au_status = tk.StringVar(value=status_to_text(ui.check_automation_granted()))

        row = 0
        tk.Label(top, text="Gum Recorder needs these permissions:", font=("Helvetica", 12, "bold")).grid(row=row, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 8))
        row += 1

        tk.Label(top, text="Screen Recording:").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        tk.Label(top, textvariable=sr_status).grid(row=row, column=1, sticky="w", padx=8)
        tk.Button(top, text="Open", command=lambda: (ui.request_screen_recording_access(), sr_status.set(status_to_text(ui.check_screen_recording_granted())))).grid(row=row, column=2, padx=12)
        row += 1

        tk.Label(top, text="Accessibility:").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        tk.Label(top, textvariable=ax_status).grid(row=row, column=1, sticky="w", padx=8)
        tk.Button(top, text="Open", command=lambda: (ui.prompt_accessibility_access(), ax_status.set(status_to_text(ui.check_accessibility_granted())))).grid(row=row, column=2, padx=12)
        row += 1

        tk.Label(top, text="Input Monitoring (Keyboard):").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        tk.Label(top, textvariable=im_status).grid(row=row, column=1, sticky="w", padx=8)
        tk.Button(top, text="Open", command=lambda: (ui.prompt_input_monitoring_access(), im_status.set(status_to_text(ui.check_input_monitoring_granted())))).grid(row=row, column=2, padx=12)
        row += 1

        tk.Label(top, text="Browser URL Capture:").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        tk.Label(top, textvariable=au_status).grid(row=row, column=1, sticky="w", padx=8)
        tk.Button(
            top,
            text="Enable Browser URLs",
            command=lambda: (ui.prompt_automation_access(), au_status.set(status_to_text(ui.check_automation_granted()))),
        ).grid(row=row, column=2, padx=12)
        row += 1

        tk.Label(
            top,
            text=(
                "Click Enable Browser URLs and approve the prompts for Safari, Chrome, Brave, Edge, or Arc (if installed). "
                "macOS will then open Privacy & Security → Automation so you can confirm Gum Recorder is allowed. "
                "If you're running from Terminal, the prompt may mention 'osascript' instead of Gum Recorder."
            ),
            wraplength=360,
            justify="left",
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 10))
        row += 1

        def finish_onboarding():
            settings["onboarding_done"] = True
            ui.save_settings(settings_path, settings)
            top.destroy()

        tk.Button(top, text="Continue", command=finish_onboarding).grid(row=row, column=2, sticky="e", padx=12, pady=(8, 12))

    def ensure_dirs() -> tuple[bool, str | None]:
        try:
            os.makedirs(screenshots_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)
            # Preflight writability
            test_path = os.path.join(output_dir, ".write_test")
            with open(test_path, "w") as f:
                f.write("ok")
            os.remove(test_path)
            return True, None
        except Exception as e:  # Catches directory creation/write test failures
            return False, str(e)

    def permissions_blocking_message() -> str | None:
        sr = ui.check_screen_recording_granted()
        ax = ui.check_accessibility_granted()
        if sr is False or ax is False:
            return "Screen Recording and Accessibility must be granted before starting. Open the permissions via the buttons, grant access, then relaunch the app."
        return None

    def start_recording() -> None:
        if recording_active["value"]:
            return

        block_msg = permissions_blocking_message()
        if block_msg:
            messagebox.showwarning("Permissions required", block_msg)
            return

        ok, err = ensure_dirs()
        if not ok:
            messagebox.showerror("Cannot write to output folder", f"Directory: {output_dir}\nError: {err}\n\nChoose a different folder or fix permissions.")
            return

        # Allow the main-thread shim to handle keyboard events when available;
        # fall back to the screen observer's internal backends otherwise.
        shim_running = False
        try:
            shim_running = kb_recorder.start()
        except Exception:  # Catches keyboard shim startup failures
            logging.getLogger("GumUI").exception("Keyboard shim failed to start")
            shim_running = False

        input_monitoring_granted = ui.check_input_monitoring_granted() is True
        if shim_running and input_monitoring_granted:
            os.environ["GUM_DISABLE_KEYBOARD"] = "1"
        else:
            os.environ.pop("GUM_DISABLE_KEYBOARD", None)
            if shim_running and not input_monitoring_granted:
                logging.getLogger("GumUI").info(
                    "Input Monitoring permission missing; keeping background keyboard listener active as fallback"
                )

        try:
            BackgroundRecorder.start(
                user_name="anonymous",
                data_directory=output_dir,
                screenshots_dir=screenshots_dir,
                debug=False,
            )
            recording_active["value"] = True
            keyboard_enabled["value"] = shim_running
            if shim_running:
                status_var.set("Recording… (Click Stop to pause)")
            else:
                status_var.set("Recording… (Keyboard fallback active; click Stop to pause)")
            start_btn.config(state=tk.DISABLED)
            stop_btn.config(state=tk.NORMAL)
            if not shim_running:
                logging.getLogger("GumUI").info("Keyboard shim unavailable; relying on background listener")
        except Exception as e:  # Catches BackgroundRecorder startup failures
            if shim_running:
                try:
                    kb_recorder.stop()
                except Exception:  # Catches keyboard shim cleanup failures
                    logging.getLogger("GumUI").exception("Failed to stop keyboard shim after startup error")
                os.environ.pop("GUM_DISABLE_KEYBOARD", None)
            messagebox.showerror("Failed to start", str(e))

    def stop_recording() -> None:
        if not recording_active["value"]:
            return
        try:
            BackgroundRecorder.stop()
            kb_recorder.stop()
            os.environ.pop("GUM_DISABLE_KEYBOARD", None)
            recording_active["value"] = False
            keyboard_enabled["value"] = False
            status_var.set("Stopped. Press Start to record again.")
            start_btn.config(state=tk.NORMAL)
            stop_btn.config(state=tk.DISABLED)
            # No-op; no background keyboard recorder
        except Exception as e:  # Catches BackgroundRecorder stop failures
            messagebox.showerror("Failed to stop", str(e))

    def quit_app() -> None:
        os._exit(0)

    root = tk.Tk()
    root.title(f"Gum Recorder v{APP_VERSION}")
    root.geometry("720x520")
    root.minsize(560, 420)
    root.resizable(True, True)

    frame = tk.Frame(root, padx=16, pady=16)
    frame.pack(fill=tk.BOTH, expand=True)

    title = tk.Label(frame, text=f"Gum Recorder v{APP_VERSION}", font=("Helvetica", 16, "bold"))
    title.pack(anchor="w")

    status_var = tk.StringVar(value="Ready. Grant permissions below, then Start Recording.")
    status = tk.Label(frame, textvariable=status_var)
    status.pack(anchor="w", pady=(8, 12))

    controls = tk.Frame(frame)
    controls.pack(anchor="w")
    start_btn = tk.Button(controls, text="Start Recording", width=18, command=start_recording)
    start_btn.grid(row=0, column=0, padx=(0, 8))
    stop_btn = tk.Button(controls, text="Stop Recording", width=18, command=stop_recording, state=tk.DISABLED)
    stop_btn.grid(row=0, column=1)

    # Permissions block
    btns = tk.Frame(frame)
    btns.pack(anchor="w", pady=(12, 8))

    # Helper for status text
    def _status_to_text(flag: bool | None) -> str:
        if flag is True:
            return "✅ Granted"
        if flag is False:
            return "❌ Not granted"
        return "ℹ️ Unknown"

    sr_status_var = tk.StringVar(value=_status_to_text(ui.check_screen_recording_granted()))
    ax_status_var = tk.StringVar(value=_status_to_text(ui.check_accessibility_granted()))
    im_status_var = tk.StringVar(value=_status_to_text(ui.check_input_monitoring_granted()))
    au_status_var = tk.StringVar(value=_status_to_text(ui.check_automation_granted()))

    tk.Label(btns, text="Screen Recording:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
    tk.Label(btns, textvariable=sr_status_var).grid(row=0, column=1, sticky="w", padx=(0, 12))
    sr_open_btn = tk.Button(btns, text="Open", command=ui.open_screen_recording_settings)
    sr_open_btn.grid(row=0, column=2, padx=(0, 8), pady=(0, 8))
    sr_help_btn = tk.Button(btns, text="How to grant", command=ui.open_screen_recording_help)
    sr_help_btn.grid(row=0, column=3, padx=(0, 8), pady=(0, 8))

    tk.Label(btns, text="Accessibility:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
    tk.Label(btns, textvariable=ax_status_var).grid(row=1, column=1, sticky="w", padx=(0, 12))
    ax_open_btn = tk.Button(btns, text="Open", command=ui.open_accessibility_settings)
    ax_open_btn.grid(row=1, column=2, padx=(0, 8), pady=(0, 8))
    ax_help_btn = tk.Button(btns, text="How to grant", command=ui.open_accessibility_help)
    ax_help_btn.grid(row=1, column=3, padx=(0, 8), pady=(0, 8))

    tk.Label(btns, text="Input Monitoring:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
    tk.Label(btns, textvariable=im_status_var).grid(row=2, column=1, sticky="w", padx=(0, 12))
    im_open_btn = tk.Button(btns, text="Open", command=ui.prompt_input_monitoring_access)
    im_open_btn.grid(row=2, column=2, padx=(0, 8), pady=(0, 8))
    im_help_btn = tk.Button(btns, text="How to grant", command=ui.open_input_monitoring_help)
    im_help_btn.grid(row=2, column=3, padx=(0, 8), pady=(0, 8))

    tk.Label(btns, text="Browser URL Capture:").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
    tk.Label(btns, textvariable=au_status_var).grid(row=3, column=1, sticky="w", padx=(0, 12))
    au_open_btn = tk.Button(btns, text="Enable Browser URLs", command=ui.prompt_automation_access)
    au_open_btn.grid(row=3, column=2, padx=(0, 8), pady=(0, 8))
    au_help_btn = tk.Button(btns, text="How to grant", command=ui.open_automation_help)
    au_help_btn.grid(row=3, column=3, padx=(0, 8), pady=(0, 8))

    def refresh_permission_status():
        sr_status_var.set(_status_to_text(ui.check_screen_recording_granted()))
        ax_status_var.set(_status_to_text(ui.check_accessibility_granted()))
        im_status_var.set(_status_to_text(ui.check_input_monitoring_granted()))
        au_status_var.set(_status_to_text(ui.check_automation_granted()))

    tk.Button(btns, text="Refresh", command=refresh_permission_status).grid(row=0, column=4, rowspan=4, padx=(12, 0))

    # Attach tooltips to all permission helper buttons with no delay for quicker guidance
    ui.Tooltip(sr_help_btn, ui.PERMISSION_TOOLTIPS["screen"], delay=0)
    ui.Tooltip(ax_help_btn, ui.PERMISSION_TOOLTIPS["accessibility"], delay=0)
    ui.Tooltip(im_help_btn, ui.PERMISSION_TOOLTIPS["input"], delay=0)
    ui.Tooltip(au_help_btn, ui.PERMISSION_TOOLTIPS["automation"], delay=0)

    folder_row = tk.Frame(frame)
    folder_row.pack(fill=tk.X, pady=(12, 8))
    folder_row.columnconfigure(1, weight=1)

    tk.Label(folder_row, text="Current Output Path:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))

    output_dir_display_var = tk.StringVar(value=ui.format_output_dir(output_dir))
    output_dir_dropdown = tk.Menubutton(
        folder_row,
        textvariable=output_dir_display_var,
        relief=tk.RAISED,
        indicatoron=True,
        anchor="w",
    )
    output_dir_dropdown.grid(row=0, column=1, sticky="we", pady=(0, 8))

    output_dropdown_menu = tk.Menu(output_dir_dropdown, tearoff=0)
    output_dropdown_menu.add_command(label="Open Output Folder", command=open_output_folder)
    output_dropdown_menu.add_separator()
    output_dropdown_menu.add_command(label="Change Output Folder…", command=choose_output_folder)
    output_dir_dropdown.configure(menu=output_dropdown_menu)

    output_path_tooltip = ui.Tooltip(output_dir_dropdown, os.path.abspath(output_dir), delay=0)

    # Main-thread pump for any queued tasks from keyboard recorder
    # Main-thread pump for keyboard events
    def _pump_keyboard() -> None:
        kb_recorder.pump_main_thread_tasks()
        root.after(50, _pump_keyboard)
    _pump_keyboard()

    # Periodically refresh permission statuses
    def periodic_refresh():
        try:
            refresh_permission_status()
        except Exception:  # Catches permission status refresh failures
            pass
        finally:
            root.after(3000, periodic_refresh)
    periodic_refresh()

    def schedule_screen_preflight() -> None:
        if ui.check_screen_recording_granted() is True:
            return

        def _prime() -> None:
            try:
                ui.prime_screen_recording_permission()
            except Exception:  # Catches screen recording permission preflight failures
                pass

        threading.Thread(name="ScreenRecordingPreflight", target=_prime, daemon=True).start()

    def schedule_accessibility_preflight() -> None:
        if ui.check_accessibility_granted() is True:
            return

        def _prime() -> None:
            try:
                ui.prime_accessibility_permission()
            except Exception:  # Catches accessibility permission preflight failures
                pass

        threading.Thread(name="AccessibilityPreflight", target=_prime, daemon=True).start()

    def schedule_input_preflight() -> None:
        if ui.check_input_monitoring_granted() is True:
            return

        def _prime() -> None:
            try:
                ui.prime_input_monitoring_permission()
            except Exception:  # Catches input monitoring permission preflight failures
                pass

        threading.Thread(name="InputMonitoringPreflight", target=_prime, daemon=True).start()

    def schedule_automation_preflight() -> None:
        if ui.check_automation_granted() is True:
            return

        def _prime() -> None:
            try:
                ui.prime_automation_permissions()
            except Exception:  # Catches automation permission preflight failures
                pass

        threading.Thread(name="AutomationPreflight", target=_prime, daemon=True).start()

    root.after(200, schedule_screen_preflight)
    root.after(300, schedule_accessibility_preflight)
    root.after(400, schedule_input_preflight)
    root.after(500, schedule_automation_preflight)

    # Show onboarding if first run
    show_onboarding_if_needed(root)

    tk.Button(frame, text="Quit", command=quit_app).pack(anchor="e")

    try:
        root.mainloop()
    finally:
        pass


if __name__ == "__main__":
    run()
