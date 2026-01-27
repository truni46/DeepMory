from typing import Dict, Any
import json
from config.database import db
from config.logger import logger

class SettingsService:
    """Service for managing user-specific settings"""
    
    DEFAULT_SETTINGS = {
        'communication_mode': 'streaming',
        'theme': 'light-green',
        'show_timestamps': True,
        'ai_response_speed': 'medium'
    }
    
    @staticmethod
    async def get_user_settings(user_id: str) -> Dict:
        """Get settings for a specific user"""
        try:
            if not db.pool:
                logger.warning("DB not connected, returning defaults")
                return SettingsService.DEFAULT_SETTINGS.copy()
                
            async with db.pool.acquire() as conn:
                # Fetch preferences column
                row = await conn.fetchrow("SELECT preferences FROM users WHERE id = $1", user_id)
                
                if row and row['preferences']:
                    user_prefs = json.loads(row['preferences']) if isinstance(row['preferences'], str) else row['preferences']
                    # Merge with defaults
                    return {**SettingsService.DEFAULT_SETTINGS, **user_prefs}
                
                return SettingsService.DEFAULT_SETTINGS.copy()
        except Exception as e:
            logger.error(f"Error getting user settings: {e}")
            return SettingsService.DEFAULT_SETTINGS.copy()
    
    @staticmethod
    async def update_user_settings(user_id: str, updates: Dict) -> Dict:
        """Update settings for a specific user"""
        try:
            # Get current settings first to merge
            current = await SettingsService.get_user_settings(user_id)
            new_settings = {**current, **updates}
            
            if not db.pool:
                 logger.warning("DB not connected, cannot save settings")
                 return new_settings

            async with db.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET preferences = $1 WHERE id = $2",
                    json.dumps(new_settings), user_id
                )
            
            logger.info(f"Updated settings for user {user_id}")
            return new_settings
        except Exception as e:
            logger.error(f"Error updating user settings: {e}")
            raise

# Export instance
settings_service = SettingsService()
