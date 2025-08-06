"""
Iray Server web interface automation using Selenium.

This module handles all Selenium-based interactions with the Iray Server web interface,
including browser management, login, and various server operations.
"""

import logging
import time
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
            try:
                WebDriverWait(self.driver, self.default_timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                logging.info("Iray Server web interface loaded successfully")
            except TimeoutException:
                logging.warning("Iray Server web interface took longer than expected to load")
                return False
            
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
            try:
                WebDriverWait(self.driver, self.default_timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                logging.info("Navigated to render queue page")
            except TimeoutException:
                logging.warning("Render queue page took longer than expected to load")
                return False
            
            logging.info("Signed in to Iray Server")
            return True
                
        except Exception as e:
            logging.error(f"Failed to start browser and sign in to Iray Server: {e}")
            return False
        
    def setup(self, storage_path: str):
        
        self.clear_queue()

        self.configure_settings(storage_path)

    def configure_settings(self, storage_path: str):
        """
        Configure Iray Server settings such as image storage path and ZIP generation switch
        """
        if not self.driver:
            logging.error("Browser not started. Call start_browser() first.")
            return False
        
        try:
            # Navigate to settings page
            self.find_element(IrayServerXPaths.navBar.SETTINGS).click()
            logging.info("Navigated to settings page")
            
            # Wait for settings page to load
            WebDriverWait(self.driver, self.default_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Set image storage path
            storage_path_input = self.find_element(IrayServerXPaths.settingsPage.IMAGE_STORAGE_PATH_INPUT)
            storage_path_input.clear()
            storage_path_input.send_keys(storage_path)
            logging.info(f"Set image storage path to: {storage_path}")
            
            # Click save button to apply the storage path change
            save_button = WebDriverWait(self.driver, self.default_timeout).until(
                EC.element_to_be_clickable((By.XPATH, IrayServerXPaths.settingsPage.GLOBAL_IMAGE_STORAGE_PATH_SAVE_BUTTON))
            )
            save_button.click()
            logging.info("Saved image storage path settings")
            
            # Ensure ZIP generation switch is toggled off
            zip_switch = self.find_element(IrayServerXPaths.settingsPage.GENERATE_ZIP_FILES_SWITCH)
            
            # Check if the switch is currently enabled (we want it disabled)
            # If switch is on, class will be "switch on", if off, class will be just "switch"
            switch_class = zip_switch.get_attribute("class")
            if "switch on" in switch_class:
                zip_switch.click()
                logging.info("Turned off ZIP generation switch")
            else:
                logging.info("ZIP generation switch already off")
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to configure settings: {e}")
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
                    logging.warning(f"Failed to click remove button: {e}")
                    break
            
            logging.info(f"Removed {removed_count} items from queue")
            return True
            
        except Exception as e:
            logging.error(f"Failed to clear queue: {e}")
            return False
    
    def close_browser(self):
        """Close the browser if it's open"""
        if self.driver:
            try:
                # Check if driver is still responsive before attempting to quit
                try:
                    # Try a simple operation to check if the session is still active
                    self.driver.current_url
                except Exception:
                    # Session is already dead, just set driver to None
                    logging.info("Browser session already closed")
                    self.driver = None
                    return
                
                # If we get here, the session is still active, so we can safely quit
                self.driver.quit()
                logging.info("Browser closed successfully")
            except Exception as e:
                logging.error(f"Error closing browser: {e}")
            finally:
                self.driver = None