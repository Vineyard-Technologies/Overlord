"""
Watchdog monitor for detecting application hangs and deadlocks.
This module provides comprehensive monitoring to detect when the application
becomes unresponsive and can force a crash with detailed diagnostics.
"""

import threading
import time
import logging
import traceback
import sys
import os
import signal
import gc
from typing import Dict, List, Callable, Optional
from datetime import datetime, timedelta


class WatchdogMonitor:
    """
    Monitors application health and can force crashes when hangs are detected.
    """
    
    def __init__(self, check_interval: int = 30, hang_timeout: int = 300):
        """
        Initialize the watchdog monitor.
        
        Args:
            check_interval: How often to check for hangs (seconds)
            hang_timeout: How long without activity before considering hung (seconds)
        """
        self.check_interval = check_interval
        self.hang_timeout = hang_timeout
        self.last_activity = time.time()
        self.is_running = False
        self.monitor_thread = None
        self.activity_callbacks: List[Callable] = []
        self.component_health: Dict[str, float] = {}
        self.thread_states: Dict[str, Dict] = {}
        self.critical_operations: Dict[str, float] = {}
        
        # Statistics
        self.stats = {
            'total_checks': 0,
            'warnings_issued': 0,
            'forced_exits': 0,
            'activity_updates': 0
        }
        
    def start(self):
        """Start the watchdog monitoring."""
        if self.is_running:
            return
            
        self.is_running = True
        self.last_activity = time.time()
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="WatchdogMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        logging.info(f"Watchdog monitor started (check_interval={self.check_interval}s, hang_timeout={self.hang_timeout}s)")
        
    def stop(self):
        """Stop the watchdog monitoring."""
        self.is_running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        logging.info("Watchdog monitor stopped")
        
    def update_activity(self, component: str = "main"):
        """Update the last activity timestamp for a component."""
        current_time = time.time()
        self.last_activity = current_time
        self.component_health[component] = current_time
        self.stats['activity_updates'] += 1
        
        # Call registered activity callbacks
        for callback in self.activity_callbacks:
            try:
                callback(component, current_time)
            except Exception as e:
                logging.warning(f"Activity callback failed: {e}")
                
    def register_activity_callback(self, callback: Callable):
        """Register a callback to be called on activity updates."""
        self.activity_callbacks.append(callback)
        
    def start_critical_operation(self, operation_name: str):
        """Mark the start of a critical operation that shouldn't hang."""
        self.critical_operations[operation_name] = time.time()
        logging.debug(f"Started critical operation: {operation_name}")
        
    def end_critical_operation(self, operation_name: str):
        """Mark the end of a critical operation."""
        if operation_name in self.critical_operations:
            duration = time.time() - self.critical_operations[operation_name]
            del self.critical_operations[operation_name]
            logging.debug(f"Completed critical operation: {operation_name} (duration: {duration:.2f}s)")
            self.update_activity(f"critical_op_{operation_name}")
            
    def register_thread(self, thread_name: str, thread_obj: threading.Thread):
        """Register a thread for monitoring."""
        self.thread_states[thread_name] = {
            'thread': thread_obj,
            'last_seen': time.time(),
            'is_alive': thread_obj.is_alive()
        }
        
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.is_running:
            try:
                self._perform_health_check()
                time.sleep(self.check_interval)
            except Exception as e:
                logging.error(f"Watchdog monitor error: {e}")
                logging.error(traceback.format_exc())
                
    def _perform_health_check(self):
        """Perform a comprehensive health check."""
        current_time = time.time()
        self.stats['total_checks'] += 1
        
        # Check main activity
        time_since_activity = current_time - self.last_activity
        
        # Log periodic health status
        if self.stats['total_checks'] % 10 == 0:  # Every 10 checks (5 minutes by default)
            self._log_health_status(current_time)
            
        # Check for overall hang
        if time_since_activity > self.hang_timeout:
            self._handle_hang_detected(time_since_activity)
            return
            
        # Check critical operations
        self._check_critical_operations(current_time)
        
        # Check thread health
        self._check_thread_health(current_time)
        
        # Check component health
        self._check_component_health(current_time)
        
        # Memory and resource checks
        self._check_system_resources()
        
    def _log_health_status(self, current_time: float):
        """Log current health status."""
        active_threads = threading.active_count()
        gc_stats = gc.get_stats() if hasattr(gc, 'get_stats') else []
        
        status_info = [
            f"Health Check #{self.stats['total_checks']}",
            f"Active threads: {active_threads}",
            f"Last activity: {current_time - self.last_activity:.1f}s ago",
            f"Components monitored: {len(self.component_health)}",
            f"Critical operations: {len(self.critical_operations)}",
            f"Memory collections: {len(gc_stats)}"
        ]
        
        logging.info(" | ".join(status_info))
        
        # Log component details if verbose logging is enabled
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            for component, last_time in self.component_health.items():
                age = current_time - last_time
                logging.debug(f"Component '{component}': {age:.1f}s ago")
                
    def _handle_hang_detected(self, time_since_activity: float):
        """Handle when a hang is detected."""
        self.stats['forced_exits'] += 1
        
        # Generate comprehensive crash report
        crash_report = self._generate_crash_report(time_since_activity)
        
        # Log the crash report
        logging.critical("=" * 80)
        logging.critical("APPLICATION HANG DETECTED - FORCING CRASH")
        logging.critical("=" * 80)
        logging.critical(crash_report)
        logging.critical("=" * 80)
        
        # Try to save crash report to file
        try:
            self._save_crash_report(crash_report)
        except Exception as e:
            logging.error(f"Failed to save crash report: {e}")
            
        # Force application exit
        self._force_crash()
        
    def _generate_crash_report(self, time_since_activity: float) -> str:
        """Generate a detailed crash report."""
        current_time = time.time()
        report_lines = [
            f"CRASH REPORT - {datetime.now().isoformat()}",
            f"Application has been unresponsive for {time_since_activity:.1f} seconds",
            f"Hang timeout threshold: {self.hang_timeout} seconds",
            "",
            "=== THREAD INFORMATION ===",
        ]
        
        # Add thread information
        for thread in threading.enumerate():
            try:
                thread_info = f"Thread: {thread.name} | Alive: {thread.is_alive()} | Daemon: {thread.daemon}"
                if hasattr(thread, 'ident'):
                    thread_info += f" | ID: {thread.ident}"
                report_lines.append(thread_info)
            except Exception as e:
                report_lines.append(f"Error getting thread info: {e}")
                
        report_lines.extend([
            "",
            "=== STACK TRACES ===",
        ])
        
        # Add stack traces for all threads
        for thread_id, frame in sys._current_frames().items():
            report_lines.append(f"Thread {thread_id}:")
            stack_lines = traceback.format_stack(frame)
            report_lines.extend(f"  {line.rstrip()}" for line in stack_lines)
            report_lines.append("")
            
        report_lines.extend([
            "=== COMPONENT HEALTH ===",
        ])
        
        # Add component health information
        for component, last_time in self.component_health.items():
            age = current_time - last_time
            status = "HEALTHY" if age < self.hang_timeout else "STALE"
            report_lines.append(f"{component}: {age:.1f}s ago [{status}]")
            
        report_lines.extend([
            "",
            "=== CRITICAL OPERATIONS ===",
        ])
        
        # Add critical operations that might be stuck
        if self.critical_operations:
            for op_name, start_time in self.critical_operations.items():
                duration = current_time - start_time
                report_lines.append(f"{op_name}: Running for {duration:.1f}s")
        else:
            report_lines.append("No critical operations in progress")
            
        report_lines.extend([
            "",
            "=== WATCHDOG STATISTICS ===",
            f"Total health checks: {self.stats['total_checks']}",
            f"Warnings issued: {self.stats['warnings_issued']}",
            f"Activity updates: {self.stats['activity_updates']}",
            f"Previous forced exits: {self.stats['forced_exits'] - 1}",  # -1 because current crash increments it
        ])
        
        return "\n".join(report_lines)
        
    def _save_crash_report(self, crash_report: str):
        """Save crash report to file."""
        try:
            # Get the log directory - handle case where overlord module might not be available
            try:
                from overlord import get_app_data_path
                log_dir = get_app_data_path()
            except ImportError:
                # Fallback for testing or standalone usage
                import os
                log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Overlord")
                os.makedirs(log_dir, exist_ok=True)
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            crash_file = os.path.join(log_dir, f"crash_report_{timestamp}.txt")
            
            with open(crash_file, 'w', encoding='utf-8') as f:
                f.write(crash_report)
                
            logging.critical(f"Crash report saved to: {crash_file}")
        except Exception as e:
            logging.error(f"Failed to save crash report: {e}")
            
    def _force_crash(self):
        """Force the application to crash."""
        try:
            # Try to flush all logs first
            logging.shutdown()
        except:
            pass
            
        # Force exit with error code
        os._exit(1)
        
    def _check_critical_operations(self, current_time: float):
        """Check if any critical operations have been running too long."""
        stuck_operations = []
        
        for op_name, start_time in self.critical_operations.items():
            duration = current_time - start_time
            if duration > self.hang_timeout:
                stuck_operations.append((op_name, duration))
                
        if stuck_operations:
            self.stats['warnings_issued'] += 1
            for op_name, duration in stuck_operations:
                logging.warning(f"Critical operation '{op_name}' has been running for {duration:.1f}s (threshold: {self.hang_timeout}s)")
                
    def _check_thread_health(self, current_time: float):
        """Check the health of registered threads."""
        dead_threads = []
        
        for thread_name, thread_info in self.thread_states.items():
            thread_obj = thread_info['thread']
            was_alive = thread_info['is_alive']
            is_alive = thread_obj.is_alive()
            
            # Update state
            thread_info['is_alive'] = is_alive
            thread_info['last_seen'] = current_time
            
            # Check for unexpected thread death
            if was_alive and not is_alive:
                dead_threads.append(thread_name)
                
        if dead_threads:
            self.stats['warnings_issued'] += 1
            logging.warning(f"Threads died unexpectedly: {', '.join(dead_threads)}")
            
    def _check_component_health(self, current_time: float):
        """Check the health of registered components."""
        stale_components = []
        
        for component, last_time in self.component_health.items():
            age = current_time - last_time
            if age > self.hang_timeout * 0.8:  # Warn at 80% of timeout
                stale_components.append((component, age))
                
        if stale_components:
            self.stats['warnings_issued'] += 1
            for component, age in stale_components:
                logging.warning(f"Component '{component}' hasn't reported activity for {age:.1f}s")
                
    def _check_system_resources(self):
        """Check system resources that might indicate problems."""
        try:
            # Check active thread count
            active_threads = threading.active_count()
            if active_threads > 50:  # Arbitrary threshold
                logging.warning(f"High thread count detected: {active_threads}")
                
            # Force garbage collection and check for growth
            collected = gc.collect()
            if collected > 1000:  # Arbitrary threshold
                logging.warning(f"High garbage collection: {collected} objects collected")
                
        except Exception as e:
            logging.debug(f"Resource check failed: {e}")


# Global watchdog instance
watchdog = WatchdogMonitor()

def start_watchdog_monitoring(check_interval: int = 30, hang_timeout: int = 300):
    """Start the global watchdog monitor."""
    global watchdog
    watchdog = WatchdogMonitor(check_interval, hang_timeout)
    watchdog.start()
    return watchdog

def stop_watchdog_monitoring():
    """Stop the global watchdog monitor."""
    global watchdog
    if watchdog:
        watchdog.stop()

def update_activity(component: str = "main"):
    """Update activity for the global watchdog."""
    global watchdog
    if watchdog and watchdog.is_running:
        watchdog.update_activity(component)

def start_critical_operation(operation_name: str):
    """Mark the start of a critical operation."""
    global watchdog
    if watchdog and watchdog.is_running:
        watchdog.start_critical_operation(operation_name)

def end_critical_operation(operation_name: str):
    """Mark the end of a critical operation."""
    global watchdog
    if watchdog and watchdog.is_running:
        watchdog.end_critical_operation(operation_name)
