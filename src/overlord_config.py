"""
Configuration settings for Overlord application.
This file contains configurable parameters for monitoring, timeouts, and debugging.

Version: 1.0.0
Compatible with: Overlord 2.0+
"""

# Configuration version for compatibility checking
CONFIG_VERSION = "1.0.0"
MIN_OVERLORD_VERSION = "2.0.0"

# ============================================================================
# WATCHDOG MONITORING CONFIGURATION
# ============================================================================

# Watchdog monitoring settings
WATCHDOG_CONFIG = {
    # How often to check for application hangs (seconds)
    "check_interval": 30,
    
    # How long without activity before considering hung (seconds)
    # 5 minutes = 300 seconds is a good default for render operations
    "hang_timeout": 300,
    
    # Enable/disable watchdog monitoring entirely
    "enabled": True,
    
    # How often the GUI updates activity (milliseconds)
    "gui_activity_interval": 60000,  # 1 minute
    
    # Enable verbose watchdog logging (more frequent status reports)
    "verbose_logging": False,
    
    # How often to log health status when verbose logging is enabled (checks)
    "health_status_interval": 10,  # Every 10 checks (5 minutes by default)
}

# Critical operation timeout settings (seconds)
CRITICAL_OPERATION_TIMEOUTS = {
    # File operations
    "file_stability_wait": 120,      # Maximum time to wait for file stability
    "exr_validation": 60,            # EXR file validation timeout
    "directory_scan": 180,           # Directory scanning timeout
    "image_display": 30,             # Image display/processing timeout
    
    # Render operations  
    "render_startup": 300,           # Render startup timeout (5 minutes)
    "render_shutdown": 180,          # Render shutdown timeout (3 minutes)
    "cleanup_all": 120,              # Application cleanup timeout
    
    # EXR conversion
    "exr_conversion": 180,           # Individual EXR conversion timeout (3 minutes)
    
    # Process operations
    "process_termination": 60,       # Process termination timeout
}

# ============================================================================
# ENHANCED LOGGING CONFIGURATION
# ============================================================================

LOGGING_CONFIG = {
    # Enable additional debug logging for hang detection
    "debug_hangs": True,
    
    # Log all critical operations start/end
    "log_critical_operations": True,
    
    # Log periodic activity updates
    "log_activity_updates": False,
    
    # Log thread health monitoring
    "log_thread_health": True,
    
    # Log resource usage warnings
    "log_resource_warnings": True,
    
    # Maximum size for individual log entries (characters)
    "max_log_entry_size": 10000,
    
    # Log file rotation settings
    "log_rotation": {
        "max_size_mb": 100,
        "backup_count": 3,
    }
}

# ============================================================================
# PERFORMANCE MONITORING
# ============================================================================

PERFORMANCE_CONFIG = {
    # Enable performance monitoring
    "enabled": True,
    
    # Track operation timing
    "track_operation_timing": True,
    
    # Warn if operations take longer than these thresholds (seconds)
    "timing_warnings": {
        "file_operations": 30,
        "image_processing": 60,
        "directory_scanning": 120,
        "exr_conversion": 180,
    },
    
    # Memory usage monitoring
    "memory_monitoring": {
        "enabled": True,
        "warning_threshold_mb": 1000,  # Warn if memory usage exceeds 1GB
        "check_interval": 60,  # Check every minute
    },
    
    # Thread monitoring
    "thread_monitoring": {
        "enabled": True,
        "max_threads_warning": 50,  # Warn if thread count exceeds this
        "check_interval": 30,  # Check every 30 seconds
    }
}

# ============================================================================
# CRASH DETECTION AND RECOVERY
# ============================================================================

CRASH_CONFIG = {
    # Automatic crash report generation
    "auto_crash_reports": True,
    
    # Save crash reports to separate files
    "save_crash_reports": True,
    
    # Include full stack traces in crash reports
    "include_stack_traces": True,
    
    # Include system information in crash reports
    "include_system_info": True,
    
    # Crash report retention (days)
    "crash_report_retention_days": 30,
    
    # Force exit methods to try (in order)
    "exit_methods": [
        "logging_shutdown",  # Try to flush logs first
        "os_exit",          # Use os._exit()
        "sys_exit",         # Use sys.exit() 
        "signal_kill",      # Use signal to kill self
    ]
}

# ============================================================================
# DEBUG UTILITIES
# ============================================================================

DEBUG_CONFIG = {
    # Enable debug mode (more verbose logging, additional checks)
    "debug_mode": False,
    
    # Create debug dumps on hang detection
    "create_debug_dumps": True,
    
    # Include environment variables in debug dumps
    "include_environment": False,
    
    # Include process list in debug dumps
    "include_process_list": True,
    
    # Test watchdog functionality on startup (for debugging)
    "test_watchdog_on_startup": False,
    
    # Simulate hangs for testing (DANGEROUS - only for development)
    "simulate_hangs": False,
}

# ============================================================================
# USER NOTIFICATION SETTINGS
# ============================================================================

NOTIFICATION_CONFIG = {
    # Show warning dialogs before forcing crashes
    "show_crash_warnings": True,
    
    # Warning dialog timeout (seconds) - auto-dismiss after this time
    "warning_timeout": 30,
    
    # Show periodic health status in UI
    "show_health_status": False,
    
    # Update status bar with monitoring info
    "update_status_bar": False,
}

def get_config_value(section: str, key: str, default=None):
    """
    Get a configuration value safely.
    
    Args:
        section: Configuration section name (e.g., 'WATCHDOG_CONFIG')
        key: Key within the section
        default: Default value if not found
        
    Returns:
        Configuration value or default
    """
    try:
        config_section = globals().get(section, {})
        return config_section.get(key, default)
    except Exception:
        return default

def update_config_value(section: str, key: str, value):
    """
    Update a configuration value at runtime.
    
    Args:
        section: Configuration section name
        key: Key within the section  
        value: New value to set
    """
    try:
        config_section = globals().get(section)
        if config_section is not None:
            config_section[key] = value
            return True
    except Exception:
        pass
    return False

def validate_config():
    """
    Validate configuration values and fix any invalid settings.
    Returns list of validation issues found.
    """
    issues = []
    
    # Validate watchdog config
    if WATCHDOG_CONFIG["check_interval"] <= 0:
        issues.append("check_interval must be positive")
        WATCHDOG_CONFIG["check_interval"] = 30
        
    if WATCHDOG_CONFIG["hang_timeout"] <= WATCHDOG_CONFIG["check_interval"]:
        issues.append("hang_timeout must be greater than check_interval")
        WATCHDOG_CONFIG["hang_timeout"] = WATCHDOG_CONFIG["check_interval"] * 2
        
    # Validate critical operation timeouts
    for op, timeout in CRITICAL_OPERATION_TIMEOUTS.items():
        if timeout <= 0:
            issues.append(f"Critical operation timeout for '{op}' must be positive")
            CRITICAL_OPERATION_TIMEOUTS[op] = 60
            
    # Validate performance config
    if PERFORMANCE_CONFIG["memory_monitoring"]["warning_threshold_mb"] <= 0:
        issues.append("Memory warning threshold must be positive")
        PERFORMANCE_CONFIG["memory_monitoring"]["warning_threshold_mb"] = 1000
        
    return issues

# Run validation on import
_validation_issues = validate_config()
if _validation_issues:
    import logging
    for issue in _validation_issues:
        logging.warning(f"Configuration validation: {issue}")
