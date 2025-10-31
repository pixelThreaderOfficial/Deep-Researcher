import sqlite3
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
import os
from pathlib import Path

# Define types for chat settings
DocumentAnalysisMode = Literal["off", "auto"]

class ChatSQLiteCRUD:
    def __init__(self, db_path: str = "database/chat_history.db"):
        """Initialize the SQLite CRUD operations for chat history"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def _create_tables(self):
        """Create the chat_history table if it doesn't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS chat_history (
                    sno INTEGER PRIMARY KEY AUTOINCREMENT,
                    chatid TEXT NOT NULL UNIQUE,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    model TEXT NOT NULL,
                    thinking BOOLEAN DEFAULT FALSE,
                    generation_time REAL,  -- in seconds
                    tokens_used INTEGER,
                    datetime_generated TEXT NOT NULL,
                    metadata TEXT,  -- JSON string containing additional metadata
                    created_at REAL,  -- timestamp
                    updated_at REAL   -- timestamp
                )
            ''')

            # Create indexes for better query performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_chatid ON chat_history(chatid)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_datetime ON chat_history(datetime_generated)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_model ON chat_history(model)')

            # Create chat_settings table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS chat_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    system_prompt TEXT,
                    user_name TEXT,
                    model TEXT NOT NULL,
                    prompt_template_id TEXT,  -- UUID
                    top_p REAL DEFAULT 0.9,
                    top_k REAL DEFAULT 0.9,
                    document_analysis_mode TEXT CHECK(document_analysis_mode IN ('off', 'auto')) DEFAULT 'off',
                    enable_thinking BOOLEAN DEFAULT FALSE,
                    max_previous_memory_retention INTEGER CHECK(max_previous_memory_retention >= 1 AND max_previous_memory_retention <= 10) DEFAULT 5,
                    chat_id TEXT,  -- UUID, can be NULL for global settings
                    is_global BOOLEAN DEFAULT FALSE,
                    created_at REAL,  -- timestamp
                    updated_at REAL   -- timestamp
                )
            ''')

            # Create indexes for chat_settings
            conn.execute('CREATE INDEX IF NOT EXISTS idx_settings_chat_id ON chat_settings(chat_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_settings_global ON chat_settings(is_global)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_settings_template ON chat_settings(prompt_template_id)')

            # Create chat_sessions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    title TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    metadata TEXT
                )
            ''')

            # Create indexes for chat_sessions
            conn.execute('CREATE INDEX IF NOT EXISTS idx_session_id ON chat_sessions(session_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON chat_sessions(updated_at)')

            # Add session_id column to chat_history if it doesn't exist (migration)
            try:
                conn.execute('ALTER TABLE chat_history ADD COLUMN session_id TEXT')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_chat_history_session_id ON chat_history(session_id)')
            except sqlite3.OperationalError:
                # Column already exists, just ensure index exists
                conn.execute('CREATE INDEX IF NOT EXISTS idx_chat_history_session_id ON chat_history(session_id)')

    def create_chat_entry(self, prompt: str, response: str, model: str,
                         thinking: bool = False, generation_time: Optional[float] = None,
                         tokens_used: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None,
                         session_id: Optional[str] = None) -> str:
        """
        Create a new chat entry and return the chatid

        Args:
            prompt: The user prompt
            response: The AI response
            model: The model used
            thinking: Whether thinking mode was enabled
            generation_time: Time taken to generate response (seconds)
            tokens_used: Number of tokens used
            metadata: Additional metadata as dictionary
            session_id: Optional session ID to group this chat entry

        Returns:
            chatid: The UUID of the created chat entry
        """
        chatid = str(uuid.uuid4())
        now = datetime.now()
        timestamp = now.timestamp()

        metadata_json = json.dumps(metadata) if metadata else None

        with sqlite3.connect(self.db_path) as conn:
            # Check if session_id column exists (for backward compatibility)
            cursor = conn.execute('PRAGMA table_info(chat_history)')
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'session_id' in columns:
                conn.execute('''
                    INSERT INTO chat_history (
                        chatid, prompt, response, model, thinking,
                        generation_time, tokens_used, datetime_generated,
                        metadata, created_at, updated_at, session_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    chatid, prompt, response, model, thinking,
                    generation_time, tokens_used, now.isoformat(),
                    metadata_json, timestamp, timestamp, session_id
                ))
            else:
                conn.execute('''
                    INSERT INTO chat_history (
                        chatid, prompt, response, model, thinking,
                        generation_time, tokens_used, datetime_generated,
                        metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    chatid, prompt, response, model, thinking,
                    generation_time, tokens_used, now.isoformat(),
                    metadata_json, timestamp, timestamp
                ))

        return chatid

    def get_chat_by_id(self, chatid: str) -> Optional[Dict[str, Any]]:
        """Get a chat entry by its chatid"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM chat_history WHERE chatid = ?', (chatid,))
            row = cursor.fetchone()

            if row:
                result = dict(row)
                # Parse metadata JSON
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                return result
            return None

    def get_all_chats(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all chat entries with pagination"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM chat_history
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                results.append(result)

            return results

    def get_chats_by_model(self, model: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chat entries by model"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM chat_history
                WHERE model = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (model, limit))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                results.append(result)

            return results

    def get_chats_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get chat entries within a date range (ISO format: YYYY-MM-DDTHH:MM:SS)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM chat_history
                WHERE datetime_generated BETWEEN ? AND ?
                ORDER BY datetime_generated DESC
            ''', (start_date, end_date))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                results.append(result)

            return results

    def update_chat_response(self, chatid: str, new_response: str,
                           tokens_used: Optional[int] = None,
                           generation_time: Optional[float] = None) -> bool:
        """Update an existing chat entry's response and related fields"""
        update_fields = ['response = ?', 'updated_at = ?']
        params = [new_response, datetime.now().timestamp()]

        if tokens_used is not None:
            update_fields.append('tokens_used = ?')
            params.append(tokens_used)

        if generation_time is not None:
            update_fields.append('generation_time = ?')
            params.append(generation_time)

        params.append(chatid)  # WHERE clause

        query = f'''
            UPDATE chat_history
            SET {', '.join(update_fields)}
            WHERE chatid = ?
        '''

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount > 0

    def delete_chat(self, chatid: str) -> bool:
        """Delete a chat entry by chatid"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('DELETE FROM chat_history WHERE chatid = ?', (chatid,))
            return cursor.rowcount > 0

    def get_chat_stats(self) -> Dict[str, Any]:
        """Get statistics about the chat history"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total_chats,
                    COUNT(DISTINCT model) as unique_models,
                    AVG(generation_time) as avg_generation_time,
                    SUM(tokens_used) as total_tokens,
                    MIN(datetime_generated) as first_chat,
                    MAX(datetime_generated) as last_chat
                FROM chat_history
            ''')

            row = cursor.fetchone()
            return {
                'total_chats': row[0],
                'unique_models': row[1],
                'avg_generation_time': row[2],
                'total_tokens': row[3],
                'first_chat': row[4],
                'last_chat': row[5]
            }

    def search_chats(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search chats by prompt or response content"""
        search_pattern = f'%{query}%'

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM chat_history
                WHERE prompt LIKE ? OR response LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (search_pattern, search_pattern, limit))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                results.append(result)

            return results

    # ==================== CHAT SETTINGS CRUD METHODS ====================

    def create_chat_settings(self, model: str, system_prompt: Optional[str] = None,
                           user_name: Optional[str] = None,
                           prompt_template_id: Optional[str] = None,
                           top_p: float = 0.9, top_k: float = 0.9,
                           document_analysis_mode: DocumentAnalysisMode = "off",
                           enable_thinking: bool = False,
                           max_previous_memory_retention: int = 5,
                           chat_id: Optional[str] = None,
                           is_global: bool = False) -> int:
        """
        Create new chat settings

        Args:
            model: The AI model to use
            system_prompt: System prompt text
            user_name: User name for personalization
            prompt_template_id: UUID of prompt template
            top_p: Top-p sampling parameter (0.0-1.0)
            top_k: Top-k sampling parameter (0.0-1.0)
            document_analysis_mode: 'off' or 'auto'
            enable_thinking: Enable thinking mode
            max_previous_memory_retention: Memory retention (1-10)
            chat_id: UUID of specific chat (None for global)
            is_global: Whether these are global settings

        Returns:
            settings_id: The ID of the created settings entry
        """
        timestamp = datetime.now().timestamp()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO chat_settings (
                    system_prompt, user_name, model, prompt_template_id,
                    top_p, top_k, document_analysis_mode, enable_thinking,
                    max_previous_memory_retention, chat_id, is_global,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                system_prompt, user_name, model, prompt_template_id,
                top_p, top_k, document_analysis_mode, enable_thinking,
                max_previous_memory_retention, chat_id, is_global,
                timestamp, timestamp
            ))
            return cursor.lastrowid

    def get_chat_settings(self, chat_id: Optional[str] = None,
                         is_global: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get chat settings by chat_id or global settings

        Args:
            chat_id: Specific chat UUID (if None, gets global settings)
            is_global: If True and chat_id is None, gets global settings

        Returns:
            Settings dictionary or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if chat_id:
                cursor = conn.execute('SELECT * FROM chat_settings WHERE chat_id = ?', (chat_id,))
            elif is_global:
                cursor = conn.execute('SELECT * FROM chat_settings WHERE is_global = TRUE ORDER BY updated_at DESC LIMIT 1')
            else:
                return None

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_chat_settings(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all chat settings with pagination"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM chat_settings
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))

            return [dict(row) for row in cursor.fetchall()]

    def update_chat_settings(self, settings_id: int,
                           system_prompt: Optional[str] = None,
                           user_name: Optional[str] = None,
                           model: Optional[str] = None,
                           prompt_template_id: Optional[str] = None,
                           top_p: Optional[float] = None,
                           top_k: Optional[float] = None,
                           document_analysis_mode: Optional[DocumentAnalysisMode] = None,
                           enable_thinking: Optional[bool] = None,
                           max_previous_memory_retention: Optional[int] = None,
                           chat_id: Optional[str] = None,
                           is_global: Optional[bool] = None) -> bool:
        """Update chat settings by ID"""
        update_fields = ['updated_at = ?']
        params = [datetime.now().timestamp()]

        # Add fields that are not None
        field_mapping = {
            'system_prompt': system_prompt,
            'user_name': user_name,
            'model': model,
            'prompt_template_id': prompt_template_id,
            'top_p': top_p,
            'top_k': top_k,
            'document_analysis_mode': document_analysis_mode,
            'enable_thinking': enable_thinking,
            'max_previous_memory_retention': max_previous_memory_retention,
            'chat_id': chat_id,
            'is_global': is_global
        }

        for field, value in field_mapping.items():
            if value is not None:
                update_fields.append(f'{field} = ?')
                params.append(value)

        params.append(settings_id)  # WHERE clause

        query = f'''
            UPDATE chat_settings
            SET {', '.join(update_fields)}
            WHERE id = ?
        '''

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount > 0

    def update_chat_settings_by_chat_id(self, chat_id: str,
                                      system_prompt: Optional[str] = None,
                                      user_name: Optional[str] = None,
                                      model: Optional[str] = None,
                                      prompt_template_id: Optional[str] = None,
                                      top_p: Optional[float] = None,
                                      top_k: Optional[float] = None,
                                      document_analysis_mode: Optional[DocumentAnalysisMode] = None,
                                      enable_thinking: Optional[bool] = None,
                                      max_previous_memory_retention: Optional[int] = None,
                                      is_global: Optional[bool] = None) -> bool:
        """Update chat settings by chat_id"""
        update_fields = ['updated_at = ?']
        params = [datetime.now().timestamp()]

        # Add fields that are not None
        field_mapping = {
            'system_prompt': system_prompt,
            'user_name': user_name,
            'model': model,
            'prompt_template_id': prompt_template_id,
            'top_p': top_p,
            'top_k': top_k,
            'document_analysis_mode': document_analysis_mode,
            'enable_thinking': enable_thinking,
            'max_previous_memory_retention': max_previous_memory_retention,
            'is_global': is_global
        }

        for field, value in field_mapping.items():
            if value is not None:
                update_fields.append(f'{field} = ?')
                params.append(value)

        params.append(chat_id)  # WHERE clause

        query = f'''
            UPDATE chat_settings
            SET {', '.join(update_fields)}
            WHERE chat_id = ?
        '''

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount > 0

    def delete_chat_settings(self, settings_id: int) -> bool:
        """Delete chat settings by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('DELETE FROM chat_settings WHERE id = ?', (settings_id,))
            return cursor.rowcount > 0

    def delete_chat_settings_by_chat_id(self, chat_id: str) -> bool:
        """Delete chat settings by chat_id"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('DELETE FROM chat_settings WHERE chat_id = ?', (chat_id,))
            return cursor.rowcount > 0

    def get_global_settings(self) -> Optional[Dict[str, Any]]:
        """Get global chat settings"""
        return self.get_chat_settings(chat_id=None, is_global=True)

    def create_or_update_global_settings(self, model: str,
                                       system_prompt: Optional[str] = None,
                                       user_name: Optional[str] = None,
                                       prompt_template_id: Optional[str] = None,
                                       top_p: float = 0.9,
                                       top_k: float = 0.9,
                                       document_analysis_mode: DocumentAnalysisMode = "off",
                                       enable_thinking: bool = False,
                                       max_previous_memory_retention: int = 5) -> int:
        """Create or update global settings"""
        existing = self.get_global_settings()

        if existing:
            # Update existing
            self.update_chat_settings(
                settings_id=existing['id'],
                system_prompt=system_prompt,
                user_name=user_name,
                model=model,
                prompt_template_id=prompt_template_id,
                top_p=top_p,
                top_k=top_k,
                document_analysis_mode=document_analysis_mode,
                enable_thinking=enable_thinking,
                max_previous_memory_retention=max_previous_memory_retention
            )
            return existing['id']
        else:
            # Create new
            return self.create_chat_settings(
                model=model,
                system_prompt=system_prompt,
                user_name=user_name,
                prompt_template_id=prompt_template_id,
                top_p=top_p,
                top_k=top_k,
                document_analysis_mode=document_analysis_mode,
                enable_thinking=enable_thinking,
                max_previous_memory_retention=max_previous_memory_retention,
                chat_id=None,
                is_global=True
            )

    # ==================== CHAT SESSION CRUD METHODS ====================

    def create_chat_session(self, title: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new chat session
        
        Args:
            title: Optional title for the session
            metadata: Optional metadata dictionary
            
        Returns:
            session_id: The UUID of the created session
        """
        session_id = str(uuid.uuid4())
        timestamp = datetime.now().timestamp()
        metadata_json = json.dumps(metadata) if metadata else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO chat_sessions (
                    session_id, title, created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?)
            ''', (session_id, title, timestamp, timestamp, metadata_json))

        return session_id

    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by its session_id"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM chat_sessions WHERE session_id = ?', (session_id,))
            row = cursor.fetchone()

            if row:
                result = dict(row)
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                return result
            return None

    def get_all_sessions(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all chat sessions with pagination"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM chat_sessions
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                results.append(result)

            return results

    def update_session_title(self, session_id: str, title: str) -> bool:
        """Update the title of a session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE chat_sessions
                SET title = ?, updated_at = ?
                WHERE session_id = ?
            ''', (title, datetime.now().timestamp(), session_id))
            return cursor.rowcount > 0

    def update_session_updated_at(self, session_id: str) -> bool:
        """Update the updated_at timestamp of a session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE chat_sessions
                SET updated_at = ?
                WHERE session_id = ?
            ''', (datetime.now().timestamp(), session_id))
            return cursor.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its associated chat entries"""
        with sqlite3.connect(self.db_path) as conn:
            # Delete all chat entries for this session
            conn.execute('DELETE FROM chat_history WHERE session_id = ?', (session_id,))
            # Delete the session
            cursor = conn.execute('DELETE FROM chat_sessions WHERE session_id = ?', (session_id,))
            return cursor.rowcount > 0

    def get_session_messages(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all messages in a session"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM chat_history
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            ''', (session_id, limit))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                results.append(result)

            return results

    def get_session_context(self, session_id: str, max_chars: int = 1000, max_messages: int = 10) -> List[Dict[str, Any]]:
        """Get last N messages for context (up to max_chars)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM chat_history
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (session_id, max_messages))

            results = []
            total_chars = 0
            
            for row in cursor.fetchall():
                result = dict(row)
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                
                # Calculate message length
                prompt_len = len(result.get('prompt', ''))
                response_len = len(result.get('response', ''))
                message_len = prompt_len + response_len
                
                if total_chars + message_len > max_chars:
                    break
                
                results.append(result)
                total_chars += message_len

            # Reverse to get chronological order
            return list(reversed(results))

    def get_chats_by_session_id(self, session_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get chat entries by session_id with pagination"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM chat_history
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ? OFFSET ?
            ''', (session_id, limit, offset))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result['metadata']:
                    result['metadata'] = json.loads(result['metadata'])
                results.append(result)

            return results

    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total_messages,
                    COUNT(DISTINCT model) as unique_models,
                    AVG(generation_time) as avg_generation_time,
                    SUM(tokens_used) as total_tokens,
                    MIN(datetime_generated) as first_message,
                    MAX(datetime_generated) as last_message
                FROM chat_history
                WHERE session_id = ?
            ''', (session_id,))

            row = cursor.fetchone()
            return {
                'total_messages': row[0] or 0,
                'unique_models': row[1] or 0,
                'avg_generation_time': row[2],
                'total_tokens': row[3] or 0,
                'first_message': row[4],
                'last_message': row[5]
            }

# Global instance for easy access
chat_db = ChatSQLiteCRUD()
