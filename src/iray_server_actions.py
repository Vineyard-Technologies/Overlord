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
    
    def find_elements(self, xpath):
        """Helper method to find multiple elements by XPath"""
        return self.driver.find_elements(By.XPATH, xpath)
    
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
            screenshot_path = self._take_error_screenshot(operation_description)
            if screenshot_path:
                log_message += f" - Screenshot saved: {screenshot_path}"
        
        if log_level == "warning":
            logging.warning(log_message)
        else:
            logging.error(log_message)
    
    def _take_error_screenshot(self, operation_description):
        """
        Take a screenshot of the browser window for debugging purposes
        Only used in development mode
        
        Args:
            operation_description: Description of the operation that failed
            
        Returns:
            str: Path to the saved screenshot, or None if failed
        """
        try:
            # Check if driver is still available for screenshots
            if not self.driver:
                logging.warning("Cannot take screenshot: browser driver is None")
                return None
                
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
                logging.info(f"Error screenshot saved to: {screenshot_path}")
                return screenshot_path
            else:
                logging.warning("Failed to save error screenshot")
                return None
                
        except Exception as screenshot_error:
            error_msg = str(screenshot_error)
            if "connection broken" in error_msg.lower() or "connection refused" in error_msg.lower():
                logging.warning("Cannot take screenshot: browser session no longer available")
            else:
                logging.warning(f"Failed to take error screenshot: {screenshot_error}")
            return None
    
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
        
    def start_browser(self):
        """
        Start Firefox WebDriver, navigate to Iray Server, and sign in
        
        Returns:
            bool: True if browser started successfully and signed in, False otherwise
        """
        try:
            # Configure Firefox options
            firefox_options = FirefoxOptions()
            firefox_options.add_argument("--disable-web-security")
            firefox_options.add_argument("--start-maximized")
            firefox_options.add_argument("--headless")
            
            # Start Firefox WebDriver
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

            # After the first successful login, (or if the 'Require password change' switch is enabled)
            # the "Please change your password" popup will appear. It can be bypassed by immediately
            # Browsing to http://127.0.0.1:9090/index.html#queue

            # Navigate to the render queue page after login
            queue_url = f"{self.base_url}/index.html#queue"
            self.driver.get(queue_url)

            # Wait for the queue page to load
            if not self.wait_for_page_ready():
                logging.warning("Render queue page took longer than expected to load")
                return False
            
            logging.info("Navigated to render queue page")
            
            logging.info("Signed in to Iray Server")
            return True
                
        except Exception as e:
            self.log_detailed_error(e, "Failed to start browser and sign in to Iray Server")
            return False
        
    def setup(self, storage_path: str):
        """
        Setup Iray Server by clearing queue and configuring settings
        
        Returns:
            bool: True if setup completed successfully, False otherwise
        """
        # Clear the render queue
        if not self.clear_queue():
            logging.error("Failed to clear render queue")
            return False

        # Configure server settings
        if not self.configure_settings(storage_path):
            logging.error("Failed to configure server settings")
            return False
        
        return True

    def configure_settings(self, storage_path: str):
        """
        Configure Iray Server settings such as image storage path and ZIP generation switch
        """
        if not self.driver:
            logging.error("Browser not started. Call start_browser() first.")
            return False
        
        try:
            # Navigate to settings page
            settings_url = f"{self.base_url}/index.html#settings"
            self.driver.get(settings_url)
            logging.info("Navigated to settings page")
            
            # Wait for settings page to load
            if not self.wait_for_page_ready():
                logging.warning("Settings page took longer than expected to load")
                return False
            
            # Set image storage path
            storage_path_input = self.find_element(IrayServerXPaths.settingsPage.GLOBAL_IMAGE_STORAGE_PATH_INPUT)
            storage_path_input.clear()
            storage_path_input.send_keys(storage_path)
            logging.info(f"Set image storage path to: {storage_path}")
            
            # Click save button to apply the storage path change
            save_button = WebDriverWait(self.driver, self.default_timeout).until(
                EC.element_to_be_clickable((By.XPATH, IrayServerXPaths.settingsPage.GLOBAL_IMAGE_STORAGE_PATH_SAVE_BUTTON))
            )
            save_button.click()
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
            
            return True
            
        except Exception as e:
            self.log_detailed_error(e, "Failed to configure settings")
            return False
    
    def clear_queue(self):
        """
        Clear all items from the render queue
        
        Returns:
            bool: True if queue cleared successfully, False otherwise
        """
        if not self.driver:
            logging.error("Browser not started. Call start_browser() first.")
            return False

        # Check if we're on the correct queue page
        current_url = self.driver.current_url
        expected_url = f"{self.base_url}/index.html#queue"
        if current_url != expected_url:
            raise WebDriverException(f"Not on queue page. Current URL: {current_url}, Expected: {expected_url}")          
            
        try:
            # Click each remove button
            removed_count = 0
            
            # Keep removing until no more buttons are found
            while True:
                # Re-find remove buttons on each iteration to avoid stale element references
                remove_buttons = self.find_elements(IrayServerXPaths.queuePage.REMOVE_BUTTONS)
                
                if not remove_buttons:
                    logging.info("No more items in queue to remove")
                    break
                
                try:
                    # Always click the first button since the list updates after each removal
                    logging.info(f"Clicking remove button 1 of {len(remove_buttons)} (removed {removed_count} so far)")
                    # Wait for the remove button to be clickable before clicking
                    remove_button = WebDriverWait(self.driver, self.default_timeout).until(
                        EC.element_to_be_clickable(remove_buttons[0])
                    )
                    remove_button.click()
                    logging.info(f"Clicked remove button")

                    delete_button = WebDriverWait(self.driver, self.default_timeout).until(
                        EC.element_to_be_clickable((By.XPATH, IrayServerXPaths.queuePage.DELETE_BUTTON))
                    )

                    logging.info(f"Clicking delete button")
                    delete_button.click()
                    logging.info(f"Clicked delete button")

                    # Wait for the modal to disappear before continuing to the next button
                    WebDriverWait(self.driver, self.default_timeout).until(
                        EC.invisibility_of_element_located((By.XPATH, IrayServerXPaths.queuePage.DELETE_CONFIRMATION_DIALOG))
                    )

                    removed_count += 1

                except Exception as e:
                    self.log_detailed_error(e, "Failed to click remove button", "warning")
                    return False
            
            logging.info(f"Removed {removed_count} items from queue")
            return True
            
        except Exception as e:
            self.log_detailed_error(e, "Failed to clear queue")
            return False
    
    def close_browser(self):
        """Close the browser if it's open"""
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