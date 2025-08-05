class IrayServerXPaths:

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