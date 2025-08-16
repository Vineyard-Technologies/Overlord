class IrayServerXPaths:

    class navBar:

        SETTINGS = "//a[@href='#settings']"

    class settingsPage:
        GLOBAL_IMAGE_STORAGE_PATH_INPUT = "//input[@name='imageStoragePath']"
        GLOBAL_IMAGE_STORAGE_PATH_SAVE_BUTTON = "//form[@id='imageStoragePathForm']//button"

        GENERATE_ZIP_FILES_SWITCH = "(//div[@id='zipBox']//div[starts-with(@class, 'switch')])[1]"

        SAVED_MESSAGE = "//div[text()='Saved']"

    class loginPage:
        USERNAME_INPUT = "//input[@type='text']"
        PASSWORD_INPUT = "(//input[@type='password'])[1]"
        LOGIN_BUTTON = "//button[text()='Login']"

        # CURRENT_PASSWORD_INPUT = "//input[@name='oldpass']"
        # NEW_PASSWORD_INPUT = "//input[@name='newpass']"
        # CONFIRM_PASSWORD_INPUT = "//input[@name='newpassConfirm']"
        # SAVE_BUTTON = "//button[text()='Save']"
    
    class queuePage:
        DONE_QUANTITY = "//h3[span[@class='item-count'] and contains(., 'Done')]/span[@class='item-count']"
    #     REMOVE_BUTTONS = "//button[@title='Remove']"

    #     DELETE_CONFIRMATION_DIALOG = "//div[@class='modal-content']"
    #     DELETE_BUTTON = "//button[text()='Delete']"

    # @classmethod
    # def job_by_id(cls, job_id):
    #     """Get XPath for a specific job by its ID"""
    #     return f"//tr[td[contains(@class, 'job-id') and contains(text(), '{job_id}')]]"