# Overlord Hang Detection and Monitoring System

This document describes the enhanced monitoring system added to Overlord to detect and handle application hangs.

## Problem

Overlord was experiencing hangs that would cause the application to become unresponsive for hours without generating error messages or logs. The application would appear frozen but not crash, making it difficult to diagnose the issue.

## Solution

A comprehensive watchdog monitoring system has been implemented that:

1. **Detects Application Hangs**: Monitors application activity and detects when the application becomes unresponsive
2. **Forces Crash on Hang**: When a hang is detected, the application is forced to crash with a detailed crash report
3. **Provides Diagnostic Information**: Generates comprehensive crash reports with stack traces, thread information, and system state
4. **Monitors Critical Operations**: Tracks long-running operations and detects when they exceed expected timeouts

## Deployment

### Production Distribution
These monitoring files are **included in the production build** and will be available when users install Overlord:

- `watchdog_monitor.py` - Core monitoring system (bundled in executable)
- `overlord_config.py` - Configuration settings (bundled in executable)

The monitoring system runs automatically in both development and production environments.

### Development and Testing
Additional files for development and testing:

- `test_watchdog.py` - Test suite for validating monitoring (development only)
- `MONITORING_README.md` - This documentation (development only)

## New Files Added

### `watchdog_monitor.py`
Core monitoring system that:
- Runs a background thread that periodically checks application health
- Tracks activity from various application components
- Monitors critical operations and their durations
- Generates detailed crash reports when hangs are detected
- Forces application exit when hangs are detected

### `overlord_config.py` 
Configuration file that allows customization of:
- Watchdog timing settings (check intervals, hang timeouts)
- Critical operation timeouts
- Logging levels and options
- Performance monitoring thresholds
- Debug and testing options

### `test_watchdog.py`
Test suite for validating the monitoring system:
- Tests normal operation monitoring
- Tests critical operation tracking
- Tests thread monitoring
- Tests hang simulation (for debugging)
- Validates configuration settings

## How It Works

### Activity Monitoring
The system tracks "activity" from various parts of the application:
- GUI event loop updates every minute
- File processing operations
- Image display updates
- EXR conversion operations
- Render startup/shutdown operations

### Critical Operation Tracking
Long-running operations are wrapped with `start_critical_operation()` and `end_critical_operation()` calls:
- File stability waits
- EXR validation and conversion
- Directory scanning
- Image processing
- Render startup/shutdown

### Hang Detection
If no activity is reported for longer than the configured timeout (default 5 minutes), the watchdog:
1. Logs a critical error with full diagnostic information
2. Generates a detailed crash report saved to disk
3. Forces the application to exit immediately

### Crash Reports
When a hang is detected, a comprehensive crash report is generated including:
- Thread information and stack traces
- Component health status
- Critical operations in progress
- System resource usage
- Timing statistics

## Configuration

### Key Settings (in `overlord_config.py`)

```python
WATCHDOG_CONFIG = {
    "check_interval": 30,    # Check for hangs every 30 seconds
    "hang_timeout": 300,     # Consider hung after 5 minutes of inactivity
    "enabled": True,         # Enable/disable watchdog monitoring
}
```

### Critical Operation Timeouts
Individual timeouts for different operation types:
- File operations: 30-180 seconds
- Render operations: 180-300 seconds  
- EXR conversion: 180 seconds
- Directory scanning: 180 seconds

## Usage

### Normal Operation
The monitoring system runs automatically when Overlord starts. No user interaction is required.

### Testing
Run the test suite to validate monitoring:
```bash
python test_watchdog.py
```

### Debugging Hangs
When a hang occurs:
1. Check the main log file for critical error messages
2. Look for crash report files in the Overlord data directory
3. Review the crash report for:
   - Which operations were in progress when the hang occurred
   - Stack traces showing where threads were blocked
   - Component health information

### Adjusting Settings
Edit `overlord_config.py` to:
- Increase/decrease hang timeout if getting false positives
- Enable more verbose logging for debugging
- Adjust critical operation timeouts
- Enable debug features for development

## Log Files and Crash Reports

### Main Log File
Location: `%APPDATA%/Overlord/log.txt`
Contains regular application logs plus monitoring information.

### Crash Reports  
Location: `%APPDATA%/Overlord/crash_report_YYYYMMDD_HHMMSS.txt`
Generated when hangs are detected, contains detailed diagnostic information.

## Troubleshooting

### False Positive Hangs
If the system incorrectly detects hangs during normal operation:
1. Check if the hang timeout is too short for your system
2. Increase `hang_timeout` in `overlord_config.py`
3. Enable verbose logging to see activity patterns

### Monitoring Not Working
If hangs still occur without detection:
1. Verify `WATCHDOG_CONFIG["enabled"]` is True
2. Check that activity updates are being called in the problematic code areas
3. Review the test suite results for monitoring functionality

### Performance Impact
The monitoring system is designed to be lightweight:
- Background thread checks every 30 seconds by default
- Activity updates are simple timestamp updates
- Minimal CPU and memory overhead

## Development Notes

### Adding Monitoring to New Code
When adding new long-running operations:

```python
# For operations that should complete quickly
start_critical_operation("operation_name")
try:
    # ... your operation ...
    update_activity("operation_progress")  # Optional progress updates
finally:
    end_critical_operation("operation_name")

# For regular activity updates
update_activity("component_name")
```

### Testing Hang Detection
Enable hang simulation in `overlord_config.py`:
```python
DEBUG_CONFIG = {
    "simulate_hangs": True,  # DANGEROUS - only for development
}
```

Then run `test_watchdog.py` which will include hang simulation tests.

## Future Enhancements

Potential improvements to consider:
1. **GUI Integration**: Show monitoring status in the UI
2. **Automatic Recovery**: Attempt to recover from certain types of hangs
3. **Performance Metrics**: Track and display operation timing statistics
4. **Remote Monitoring**: Send hang notifications to external monitoring systems
5. **Predictive Detection**: Detect early warning signs before complete hangs occur

## Support

If you encounter issues with the monitoring system:
1. Check the configuration in `overlord_config.py`
2. Run the test suite with `python test_watchdog.py`
3. Review crash reports for diagnostic information
4. Enable debug logging for more detailed information
5. Disable monitoring temporarily if needed by setting `WATCHDOG_CONFIG["enabled"] = False`
