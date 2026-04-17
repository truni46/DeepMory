import os

class QuotaConfig:
    def __init__(self):
        self.sessionLimit = int(os.getenv("TOKEN_SESSION_LIMIT", 500000))
        self.sessionDuration = int(os.getenv("TOKEN_SESSION_DURATION", 7200))
        self.weeklyLimit = int(os.getenv("TOKEN_WEEKLY_LIMIT", 5000000))
        self.warningThreshold = float(os.getenv("TOKEN_WARNING_THRESHOLD", 0.9))

quotaConfig = QuotaConfig()
