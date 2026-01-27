from typing import List, Dict, Optional
from config.database import db
from config.logger import logger
import uuid
import json

class ProjectService:
    
    async def create_project(self, user_id: str, name: str, description: str = None, config: Dict = None) -> Dict:
        """Create a new project"""
        if not db.pool:
            raise Exception("Database not connected")
            
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO projects (user_id, name, description, config) 
                   VALUES ($1, $2, $3, $4) 
                   RETURNING *""",
                user_id, name, description, json.dumps(config or {})
            )
            return dict(row)

    async def get_projects(self, user_id: str) -> List[Dict]:
        """Get all projects for a user"""
        if not db.pool:
            return []
            
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM projects WHERE user_id = $1 ORDER BY updated_at DESC", user_id)
            return [dict(row) for row in rows]

    async def get_project(self, project_id: str, user_id: str) -> Optional[Dict]:
        """Get a specific project"""
        if not db.pool:
            return None
            
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM projects WHERE id = $1 AND user_id = $2",
                project_id, user_id
            )
            return dict(row) if row else None
            
    async def update_project(self, project_id: str, user_id: str, updates: Dict) -> Optional[Dict]:
        """Update a project"""
        if not db.pool:
            return None
            
        # Build query dynamically
        set_clauses = []
        values = []
        param_count = 1
        
        for key, value in updates.items():
            if key in ['name', 'description', 'config']:
                set_clauses.append(f"{key} = ${param_count}")
                values.append(value)
                param_count += 1
                
        if not set_clauses:
            return await self.get_project(project_id, user_id)
            
        values.append(project_id)
        values.append(user_id)
        
        query = f"""
            UPDATE projects 
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE id = ${param_count} AND user_id = ${param_count + 1}
            RETURNING *
        """
        
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)
            return dict(row) if row else None

    async def delete_project(self, project_id: str, user_id: str) -> bool:
        """Delete a project"""
        if not db.pool:
            return False
            
        async with db.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM projects WHERE id = $1 AND user_id = $2",
                project_id, user_id
            )
            return "DELETE 0" not in result

project_service = ProjectService()
