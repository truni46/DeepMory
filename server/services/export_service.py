import json
from typing import Dict, List
from datetime import datetime
from services.conversation_service import conversation_service
from services.history_service import history_service
from config.logger import logger


class ExportService:
    """Service for exporting conversations"""
    
    @staticmethod
    async def export_as_json(conversation_id: str) -> Dict:
        """Export conversation as JSON"""
        try:
            conversation = await conversation_service.get_conversation_by_id(conversation_id)
            messages = await history_service.get_chat_history(conversation_id)
            
            export_data = {
                'conversation': conversation,
                'messages': messages,
                'exported_at': datetime.now().isoformat(),
                'format': 'json'
            }
            
            logger.info(f"Exported conversation {conversation_id} as JSON")
            return export_data
        except Exception as e:
            logger.error(f"Error exporting conversation as JSON: {e}")
            raise
    
    @staticmethod
    async def export_as_text(conversation_id: str) -> str:
        """Export conversation as plain text"""
        try:
            conversation = await conversation_service.get_conversation_by_id(conversation_id)
            messages = await history_service.get_chat_history(conversation_id)
            
            lines = [
                f"Conversation: {conversation.get('title', 'Untitled')}",
                f"Created: {conversation.get('created_at', 'Unknown')}",
                f"Exported: {datetime.now().isoformat()}",
                "=" * 60,
                ""
            ]
            
            for msg in messages:
                role = msg.get('role', 'unknown').upper()
                content = msg.get('content', '')
                timestamp = msg.get('created_at', '')
                
                lines.append(f"[{role}] {timestamp}")
                lines.append(content)
                lines.append("")
            
            text = "\n".join(lines)
            logger.info(f"Exported conversation {conversation_id} as text")
            return text
        except Exception as e:
            logger.error(f"Error exporting conversation as text: {e}")
            raise
    
    @staticmethod
    async def export_as_markdown(conversation_id: str) -> str:
        """Export conversation as Markdown"""
        try:
            conversation = await conversation_service.get_conversation_by_id(conversation_id)
            messages = await history_service.get_chat_history(conversation_id)
            
            lines = [
                f"# {conversation.get('title', 'Untitled Conversation')}",
                "",
                f"**Created:** {conversation.get('created_at', 'Unknown')}  ",
                f"**Exported:** {datetime.now().isoformat()}",
                "",
                "---",
                ""
            ]
            
            for msg in messages:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                timestamp = msg.get('created_at', '')
                
                if role == 'user':
                    lines.append(f"### 👤 User")
                elif role == 'assistant':
                    lines.append(f"### 🤖 Assistant")
                else:
                    lines.append(f"### {role.title()}")
                
                lines.append(f"*{timestamp}*")
                lines.append("")
                lines.append(content)
                lines.append("")
            
            markdown = "\n".join(lines)
            logger.info(f"Exported conversation {conversation_id} as markdown")
            return markdown
        except Exception as e:
            logger.error(f"Error exporting conversation as markdown: {e}")
            raise
    
    @staticmethod
    async def export_all_conversations(format: str = 'json'):
        """Export all conversations"""
        try:
            conversations = await conversation_service.get_all_conversations()
            
            if format == 'json':
                export_data = []
                for conv in conversations:
                    messages = await history_service.get_chat_history(conv['id'])
                    export_data.append({
                        'conversation': conv,
                        'messages': messages
                    })
                
                logger.info(f"Exported all conversations as JSON")
                return export_data
            
            elif format == 'txt' or format == 'md':
                all_exports = []
                for conv in conversations:
                    if format == 'txt':
                        export = await ExportService.export_as_text(conv['id'])
                    else:
                        export = await ExportService.export_as_markdown(conv['id'])
                    all_exports.append(export)
                
                separator = "\n\n" + ("=" * 80) + "\n\n"
                result = separator.join(all_exports)
                
                logger.info(f"Exported all conversations as {format}")
                return result
            
            else:
                raise ValueError(f"Unsupported format: {format}")
        
        except Exception as e:
            logger.error(f"Error exporting all conversations: {e}")
            raise


# Export instance
export_service = ExportService()
