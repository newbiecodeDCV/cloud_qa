"""
LangSmith Integration for Call Center QA Project
File: api/langsmith_integration.py
"""

import os
import asyncio
from functools import wraps
from typing import Dict, Any
from datetime import datetime
import logging

from langsmith import Client, traceable
from langsmith.run_helpers import get_current_run_tree
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Khởi tạo LangSmith client
LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

if LANGSMITH_ENABLED:
    langsmith_client = Client(
        api_key=os.getenv("LANGCHAIN_API_KEY"),
        api_url=os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    )
    logger.info("✓ LangSmith tracking enabled")
else:
    langsmith_client = None
    logger.info("LangSmith tracking disabled")


def log_feedback(key: str, score: float, comment: str = ""):
    """Log feedback vào LangSmith"""
    if not LANGSMITH_ENABLED or not langsmith_client:
        return
    
    try:
        run_tree = get_current_run_tree()
        if run_tree:
            langsmith_client.create_feedback(
                run_id=run_tree.id,
                key=key,
                score=score,
                comment=comment
            )
    except Exception as e:
        logger.warning(f"Failed to log feedback: {e}")


def add_metadata(metadata: Dict[str, Any]):
    """Thêm metadata vào current run"""
    if not LANGSMITH_ENABLED:
        return
    
    try:
        run_tree = get_current_run_tree()
        if run_tree:
            if not hasattr(run_tree, 'extra') or run_tree.extra is None:
                run_tree.extra = {}
            run_tree.extra.update(metadata)
    except Exception as e:
        logger.warning(f"Failed to add metadata: {e}")


def add_tags(*tags: str):
    """Thêm tags vào current run"""
    if not LANGSMITH_ENABLED:
        return
    
    try:
        run_tree = get_current_run_tree()
        if run_tree:
            if not hasattr(run_tree, 'tags') or run_tree.tags is None:
                run_tree.tags = []
            run_tree.tags.extend(tags)
    except Exception as e:
        logger.warning(f"Failed to add tags: {e}")


def trace_chain(name: str = None):
    """Decorator trace cho pipeline/chain operations"""
    def decorator(func):
        if not LANGSMITH_ENABLED:
            return func
        
        @wraps(func)
        @traceable(
            run_type="chain",
            name=name or func.__name__,
            project_name=os.getenv("LANGCHAIN_PROJECT", "call-center-qa")
        )
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        @wraps(func)
        @traceable(
            run_type="chain",
            name=name or func.__name__,
            project_name=os.getenv("LANGCHAIN_PROJECT", "call-center-qa")
        )
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def trace_llm(name: str = None, model: str = None):
    """Decorator trace cho LLM calls"""
    def decorator(func):
        if not LANGSMITH_ENABLED:
            return func
        
        @wraps(func)
        @traceable(
            run_type="llm",
            name=name or func.__name__,
            project_name=os.getenv("LANGCHAIN_PROJECT", "call-center-qa")
        )
        async def async_wrapper(*args, **kwargs):
            if model:
                add_metadata({"model": model})
            return await func(*args, **kwargs)
        
        @wraps(func)
        @traceable(
            run_type="llm",
            name=name or func.__name__,
            project_name=os.getenv("LANGCHAIN_PROJECT", "call-center-qa")
        )
        def sync_wrapper(*args, **kwargs):
            if model:
                add_metadata({"model": model})
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def trace_tool(name: str = None):
    """Decorator trace cho tool/utility operations"""
    def decorator(func):
        if not LANGSMITH_ENABLED:
            return func
        
        @wraps(func)
        @traceable(
            run_type="tool",
            name=name or func.__name__,
            project_name=os.getenv("LANGCHAIN_PROJECT", "call-center-qa")
        )
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        @wraps(func)
        @traceable(
            run_type="tool",
            name=name or func.__name__,
            project_name=os.getenv("LANGCHAIN_PROJECT", "call-center-qa")
        )
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


__all__ = [
    "trace_chain",
    "trace_llm", 
    "trace_tool",
    "log_feedback",
    "add_metadata",
    "add_tags",
    "LANGSMITH_ENABLED"
]