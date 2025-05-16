#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Database management for storing and retrieving research results.
"""

import os
import json
import sqlite3
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import asdict

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False


class DatabaseManager:
    """Manages database operations for storing and retrieving research results."""
    
    def __init__(self, db_path: str, use_duckdb: bool = True):
        """Initialize the database manager.
        
        Args:
            db_path: Path to the database file
            use_duckdb: Whether to use DuckDB (if available) or SQLite
        """
        self.db_path = db_path
        self.use_duckdb = use_duckdb and DUCKDB_AVAILABLE
        
        self._init_db()
    
    def _init_db(self):
        """Initialize the database and create tables if they don't exist."""
        if self.use_duckdb:
            self.conn = duckdb.connect(self.db_path)
        else:
            self.conn = sqlite3.connect(self.db_path)
            
        # Create tables
        self._create_tables()
    
    def _create_tables(self):
        """Create necessary tables if they don't exist."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_results (
            id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            website TEXT NOT NULL,
            industry TEXT,
            fit_level TEXT NOT NULL,
            fit_score REAL NOT NULL,
            fit_explanation TEXT,
            timestamp TEXT NOT NULL,
            selling_product_id TEXT NOT NULL,
            total_time_seconds REAL NOT NULL,
            result_json TEXT NOT NULL
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS selling_products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            website TEXT NOT NULL,
            description TEXT,
            product_json TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS matched_signals (
            id TEXT PRIMARY KEY,
            research_id TEXT NOT NULL,
            signal_name TEXT NOT NULL,
            importance INTEGER NOT NULL,
            evidence TEXT,
            FOREIGN KEY (research_id) REFERENCES research_results (id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_steps (
            id TEXT PRIMARY KEY,
            research_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_seconds REAL NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (research_id) REFERENCES research_results (id)
        )
        """)
        
        self.conn.commit()
    
    def save_selling_product(self, product: 'SellingProduct') -> str:
        """Save selling product to database and return its ID."""
        from .data_models import SellingProduct  # Avoid circular import
        
        # Generate ID if not present
        product_id = str(uuid.uuid4())
        
        # Serialize product
        product_json = json.dumps(asdict(product))
        
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO selling_products (id, name, website, description, product_json, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            product.name,
            product.website,
            product.description,
            product_json,
            datetime.now().isoformat()
        ))
        
        self.conn.commit()
        return product_id
    
    def save_research_result(self, result: 'ProspectingResult', selling_product_id: str) -> str:
        """Save research result to database and return its ID."""
        from .data_models import ProspectingResult, Enum, MatchedSignal  # Avoid circular import
        
        # Generate ID if not present
        result_id = str(uuid.uuid4())
        
        # Serialize result
        result_json = json.dumps(result.to_dict())
        
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO research_results (
            id, company_name, website, industry, fit_level, fit_score, 
            fit_explanation, timestamp, selling_product_id, total_time_seconds, result_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result_id,
            result.target.company_name,
            result.target.website,
            result.target.industry,
            result.fit_level.value if isinstance(result.fit_level, Enum) else result.fit_level,
            result.fit_score,
            result.fit_explanation,
            datetime.now().isoformat(),
            selling_product_id,
            result.total_time_seconds,
            result_json
        ))
        
        # Save matched signals for easier querying
        for signal in result.matched_signals:
            signal_id = str(uuid.uuid4())
            cursor.execute("""
            INSERT INTO matched_signals (id, research_id, signal_name, importance, evidence)
            VALUES (?, ?, ?, ?, ?)
            """, (
                signal_id,
                result_id,
                signal.name,
                signal.importance,
                signal.evidence
            ))
        
        # Save step results
        for step_id, step_result in result.steps.items():
            step_record_id = str(uuid.uuid4())
            # Estimate step duration (not perfect but useful for analysis)
            step_duration = -1  # Default if can't be determined
            
            cursor.execute("""
            INSERT INTO research_steps (id, research_id, step_id, status, duration_seconds, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                step_record_id,
                result_id,
                step_id,
                step_result.status.value if isinstance(step_result.status, Enum) else step_result.status,
                step_duration,
                step_result.timestamp
            ))
        
        self.conn.commit()
        return result_id
    
    def get_research_results(self, company_name: str = None, selling_product_id: str = None, 
                            min_fit_score: float = None, has_signal: str = None,
                            limit: int = None, offset: int = 0, sort_by: str = "fit_score",
                            sort_order: str = "DESC") -> tuple[List[Dict], int]:
        """Query research results with optional filters.
        
        Args:
            company_name: Filter by company name (partial match)
            selling_product_id: Filter by selling product ID
            min_fit_score: Filter by minimum fit score
            has_signal: Filter by signal name (partial match)
            limit: Maximum number of results to return
            offset: Number of results to skip
            sort_by: Field to sort by (fit_score, company_name, timestamp)
            sort_order: Sort order (ASC or DESC)
            
        Returns:
            Tuple of (results, total_count)
        """
        # Validate sort parameters
        sort_by = sort_by.lower() if sort_by else "fit_score"
        if sort_by not in ["fit_score", "company_name", "timestamp", "total_time_seconds"]:
            sort_by = "fit_score"
            
        sort_order = sort_order.upper() if sort_order else "DESC"
        if sort_order not in ["ASC", "DESC"]:
            sort_order = "DESC"
        
        # Build query for counting total results
        count_query = "SELECT COUNT(DISTINCT research_results.id) FROM research_results"
        
        # Build main query
        query = """
        SELECT id, company_name, website, industry, fit_level, fit_score, 
               timestamp, total_time_seconds 
        FROM research_results
        """
        params = []
        where_clauses = []
        
        if company_name:
            where_clauses.append("company_name LIKE ?")
            params.append(f"%{company_name}%")
        
        if selling_product_id:
            where_clauses.append("selling_product_id = ?")
            params.append(selling_product_id)
        
        if min_fit_score is not None:
            where_clauses.append("fit_score >= ?")
            params.append(min_fit_score)
        
        if has_signal:
            query = query.replace(
                "SELECT id", 
                "SELECT DISTINCT research_results.id"
            )
            count_query += " INNER JOIN matched_signals ON research_results.id = matched_signals.research_id"
            query += " INNER JOIN matched_signals ON research_results.id = matched_signals.research_id"
            where_clauses.append("matched_signals.signal_name LIKE ?")
            params.append(f"%{has_signal}%")
        
        if where_clauses:
            where_clause = " WHERE " + " AND ".join(where_clauses)
            query += where_clause
            count_query += where_clause
        
        # Get total count
        cursor = self.conn.cursor()
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]
        
        # Add sorting
        query += f" ORDER BY {sort_by} {sort_order}"
        
        # Add pagination
        if limit is not None:
            query += f" LIMIT {limit}"
        if offset > 0:
            query += f" OFFSET {offset}"
        
        # Execute main query
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "company_name": row[1],
                "website": row[2],
                "industry": row[3],
                "fit_level": row[4],
                "fit_score": row[5],
                "timestamp": row[6],
                "total_time_seconds": row[7] if len(row) > 7 else -1
            })
        
        return results, total_count
    
    def get_research_detail(self, research_id: str) -> Dict:
        """Get full details of a research result by ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT result_json FROM research_results WHERE id = ?",
            (research_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return json.loads(row[0])
    
    def get_signals_summary(self, selling_product_id: str = None) -> Dict[str, Dict]:
        """Get summary statistics for matched signals."""
        query = """
        SELECT 
            signal_name, 
            COUNT(*) as match_count, 
            AVG(importance) as avg_importance,
            MAX(importance) as max_importance
        FROM matched_signals
        """
        
        params = []
        if selling_product_id:
            query += """
            INNER JOIN research_results ON matched_signals.research_id = research_results.id
            WHERE research_results.selling_product_id = ?
            """
            params.append(selling_product_id)
        
        query += "GROUP BY signal_name ORDER BY match_count DESC, avg_importance DESC"
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        signals = {}
        for row in rows:
            signals[row[0]] = {
                "match_count": row[1],
                "avg_importance": row[2],
                "max_importance": row[3]
            }
        
        return signals
    
    def get_performance_summary(self, selling_product_id: str = None) -> Dict[str, Any]:
        """Get performance statistics about research."""
        query = """
        SELECT 
            COUNT(*) as total_results,
            AVG(total_time_seconds) as avg_time,
            MIN(total_time_seconds) as min_time,
            MAX(total_time_seconds) as max_time,
            SUM(total_time_seconds) as total_time
        FROM research_results
        """
        
        params = []
        if selling_product_id:
            query += " WHERE selling_product_id = ?"
            params.append(selling_product_id)
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        if not row:
            return {
                "total_results": 0,
                "avg_time_seconds": 0,
                "min_time_seconds": 0,
                "max_time_seconds": 0,
                "total_time_seconds": 0
            }
        
        return {
            "total_results": row[0],
            "avg_time_seconds": row[1],
            "min_time_seconds": row[2],
            "max_time_seconds": row[3],
            "total_time_seconds": row[4]
        }

    def close(self):
        if self.conn:
            self.conn.close()