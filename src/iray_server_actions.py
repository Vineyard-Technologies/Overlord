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
from iray_server_xpaths import IrayServerXPaths


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
    
    def find_element(self, xpath):
        """Helper method to find element by XPath"""
        return self.driver.find_element(By.XPATH, xpath)
    
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
                # Check if driver is still available for screenshots
                if self.driver:
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
                else:
                    logging.warning("Cannot take screenshot: browser driver is None")
            except Exception as screenshot_error:
                error_msg = str(screenshot_error)
                if "connection broken" in error_msg.lower() or "connection refused" in error_msg.lower():
                    logging.warning("Cannot take screenshot: browser session no longer available")
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
            global_image_storage_path_input = self.find_element(IrayServerXPaths.settingsPage.GLOBAL_IMAGE_STORAGE_PATH_INPUT)
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

            WebDriverWait(self.driver, 60 * renders_per_session).until(
                EC.text_to_be_present_in_element((By.XPATH, IrayServerXPaths.queuePage.DONE_QUANTITY), str(renders_per_session))
            )
            return True
            
        except Exception as e:
            self.log_detailed_error(e, "Failed to configure Iray Server")
            return False
        finally:
            # Always close browser, even if configuration failed
            if self.driver:
                try:
                    # Try to quit the driver directly without checking responsiveness first
                    # This avoids connection errors when the session is already dead
                    self.driver.quit()
                    logging.info("Browser closed successfully")
                except Exception as e:
                    # Log the error but don't treat it as critical - the browser may already be closed
                    error_msg = str(e)
                    if "connection broken" in error_msg.lower() or "connection refused" in error_msg.lower():
                        logging.info("Browser session was already closed or unreachable")
                    else:
                        logging.warning(f"Error during browser cleanup (non-critical): {e}")
                finally:
                    # Always set driver to None regardless of quit() success
                    self.driver = None
                    # Also clear the driver from cleanup manager to prevent double-quit attempts
                    if self.cleanup_manager and hasattr(self.cleanup_manager, 'browser_driver'):
                        self.cleanup_manager.browser_driver = None