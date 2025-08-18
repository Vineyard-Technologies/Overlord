"""
Iray Server web interface automation using Selenium.

This module handles all Selenium-based interactions with the Iray Server web interface,
including browser management, login, and various server operations.
"""

import logging
import time
import sys
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
try:
    from iray_server_xpaths import IrayServerXPaths
except ImportError:
    # Try relative import if absolute import fails
    from .iray_server_xpaths import IrayServerXPaths

# Suppress urllib3 connection pool warnings from Selenium WebDriver
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging levels to suppress connection pool warnings
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)

# Increase the default connection pool settings to prevent pool exhaustion
try:
    # Configure pool manager defaults to handle more connections
    urllib3.poolmanager.DEFAULT_POOLBLOCK = False
    urllib3.poolmanager.DEFAULT_POOLSIZE = 50
    urllib3.poolmanager.DEFAULT_RETRIES = 3
except AttributeError:
    # Fallback if urllib3 structure changes in future versions
    pass


class IrayServerActions:
    """Handles all Selenium-based interactions with the Iray Server web interface"""
    
    def __init__(self, cleanup_manager=None):
        """
        Initialize the Iray Server Actions handler
        
        Args:
            cleanup_manager: Optional cleanup manager to register browser driver for cleanup
        """
        self.driver = None
        self.cleanup_manager = cleanup_manager
        self.base_url = "http://127.0.0.1:9090"
        self.default_timeout = 10
        self.stop_requested = False  # Flag to signal when operations should stop
    
    def find_element(self, xpath):
        """Helper method to find element by XPath"""
        return self.driver.find_element(By.XPATH, xpath)
    
    def is_session_valid(self):
        """
        Check if the WebDriver session is still valid and active
        
        Returns:
            bool: True if session is valid, False otherwise
        """
        if not self.driver:
            return False
        
        try:
            # Try a simple operation that requires an active session
            self.driver.current_url
            return True
        except Exception as e:
            error_msg = str(e).lower()
            if any(phrase in error_msg for phrase in [
                "without establishing a connection", "invalidsessionid",
                "session not created", "session deleted", "connection refused"
            ]):
                return False
            # For other exceptions, assume session might still be valid
            return False
    
    def request_stop(self):
        """
        Signal that all operations should stop (called when Stop Render is clicked)
        """
        self.stop_requested = True
        logging.debug("Stop requested for IrayServerActions")
    
    def cleanup_driver(self):
        """
        Clean up the WebDriver session safely and ensure all connections are closed
        """
        if self.driver:
            try:
                # Check if the session is still valid before attempting operations
                session_active = self.is_session_valid()
                
                if session_active:
                    # Only try to close windows if session is still active
                    try:
                        handles = self.driver.window_handles
                        for handle in handles:
                            try:
                                self.driver.switch_to.window(handle)
                                self.driver.close()
                            except Exception:
                                pass  # Ignore individual window close errors
                    except Exception:
                        pass  # Ignore if window operations fail
                
                # Always attempt to quit, even if session appears inactive
                self.driver.quit()
                logging.info("WebDriver session closed successfully")
            except Exception as e:
                error_msg = str(e)
                if any(phrase in error_msg.lower() for phrase in [
                    "connection broken", "connection refused", 
                    "without establishing a connection", "invalidsessionid",
                    "session not created", "session deleted"
                ]):
                    logging.info("WebDriver session was already closed or unreachable")
                else:
                    logging.warning(f"Error during WebDriver cleanup (non-critical): {e}")
            finally:
                self.driver = None
                if self.cleanup_manager and hasattr(self.cleanup_manager, 'browser_driver'):
                    self.cleanup_manager.browser_driver = None
                
                # Set stop flag to signal any running operations to exit
                self.stop_requested = True
                
                # Give urllib3 a moment to clean up connections
                import time
                time.sleep(0.1)
    
    def log_detailed_error(self, e, operation_description, log_level="error"):
        """
        Helper method to log detailed error information and take screenshot in dev mode
        
        Args:
            e: The exception object
            operation_description: Description of the operation that failed
            log_level: Logging level ("error" or "warning")
        """
        error_type = type(e).__name__
        error_message = str(e) if str(e) else "No error message"
        error_args = getattr(e, 'args', ())
        
        log_message = f"{operation_description} - Type: {error_type}, Message: '{error_message}', Args: {error_args}"
        
        # Take screenshot in development mode only
        screenshot_path = None
        if not getattr(sys, 'frozen', False) and self.driver:
            try:
                # Check if driver session is still valid before attempting screenshot
                if self.driver and self.is_session_valid():
                    # Create screenshots directory in user's Pictures folder
                    user_profile = os.environ.get('USERPROFILE') or os.path.expanduser('~')
                    screenshots_dir = os.path.join(user_profile, 'Pictures', 'Overlord Error Screenshots')
                    os.makedirs(screenshots_dir, exist_ok=True)
                    
                    # Create filename with timestamp and operation description
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    # Clean operation description for filename
                    clean_operation = "".join(c for c in operation_description if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    clean_operation = clean_operation.replace(' ', '_')
                    
                    filename = f"iray_error_{timestamp}_{clean_operation}.png"
                    screenshot_path = os.path.join(screenshots_dir, filename)
                    
                    # Take screenshot
                    if self.driver.save_screenshot(screenshot_path):
                        logging.info(f"Error screenshot saved to: '{screenshot_path}'")
                    else:
                        logging.warning("Failed to save error screenshot")
                        screenshot_path = None
                elif self.driver:
                    logging.debug("Cannot take screenshot: browser session is no longer valid")
                else:
                    logging.debug("Cannot take screenshot: browser driver is None")
            except Exception as screenshot_error:
                error_msg = str(screenshot_error).lower()
                if any(phrase in error_msg for phrase in [
                    "connection broken", "connection refused", "max retries exceeded",
                    "without establishing a connection", "invalidsessionid",
                    "failed to establish a new connection"
                ]):
                    logging.debug("Cannot take screenshot: browser session no longer available")
                else:
                    logging.warning(f"Failed to take error screenshot: {screenshot_error}")
                screenshot_path = None
        
        if screenshot_path:
            log_message += f" - Screenshot saved: '{screenshot_path}'"
        
        if log_level == "warning":
            logging.warning(log_message)
        else:
            logging.error(log_message)
    
    def wait_for_page_ready(self):
        """
        Wait for the page to be fully loaded and JavaScript to finish executing
        """
        try:
            # First wait for document ready state
            WebDriverWait(self.driver, self.default_timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Wait for jQuery to finish loading if present
            WebDriverWait(self.driver, self.default_timeout).until(
                lambda driver: driver.execute_script("return typeof jQuery === 'undefined' || jQuery.active === 0")
            )
            
            # Additional wait to ensure all dynamic content is loaded
            time.sleep(0.5)
            
            logging.info("Page is fully loaded and ready")
            return True
            
        except TimeoutException:
            logging.warning("Page took longer than expected to fully load")
            return False
        except Exception as e:
            self.log_detailed_error(e, "Error waiting for page to be ready")
            return False

    def wait_for_saved_message(self, operation_description="operation"):
        """
        Wait for the saved message to appear and then disappear
        
        Args:
            operation_description: Description of the operation for logging purposes
        """
        try:
            # Wait for saved message to appear
            WebDriverWait(self.driver, self.default_timeout).until(
                EC.presence_of_element_located((By.XPATH, IrayServerXPaths.settingsPage.SAVED_MESSAGE))
            )
            # Wait for saved message to disappear
            WebDriverWait(self.driver, self.default_timeout).until(
                EC.invisibility_of_element_located((By.XPATH, IrayServerXPaths.settingsPage.SAVED_MESSAGE))
            )
            logging.info(f"{operation_description} confirmation message appeared and disappeared")
        except TimeoutException:
            logging.warning(f"{operation_description} confirmation message did not appear or disappear as expected")

    def configure_server(self, storage_path: str, renders_per_session: int):
        """
        Configure Iray Server by starting browser, configuring settings, and closing browser
        
        Args:
            storage_path: Path for image storage
            
        Returns:
            bool: True if configuration completed successfully, False otherwise
        """
        try:
            # Start Firefox WebDriver
            firefox_options = FirefoxOptions()
            firefox_options.add_argument("--disable-web-security")
            firefox_options.add_argument("--start-maximized")
            firefox_options.add_argument("--headless")
            
            # Add connection management options to reduce connection pool warnings
            firefox_options.add_argument("--disable-dev-shm-usage")
            firefox_options.add_argument("--no-sandbox")
            firefox_options.add_argument("--disable-gpu")
            firefox_options.add_argument("--disable-features=VizDisplayCompositor")
            
            # Set Firefox preferences to optimize connection handling
            firefox_options.set_preference("network.http.max-connections", 10)
            firefox_options.set_preference("network.http.max-connections-per-server", 5)
            firefox_options.set_preference("network.http.max-persistent-connections-per-server", 2)
            
            self.driver = webdriver.Firefox(options=firefox_options)
            logging.info("Successfully started Firefox WebDriver")
            
            # Register driver for cleanup if cleanup manager is available
            if self.cleanup_manager:
                self.cleanup_manager.register_browser_driver(self.driver)
            
            # Navigate to the Iray Server web interface
            url = f"{self.base_url}/index.html#login"
            self.driver.get(url)
            logging.info(f"Opened Iray Server web interface: {url}")
            
            # Wait for the page to load
            if not self.wait_for_page_ready():
                logging.warning("Iray Server web interface took longer than expected to load")
                return False
            
            logging.info("Iray Server web interface loaded successfully")
            
            # Sign in automatically
            username_input = self.find_element(IrayServerXPaths.loginPage.USERNAME_INPUT)
            password_input = self.find_element(IrayServerXPaths.loginPage.PASSWORD_INPUT)
            login_button = self.find_element(IrayServerXPaths.loginPage.LOGIN_BUTTON)

            USERNAME = "admin"
            PASSWORD = "admin"

            username_input.send_keys(USERNAME)
            password_input.send_keys(PASSWORD)
            login_button.click()
            logging.info("Signed in to Iray Server")

            # After the first successful login, (or if the 'Require password change' switch is enabled)
            # the "Please change your password" popup will appear. It can be bypassed by immediately
            # browsing to any page

            # Navigate to the settings page after login
            settings_url = f"{self.base_url}/index.html#settings"
            self.driver.get(settings_url)
            logging.info("Navigated to settings page")

            # Wait for the settings page to load
            if not self.wait_for_page_ready():
                logging.warning("Settings page took longer than expected to load")
                return False
            
            # Set image storage path
            # Wait for the image storage path input to be present before interacting
            global_image_storage_path_input = WebDriverWait(self.driver, self.default_timeout).until(
                EC.presence_of_element_located((By.XPATH, IrayServerXPaths.settingsPage.GLOBAL_IMAGE_STORAGE_PATH_INPUT))
            )
            global_image_storage_path_input.clear()
            global_image_storage_path_input.send_keys(storage_path.replace('/', '\\'))
            logging.info(f"Set image storage path to: {storage_path}")
            
            # Click save button to apply the storage path change
            global_image_storage_path_save_button = WebDriverWait(self.driver, self.default_timeout).until(
                EC.element_to_be_clickable((By.XPATH, IrayServerXPaths.settingsPage.GLOBAL_IMAGE_STORAGE_PATH_SAVE_BUTTON))
            )
            global_image_storage_path_save_button.click()
            logging.info("Saved image storage path settings")
            
            # Wait for the saved message to appear and then disappear
            self.wait_for_saved_message("Save")
            
            # Ensure ZIP generation switch is toggled off
            zip_switch = self.find_element(IrayServerXPaths.settingsPage.GENERATE_ZIP_FILES_SWITCH)
            
            # Check if the switch is currently enabled (we want it disabled)
            # If switch is on, class will be "switch on", if off, class will be just "switch"
            switch_class = zip_switch.get_attribute("class")
            if "switch on" in switch_class:
                zip_switch.click()
                logging.info("Turned off ZIP generation switch")
                
                # Wait for the saved message to appear and then disappear after toggling switch
                self.wait_for_saved_message("ZIP switch toggle")
            else:
                logging.info("ZIP generation switch already off")

            # Navigate to the queue page after configuring settings
            queue_url = f"{self.base_url}/index.html#queue"
            self.driver.get(queue_url)
            logging.info(f"Navigated to queue page: {queue_url}")

            # Wait for the queue page to load
            if not self.wait_for_page_ready():
                logging.warning("Queue page took longer than expected to load")
                return False

            # Configuration is complete - return True immediately
            # The caller can start a background thread to wait for renders to complete
            logging.info("Iray Server configuration completed successfully")
            return True
            
        except Exception as e:
            self.log_detailed_error(e, "Failed to configure Iray Server")
            # Close browser on configuration failure
            self.cleanup_driver()
            return False
        # Note: browser is kept open on success for background render monitoring

    def wait_for_render_completion(self, renders_per_session: int, completion_callback=None):
        """
        Wait for all renders to complete by monitoring the DONE_QUANTITY element.
        This method should be called in a background thread after configure_server() succeeds.
        
        Args:
            renders_per_session: Expected number of completed renders
            completion_callback: Optional callback function to call when renders complete successfully
            
        Returns:
            bool: True if all renders completed successfully, False otherwise
        """
        try:
            if not self.driver:
                logging.error("Cannot wait for render completion: browser driver not available")
                return False
            
            # Check if stop has been requested
            if self.stop_requested:
                logging.info("Render completion check stopped due to stop request")
                return False
            
            # Check if session is still valid before proceeding
            if not self.is_session_valid():
                logging.info("Cannot wait for render completion: browser session is no longer valid")
                return False
                
            # Wait for the expected number of renders to complete
            # Use a custom condition that also checks for stop requests
            def wait_condition(driver):
                if self.stop_requested:
                    return True  # Exit the wait
                try:
                    element = driver.find_element(By.XPATH, IrayServerXPaths.queuePage.DONE_QUANTITY)
                    return element.text.strip() == str(renders_per_session)
                except Exception:
                    return False
            
            WebDriverWait(self.driver, 60 * renders_per_session).until(wait_condition)
            
            # Check if we exited due to stop request
            if self.stop_requested:
                logging.info("Render completion check stopped due to stop request")
                return False
            
            # Verify the completion by checking the actual element value
            try:
                # Double-check session validity before accessing elements
                if not self.is_session_valid():
                    logging.info("Browser session became invalid during render completion check")
                    return False
                
                done_elem = self.find_element(IrayServerXPaths.queuePage.DONE_QUANTITY)
                done_text = (done_elem.text or '').strip()
                
                # Extract numeric characters and compare
                numeric = ''.join(ch for ch in done_text if ch.isdigit())
                if numeric and int(numeric) == renders_per_session:
                    logging.info(f"All {renders_per_session} renders completed successfully")
                    
                    # Call the completion callback if provided
                    if completion_callback:
                        try:
                            completion_callback()
                            logging.info("Render completion callback executed successfully")
                        except Exception as cb_e:
                            logging.error(f"Error in render completion callback: {cb_e}")
                    
                    return True
                else:
                    logging.warning(f"DONE_QUANTITY shows '{done_text}' but expected {renders_per_session}")
                    return False
            except Exception as e:
                # Check if this is a session-related error before logging as an error
                error_msg = str(e).lower()
                if any(phrase in error_msg for phrase in [
                    "without establishing a connection", "invalidsessionid",
                    "session not created", "session deleted", "connection refused",
                    "max retries exceeded", "failed to establish a new connection"
                ]):
                    logging.info("Render completion check stopped due to invalid browser session")
                    return False
                else:
                    self.log_detailed_error(e, "Error verifying render completion")
                    return False
                
        except TimeoutException:
            # Check if timeout was due to session being closed
            if not self.is_session_valid():
                logging.info("Render completion check stopped due to invalid browser session")
                return False
            else:
                logging.warning(f"Timeout waiting for {renders_per_session} renders to complete")
                return False
        except Exception as e:
            # Check if this is a session-related error
            error_msg = str(e).lower()
            if any(phrase in error_msg for phrase in [
                "without establishing a connection", "invalidsessionid",
                "session not created", "session deleted", "connection refused",
                "max retries exceeded", "failed to establish a new connection"
            ]):
                logging.info("Render completion check stopped due to invalid browser session")
                return False
            else:
                self.log_detailed_error(e, "Error waiting for render completion")
                return False
        finally:
            # Only close browser if session is still valid
            if self.driver and self.is_session_valid():
                self.cleanup_driver()
            elif self.driver:
                # Session is invalid, just clean up the reference
                self.driver = None