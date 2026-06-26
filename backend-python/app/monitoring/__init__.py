"""
Drawing Assistant Monitoring — performance tracking, chat logging,
task auditing, and automated improvement recommendations.
"""
from .log_db import (
    log_chat, log_task, log_decision, log_tool_usage,
    update_performance_metrics, get_performance_dashboard,
    get_recent_chats, get_recent_tasks, get_recent_tools, get_recent_decisions,
    add_recommendation, update_recommendation_status, get_open_recommendations,
)
