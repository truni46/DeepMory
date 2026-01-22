from typing import Dict
from config.database import db
from config.logger import logger


class SettingsService:
    """Service for managing application settings"""
    
    DEFAULT_SETTINGS = {
        'communication_mode': 'streaming',
        'theme': 'dark-green',
        'show_timestamps': True,
        'ai_response_speed': 'medium'
    }
    
    @staticmethod
    async def get_all_settings() -> Dict:
        """Get all settings"""
        try:
            settings = await db.get_settings()
            
            # Merge with defaults for any missing keys
            final_settings = {**SettingsService.DEFAULT_SETTINGS, **settings}
            
            logger.info("Retrieved settings")
            return final_settings
        except Exception as e:
            logger.error(f"Error getting settings: {e}")
            return SettingsService.DEFAULT_SETTINGS.copy()
    
    @staticmethod
    async def update_settings(updates: Dict) -> Dict:
        """Update settings"""
        try:
            # Update each setting
            for key, value in updates.items():
                await db.update_setting(key, value)
            
            logger.info(f"Updated {len(updates)} settings")
            
            # Return all settings
            return await SettingsService.get_all_settings()
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            raise
    
    @staticmethod
    async def reset_settings() -> Dict:
        """Reset settings to defaults"""
        try:
            # Reset all settings to defaults
            for key, value in SettingsService.DEFAULT_SETTINGS.items():
                await db.update_setting(key, value)
            
            logger.info("Reset settings to defaults")
            return SettingsService.DEFAULT_SETTINGS.copy()
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            raise


# Export instance
settings_service = SettingsService()
