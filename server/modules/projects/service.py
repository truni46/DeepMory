from typing import List, Dict, Optional
from config.database import db
from config.logger import logger
import uuid
import json

class ProjectService:
    
    async def create_project(self, userId: str, name: str, description: str = None, config: Dict = None) -> Dict:
        """Create a new project"""
        if not db.pool:
            raise Exception("Database not connected")
            
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO projects ("userId", name, description, config) 
                   VALUES ($1, $2, $3, $4) 
                   RETURNING *""",
                userId, name, description, json.dumps(config or {})
            )
            return dict(row)

    async def get_projects(self, userId: str) -> List[Dict]:
        """Get all projects for a user"""
        if not db.pool:
            return []
            
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM projects WHERE "userId" = $1 ORDER BY "updatedAt" DESC""",
                userId
            )
            return [dict(row) for row in rows]

    async def get_project(self, projectId: str, userId: str) -> Optional[Dict]:
        """Get a specific project"""
        if not db.pool:
            return None
            
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT * FROM projects WHERE id = $1 AND "userId" = $2""",
                projectId, userId
            )
            return dict(row) if row else None
            
    async def update_project(self, projectId: str, userId: str, updates: Dict) -> Optional[Dict]:
        """Update a project"""
        if not db.pool:
            return None
            
        setClauses = []
        values = []
        paramCount = 1
        
        for key, value in updates.items():
            if key in ['name', 'description', 'config']:
                setClauses.append(f'"{key}" = ${paramCount}')
                values.append(value)
                paramCount += 1
                
        if not setClauses:
            return await self.get_project(projectId, userId)
            
        values.append(projectId)
        values.append(userId)
        
        query = f"""
            UPDATE projects 
            SET {', '.join(setClauses)}, "updatedAt" = NOW()
            WHERE id = ${paramCount} AND "userId" = ${paramCount + 1}
            RETURNING *
        """
        
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)
            return dict(row) if row else None

    async def delete_project(self, projectId: str, userId: str) -> bool:
        """Delete a project"""
        if not db.pool:
            return False
            
        async with db.pool.acquire() as conn:
            result = await conn.execute(
                """DELETE FROM projects WHERE id = $1 AND "userId" = $2""",
                projectId, userId
            )
            return "DELETE 0" not in result

projectService = ProjectService()
