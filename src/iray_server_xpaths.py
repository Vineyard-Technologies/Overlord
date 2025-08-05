class IrayServerXPaths:

    class navBar:

        SETTINGS = "//a[@href='#settings']"

    class settingsPage:
        GLOBAL_IMAGE_STORAGE_PATH_INPUT = "//input[@name='imageStoragePath']"
        GLOBAL_IMAGE_STORAGE_PATH_SAVE_BUTTON = "//form[@id='imageStoragePathForm']//button"

        GENERATE_ZIP_FILES_SWITCH = "(//div[@id='zipBox']//div[starts-with(@class, 'switch')])[1]"

    class loginPage:
        USERNAME_INPUT = "//input[@type='text']"
        PASSWORD_INPUT = "//input[@type='password']"
        LOGIN_BUTTON = "//button"
    
    class queuePage:
        REMOVE_BUTTONS = "//button[@title='Remove']"

    # @classmethod
    # def job_by_id(cls, job_id):
    #     """Get XPath for a specific job by its ID"""
    #     return f"//tr[td[contains(@class, 'job-id') and contains(text(), '{job_id}')]]"