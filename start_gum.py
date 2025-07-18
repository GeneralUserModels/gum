#!/usr/bin/env python3
"""
GUM Application Startup Script

This script starts both the GUM backend API controller and frontend web server
to provide a complete user interface for the GUM (General User Models) system.

Features:
- Concurrent startup of backend and frontend servers
- Automatic browser opening
- Graceful shutdown handling
- Environment validation
- Configurable ports and settings
"""

import asyncio
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Optional, Dict
import getpass

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)  # Don't override existing env vars
except ImportError:
    pass  # python-dotenv not installed, continue without it

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_BACKEND_PORT = 8001
DEFAULT_FRONTEND_PORT = 3000
DEFAULT_USER_NAME = "GUM_User"

class GUMStartup:
    """Manages the startup and shutdown of GUM backend and frontend services."""
    
    def __init__(self, 
                 backend_port: int = DEFAULT_BACKEND_PORT,
                 frontend_port: int = DEFAULT_FRONTEND_PORT,
                 user_name: Optional[str] = None,
                 open_browser: bool = True,
                 verbose: bool = False,
                 show_logs: bool = True):
        """
        Initialize the GUM startup manager.
        
        Args:
            backend_port: Port for the backend API server
            frontend_port: Port for the frontend web server
            user_name: Default user name for GUM operations
            open_browser: Whether to automatically open the browser
            verbose: Enable verbose logging
            show_logs: Whether to show backend/frontend logs in real-time
        """
        self.backend_port = backend_port
        self.frontend_port = frontend_port
        self.user_name = user_name or os.getenv("USER_NAME", DEFAULT_USER_NAME)
        self.open_browser = open_browser
        self.verbose = verbose
        self.show_logs = show_logs
        
        # Process tracking
        self.backend_process: Optional[subprocess.Popen] = None
        self.frontend_process: Optional[subprocess.Popen] = None
        
        # Paths
        self.root_dir = Path(__file__).parent
        self.frontend_dir = self.root_dir / "frontend"
        
        # Set logging level
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Verbose logging enabled")
    
    def get_user_input(self, prompt: str, default: str = "", sensitive: bool = False) -> str:
        """Get user input with optional default value and sensitive input handling."""
        if default:
            display_prompt = f"{prompt} [{default}]: "
        else:
            display_prompt = f"{prompt}: "
        
        if sensitive:
            value = getpass.getpass(display_prompt)
            if not value and default:
                return default
            return value
        else:
            value = input(display_prompt).strip()
            if not value and default:
                return default
            return value
    
    def configure_environment_interactively(self) -> Dict[str, str]:
        """Interactively configure environment variables based on user choices."""
        logger.info("Environment Configuration Setup")
        print("=" * 50)
        print("Let's configure your GUM environment!")
        print("You can press Enter to use default values where shown.")
        print()
        
        config = {}
        
        # Backend configuration
        config["BACKEND_ADDRESS"] = f"http://localhost:{self.backend_port}"
        
        # Get text provider choice
        print("TEXT PROVIDER CONFIGURATION")
        print("Available text providers:")
        print("  1. azure  - Azure OpenAI")
        print("  2. openai - OpenAI API")
        print()
        
        while True:
            text_provider = self.get_user_input("Choose text provider (azure/openai)", "azure").lower()
            if text_provider in ["azure", "openai"]:
                config["TEXT_PROVIDER"] = text_provider
                break
            print("Please choose either 'azure' or 'openai'")
        
        print()
        
        # Configure text provider specific settings
        if config["TEXT_PROVIDER"] == "azure":
            print("AZURE OPENAI CONFIGURATION")
            config["AZURE_OPENAI_API_KEY"] = self.get_user_input(
                "Azure OpenAI API Key", 
                sensitive=True
            )
            config["AZURE_OPENAI_ENDPOINT"] = self.get_user_input(
                "Azure OpenAI Endpoint", 
                "https://your-resource-name.openai.azure.com/"
            )
            config["AZURE_OPENAI_API_VERSION"] = self.get_user_input(
                "Azure OpenAI API Version", 
                "2025-01-01-preview"
            )
            config["AZURE_OPENAI_DEPLOYMENT"] = self.get_user_input(
                "Azure OpenAI Deployment", 
                "gpt-4o"
            )
        else:  # openai
            print("OPENAI CONFIGURATION")
            config["OPENAI_API_KEY"] = self.get_user_input(
                "OpenAI API Key", 
                sensitive=True
            )
        
        print()
        
        # Get vision provider choice
        print("VISION PROVIDER CONFIGURATION")
        print("Available vision providers:")
        print("  1. openrouter - OpenRouter API")
        print()
        
        vision_provider = self.get_user_input("Choose vision provider", "openrouter").lower()
        config["VISION_PROVIDER"] = vision_provider
        
        if vision_provider == "openrouter":
            print("OPENROUTER CONFIGURATION")
            config["OPENROUTER_API_KEY"] = self.get_user_input(
                "OpenRouter API Key", 
                sensitive=True
            )
            config["OPENROUTER_API_URL"] = self.get_user_input(
                "OpenRouter API URL", 
                "https://openrouter.ai/api/v1/chat/completions"
            )
            config["OPENROUTER_MODEL"] = self.get_user_input(
                "OpenRouter Model", 
                "qwen/qwen-2.5-vl-72b-instruct:free"
            )
        
        print()
        
        # Default user configuration
        default_user = self.user_name
        config["DEFAULT_USER_NAME"] = self.get_user_input(
            "Default User Name", 
            default_user
        )
        
        print()
        print("Configuration complete!")
        print("=" * 50)
        
        return config
    
    def apply_environment_config(self, config: Dict[str, str]) -> None:
        """Apply the configuration to the current environment."""
        for key, value in config.items():
            if value:  # Only set non-empty values
                os.environ[key] = value
                if self.verbose and not any(sensitive in key.lower() for sensitive in ['key', 'secret', 'password']):
                    logger.debug(f"Set environment variable: {key}={value}")
    
    def check_required_environment_variables(self) -> bool:
        """Check if all required environment variables are set based on provider configuration."""
        # Get explicitly set providers
        text_provider = os.getenv("TEXT_PROVIDER", "").lower()
        vision_provider = os.getenv("VISION_PROVIDER", "").lower()
        
        # Auto-detect text provider if not explicitly set
        if not text_provider:
            if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
                text_provider = "azure"
                logger.info("Auto-detected text provider: azure")
            elif os.getenv("OPENAI_API_KEY"):
                text_provider = "openai"
                logger.info("Auto-detected text provider: openai")
        
        # Auto-detect vision provider if not explicitly set
        if not vision_provider:
            if os.getenv("OPENROUTER_API_KEY"):
                vision_provider = "openrouter"
                logger.info("Auto-detected vision provider: openrouter")
        
        required_vars = []
        
        # Check text provider requirements
        if text_provider == "azure":
            required_vars.extend([
                "AZURE_OPENAI_API_KEY",
                "AZURE_OPENAI_ENDPOINT",
                "AZURE_OPENAI_API_VERSION",
                "AZURE_OPENAI_DEPLOYMENT"
            ])
        elif text_provider == "openai":
            required_vars.append("OPENAI_API_KEY")
        else:
            # If no provider is detected/configured, we'll need to configure
            logger.info("No text provider configured or detected")
            return False
        
        # Check vision provider requirements
        if vision_provider == "openrouter":
            required_vars.extend([
                "OPENROUTER_API_KEY",
                "OPENROUTER_API_URL",
                "OPENROUTER_MODEL"
            ])
        else:
            # If no provider is detected/configured, we'll need to configure
            logger.info("No vision provider configured or detected")
            return False
        
        # Check if all required variables are present
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.warning(f"Missing required environment variables: {', '.join(missing_vars)}")
            return False
        
        # Set the detected providers in environment if they weren't explicitly set
        if not os.getenv("TEXT_PROVIDER"):
            os.environ["TEXT_PROVIDER"] = text_provider
            logger.debug(f"Set TEXT_PROVIDER to auto-detected value: {text_provider}")
        
        if not os.getenv("VISION_PROVIDER"):
            os.environ["VISION_PROVIDER"] = vision_provider
            logger.debug(f"Set VISION_PROVIDER to auto-detected value: {vision_provider}")
        
        # Set default values for missing optional variables
        if text_provider == "azure" and not os.getenv("AZURE_OPENAI_API_VERSION"):
            os.environ["AZURE_OPENAI_API_VERSION"] = "2025-01-01-preview"
            logger.debug("Set AZURE_OPENAI_API_VERSION to default value")
        
        if text_provider == "azure" and not os.getenv("AZURE_OPENAI_DEPLOYMENT"):
            os.environ["AZURE_OPENAI_DEPLOYMENT"] = "gpt-4o"
            logger.debug("Set AZURE_OPENAI_DEPLOYMENT to default value")
        
        if vision_provider == "openrouter" and not os.getenv("OPENROUTER_API_URL"):
            os.environ["OPENROUTER_API_URL"] = "https://openrouter.ai/api/v1/chat/completions"
            logger.debug("Set OPENROUTER_API_URL to default value")
        
        if vision_provider == "openrouter" and not os.getenv("OPENROUTER_MODEL"):
            os.environ["OPENROUTER_MODEL"] = "qwen/qwen-2.5-vl-72b-instruct:free"
            logger.debug("Set OPENROUTER_MODEL to default value")
        
        return True
    
    def validate_environment(self) -> bool:
        """Validate that the environment is properly configured."""
        logger.info("Validating environment...")
        
        # Check required files exist
        controller_path = self.root_dir / "controller.py"
        frontend_server_path = self.frontend_dir / "server.py"
        requirements_path = self.root_dir / "requirements.txt"
        
        if not controller_path.exists():
            logger.error(f"Backend controller not found: {controller_path}")
            return False
        
        if not frontend_server_path.exists():
            logger.error(f"Frontend server not found: {frontend_server_path}")
            return False
        
        # Check and install dependencies if needed
        if not self.check_dependencies():
            logger.info("Installing missing dependencies...")
            if not self.install_dependencies():
                logger.error("Failed to install dependencies")
                return False
        
        # Check if environment variables are properly configured
        if not self.check_required_environment_variables():
            logger.info("Environment configuration needed...")
            
            # Show what's currently available
            text_keys = ["AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"]
            vision_keys = ["OPENROUTER_API_KEY"]
            
            found_text_keys = [key for key in text_keys if os.getenv(key)]
            found_vision_keys = [key for key in vision_keys if os.getenv(key)]
            
            if found_text_keys or found_vision_keys:
                logger.info("Found some environment variables:")
                if found_text_keys:
                    logger.info(f"  Text provider keys: {', '.join(found_text_keys)}")
                if found_vision_keys:
                    logger.info(f"  Vision provider keys: {', '.join(found_vision_keys)}")
                logger.info("But additional configuration is still required.")
            else:
                logger.info("No API keys found in environment variables.")
            
            print()
            
            # Ask user if they want to configure now
            configure_now = input("Would you like to configure the environment now? (y/N): ").strip().lower()
            if configure_now in ['y', 'yes']:
                config = self.configure_environment_interactively()
                self.apply_environment_config(config)
                
                # Verify configuration was successful
                if not self.check_required_environment_variables():
                    logger.error("Environment configuration failed - missing required variables")
                    return False
                    
                logger.info("Environment configured successfully!")
            else:
                logger.error("Environment configuration is required to run GUM")
                logger.info("Please set the required environment variables or run with configuration")
                return False
        else:
            # Show what was detected/configured
            text_provider = os.getenv("TEXT_PROVIDER", "unknown")
            vision_provider = os.getenv("VISION_PROVIDER", "unknown")
            logger.info(f"Environment variables configured successfully")
            logger.info(f"  Text provider: {text_provider}")
            logger.info(f"  Vision provider: {vision_provider}")
        
        logger.info("Environment validation completed")
        return True
    
    def check_dependencies(self) -> bool:
        """Check if required dependencies are installed."""
        try:
            logger.info("Checking dependencies...")
            
            # List of critical imports to test
            critical_imports = [
                "fastapi",
                "uvicorn", 
                "dateutil",
                "PIL",
                "aiohttp",
                "sqlalchemy",
                "pydantic"
            ]
            
            missing_imports = []
            for module in critical_imports:
                try:
                    __import__(module)
                except ImportError:
                    missing_imports.append(module)
            
            if missing_imports:
                logger.warning(f"Missing dependencies: {', '.join(missing_imports)}")
                return False
            
            logger.info("All critical dependencies are installed")
            return True
            
        except Exception as e:
            logger.error(f"Error checking dependencies: {e}")
            return False
    
    def install_dependencies(self) -> bool:
        """Install missing dependencies from requirements.txt."""
        try:
            requirements_path = self.root_dir / "requirements.txt"
            if not requirements_path.exists():
                logger.error("requirements.txt not found")
                return False
            
            logger.info("Installing dependencies from requirements.txt...")
            
            # Install using pip
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                logger.info("Dependencies installed successfully")
                return True
            else:
                logger.error(f"Failed to install dependencies: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Dependency installation timed out")
            return False
        except Exception as e:
            logger.error(f"Error installing dependencies: {e}")
            return False
    
    def start_backend(self) -> bool:
        """Start the GUM backend API controller."""
        try:
            logger.info(f"Starting GUM backend on port {self.backend_port}...")
            
            # Prepare backend command
            backend_cmd = [
                sys.executable,
                "controller.py",
                "--port", str(self.backend_port),
                "--host", "0.0.0.0"
            ]
            
            # Set environment variables for the backend
            env = os.environ.copy()
            env["DEFAULT_USER_NAME"] = self.user_name
            env["BACKEND_PORT"] = str(self.backend_port)
            
            # Start backend process (show logs for better debugging)
            self.backend_process = subprocess.Popen(
                backend_cmd,
                cwd=self.root_dir,
                env=env,
                stdout=None if self.show_logs else subprocess.PIPE,
                stderr=None if self.show_logs else subprocess.STDOUT,
                text=True
            )
            
            # Wait a bit and check if process started successfully
            time.sleep(2)
            if self.backend_process.poll() is not None:
                logger.error("Backend failed to start")
                return False
            
            logger.info(f"Backend started successfully (PID: {self.backend_process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"Error starting backend: {e}")
            return False
    
    def start_frontend(self) -> bool:
        """Start the GUM frontend web server."""
        try:
            logger.info(f"Starting GUM frontend on port {self.frontend_port}...")
            
            # Set backend address for frontend configuration
            backend_address = f"http://localhost:{self.backend_port}"
            
            # Prepare frontend command
            frontend_cmd = [
                sys.executable,
                "server.py",
                "--port", str(self.frontend_port)
            ]
            
            # Set environment variables for the frontend
            env = os.environ.copy()
            env["BACKEND_ADDRESS"] = backend_address
            env["FRONTEND_PORT"] = str(self.frontend_port)
            
            # Start frontend process (hide logs unless verbose)
            self.frontend_process = subprocess.Popen(
                frontend_cmd,
                cwd=self.frontend_dir,
                env=env,
                stdout=None if self.verbose else subprocess.PIPE,
                stderr=None if self.verbose else subprocess.STDOUT,
                text=True
            )
            
            # Wait a bit and check if process started successfully
            time.sleep(2)
            if self.frontend_process.poll() is not None:
                logger.error("Frontend failed to start")
                return False
            
            logger.info(f"Frontend started successfully (PID: {self.frontend_process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"Error starting frontend: {e}")
            return False
    
    def open_browser_tab(self) -> None:
        """Open the GUM web interface in the default browser."""
        if not self.open_browser:
            return
        
        try:
            url = f"http://localhost:{self.frontend_port}"
            logger.info(f"Opening browser to {url}")
            time.sleep(3)  # Give servers time to fully start
            webbrowser.open(url)
        except Exception as e:
            logger.warning(f"Could not open browser automatically: {e}")
            logger.info(f"Please manually open: http://localhost:{self.frontend_port}")
    
    def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal (Ctrl+C) and handle graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info("\nShutdown signal received...")
            self.shutdown()
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            logger.info("GUM is running! Press Ctrl+C to stop.")
            logger.info(f"Backend API: http://localhost:{self.backend_port}")
            logger.info(f"Frontend UI: http://localhost:{self.frontend_port}")
            logger.info(f"Default User: {self.user_name}")
            logger.info("Backend logs will appear below:")
            logger.info("-" * 50)
            
            # Keep the main process alive and monitor subprocesses
            while True:
                # Check if processes are still running
                if self.backend_process and self.backend_process.poll() is not None:
                    logger.error("Backend process died unexpectedly")
                    logger.error(f"   Exit code: {self.backend_process.returncode}")
                    break
                
                if self.frontend_process and self.frontend_process.poll() is not None:
                    logger.error("Frontend process died unexpectedly")
                    logger.error(f"   Exit code: {self.frontend_process.returncode}")
                    break
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("\nKeyboard interrupt received...")
        finally:
            self.shutdown()
    
    def shutdown(self) -> None:
        """Gracefully shutdown both backend and frontend services."""
        logger.info("Shutting down GUM services...")
        
        # Shutdown frontend
        if self.frontend_process:
            try:
                logger.info("Stopping frontend...")
                self.frontend_process.terminate()
                self.frontend_process.wait(timeout=5)
                logger.info("Frontend stopped")
            except subprocess.TimeoutExpired:
                logger.warning("Frontend didn't stop gracefully, forcing...")
                self.frontend_process.kill()
            except Exception as e:
                logger.error(f"Error stopping frontend: {e}")
        
        # Shutdown backend
        if self.backend_process:
            try:
                logger.info("Stopping backend...")
                self.backend_process.terminate()
                self.backend_process.wait(timeout=10)
                logger.info("Backend stopped")
            except subprocess.TimeoutExpired:
                logger.warning("Backend didn't stop gracefully, forcing...")
                self.backend_process.kill()
            except Exception as e:
                logger.error(f"Error stopping backend: {e}")
        
        logger.info("GUM shutdown complete")
    
    def start(self) -> bool:
        """Start the complete GUM application stack."""
        logger.info("Starting GUM Application Stack...")
        logger.info("=" * 50)
        
        # Validate environment
        if not self.validate_environment():
            return False
        
        # Start backend
        if not self.start_backend():
            self.shutdown()
            return False
        
        # Start frontend
        if not self.start_frontend():
            self.shutdown()
            return False
        
        # Open browser
        self.open_browser_tab()
        
        # Wait for shutdown
        self.wait_for_shutdown()
        return True


def main():
    """Main entry point for the startup script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Start the complete GUM (General User Models) application stack with backend API and web frontend",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Start with defaults
  %(prog)s --backend-port 8002 --verbose     # Custom backend port with verbose logs
  %(prog)s --no-browser --no-logs           # Headless mode without browser or logs
  %(prog)s --user-name "John Doe"            # Set default user name
        """
    )
    
    parser.add_argument(
        "--backend-port", 
        type=int, 
        default=DEFAULT_BACKEND_PORT,
        help="Port for the backend API server"
    )
    
    parser.add_argument(
        "--frontend-port", 
        type=int, 
        default=DEFAULT_FRONTEND_PORT,
        help="Port for the frontend web server"
    )
    
    parser.add_argument(
        "--user-name", 
        type=str,
        help="Default user name for GUM operations"
    )
    
    parser.add_argument(
        "--no-browser", 
        action="store_true",
        help="Don't automatically open the browser"
    )
    
    parser.add_argument(
        "--no-logs", 
        action="store_true",
        help="Hide backend logs (keep startup script logs only)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging for all components"
    )
    
    args = parser.parse_args()
    
    # Create and start the GUM application
    gum_app = GUMStartup(
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        user_name=args.user_name,
        open_browser=not args.no_browser,
        verbose=args.verbose,
        show_logs=not args.no_logs
    )
    
    success = gum_app.start()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
