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
        Start Firefox WebDriver and navigate to Iray Server
        
        Returns:
            bool: True if browser started successfully, False otherwise
        """
        try:
            # Configure Firefox options
            firefox_options = FirefoxOptions()
            firefox_options.add_argument("--disable-web-security")
            firefox_options.add_argument("--start-maximized")
            
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
                return True
            except TimeoutException:
                logging.warning("Iray Server web interface took longer than expected to load")
                return False
                
        except Exception as e:
            logging.error(f"Failed to start browser and open Iray Server web interface: {e}")
            return False
    
    def sign_in(self, username="admin", password="admin"):
        """
        Sign into the Iray Server web interface
        
        Args:
            username (str): Username for login (default: "admin")
            password (str): Password for login (default: "admin")
            
        """
        username_input = self.find_element(IrayServerXPaths.loginPage.USERNAME_INPUT)
        password_input = self.find_element(IrayServerXPaths.loginPage.PASSWORD_INPUT)
        login_button = self.find_element(IrayServerXPaths.loginPage.LOGIN_BUTTON)

        USERNAME = "admin";
        # This is OK to commit because it's on 127.0.0.1
        PASSWORD = "John3:16";

        username_input.send_keys(USERNAME)
        password_input.send_keys(PASSWORD)
        login_button.click()
    
    def clear_queue(self):
        """
        Clear all items from the render queue
        
        Returns:
            bool: True if queue cleared successfully, False otherwise
        """
        if not self.driver:
            logging.error("Browser not started. Call start_browser() first.")
            return False
            
        try:
            # Find all remove buttons
            remove_buttons = self.find_elements(IrayServerXPaths.queuePage.REMOVE_BUTTONS)
            
            if not remove_buttons:
                logging.info("No items in queue to remove")
                return True
            
            # Click each remove button
            removed_count = 0
            for button in remove_buttons:
                try:
                    button.click()
                    removed_count += 1
                    time.sleep(0.5)  # Brief pause between clicks
                except Exception as e:
                    logging.warning(f"Failed to click remove button: {e}")
                    continue
            
            logging.info(f"Removed {removed_count} items from queue")
            return True
            
        except Exception as e:
            logging.error(f"Failed to clear queue: {e}")
            return False
    
    def close_browser(self):
        """Close the browser if it's open"""
        if self.driver:
            try:
                self.driver.quit()
                logging.info("Browser closed successfully")
            except Exception as e:
                logging.error(f"Error closing browser: {e}")
            finally:
                self.driver = None
    
    def is_browser_open(self):
        """
        Check if browser is currently open and responsive
        
        Returns:
            bool: True if browser is open and responsive, False otherwise
        """
        if not self.driver:
            return False
            
        try:
            # Try to get current URL to test if browser is responsive
            _ = self.driver.current_url
            return True
        except Exception:
            return False


def demo_iray_server_login(cleanup_manager=None, username="admin", password="admin"):
    """
    Demonstration function showing how to use the IrayServerActions class
    to open browser, sign in, and perform basic operations.
    
    Args:
        cleanup_manager: Optional cleanup manager for browser driver registration
        username (str): Username for login
        password (str): Password for login
        
    Returns:
        IrayServerActions: The actions instance for further operations, or None if failed
    """
    try:
        # Create actions instance
        actions = IrayServerActions(cleanup_manager)
        
        # Start browser
        if not actions.start_browser():
            logging.error("Failed to start browser")
            return None
        
        # Sign in
        if not actions.sign_in(username, password):
            logging.error("Failed to sign in")
            actions.close_browser()
            return None
        
        # Navigate to queue (optional)
        if actions.navigate_to_queue():
            logging.info("Successfully navigated to queue page")
        
        return actions
        
    except Exception as e:
        logging.error(f"Demo login failed: {e}")
        return None
