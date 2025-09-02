"""
Test script for Overlord watchdog monitoring functionality.
This script can be used to test hang detection without running the full application.

Note: This script is intended for development and testing only.
It is not included in the production build of Overlord.
"""

import time
import threading
import logging
import sys
import os

# Add the src directory to path so we can import our modules
# Handle both development and potential bundled scenarios
try:
    # Try to import directly first
    from watchdog_monitor import start_watchdog_monitoring, stop_watchdog_monitoring, update_activity, start_critical_operation, end_critical_operation
    from overlord_config import WATCHDOG_CONFIG, DEBUG_CONFIG
except ImportError:
    # Fallback: add src directory to path
    current_dir = os.path.dirname(__file__)
    if os.path.basename(current_dir) != 'src':
        src_dir = os.path.join(current_dir, 'src')
        if os.path.exists(src_dir):
            sys.path.insert(0, src_dir)
    
    try:
        from watchdog_monitor import start_watchdog_monitoring, stop_watchdog_monitoring, update_activity, start_critical_operation, end_critical_operation
        from overlord_config import WATCHDOG_CONFIG, DEBUG_CONFIG
    except ImportError as e:
        print(f"ERROR: Cannot import monitoring modules: {e}")
        print("This test script requires the monitoring system modules.")
        print("Make sure you're running from the development environment.")
        sys.exit(1)

def setup_test_logging():
    """Set up logging for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[logging.StreamHandler()]
    )

def test_normal_operation():
    """Test normal operation with regular activity updates."""
    print("Testing normal operation...")
    
    for i in range(10):
        print(f"Normal operation step {i+1}/10")
        update_activity(f"test_step_{i+1}")
        time.sleep(2)
    
    print("Normal operation test completed")

def test_critical_operation():
    """Test critical operation monitoring."""
    print("Testing critical operation monitoring...")
    
    start_critical_operation("test_critical_op")
    
    for i in range(5):
        print(f"Critical operation step {i+1}/5")
        time.sleep(1)
        update_activity("critical_op_progress")
    
    end_critical_operation("test_critical_op")
    print("Critical operation test completed")

def test_hang_simulation():
    """Test hang detection by simulating a hang."""
    if not DEBUG_CONFIG.get("simulate_hangs", False):
        print("Hang simulation disabled in configuration. Enable 'simulate_hangs' in DEBUG_CONFIG to test.")
        return
        
    print("WARNING: Simulating hang for testing...")
    print("This will trigger the watchdog monitor and force application exit!")
    
    # Wait for user confirmation
    response = input("Type 'yes' to continue with hang simulation: ")
    if response.lower() != 'yes':
        print("Hang simulation cancelled")
        return
    
    print("Starting hang simulation...")
    print("Watchdog should detect hang and force crash after timeout period")
    
    # Start a critical operation but never end it
    start_critical_operation("test_hang_simulation")
    
    # Simulate a complete hang - no activity updates
    hang_duration = WATCHDOG_CONFIG["hang_timeout"] + 30  # Wait longer than timeout
    print(f"Hanging for {hang_duration} seconds...")
    time.sleep(hang_duration)
    
    # This should never be reached if watchdog is working
    print("ERROR: Hang simulation completed without watchdog intervention!")
    end_critical_operation("test_hang_simulation")

def test_thread_monitoring():
    """Test thread monitoring functionality."""
    print("Testing thread monitoring...")
    
    def worker_thread(thread_id):
        """Worker thread that reports activity."""
        for i in range(5):
            print(f"Worker thread {thread_id} step {i+1}/5")
            update_activity(f"worker_thread_{thread_id}")
            time.sleep(1)
    
    # Start multiple worker threads
    threads = []
    for i in range(3):
        thread = threading.Thread(target=worker_thread, args=(i+1,), name=f"TestWorker{i+1}")
        threads.append(thread)
        thread.start()
    
    # Wait for threads to complete
    for thread in threads:
        thread.join()
    
    print("Thread monitoring test completed")

def test_resource_monitoring():
    """Test resource monitoring functionality."""
    print("Testing resource monitoring...")
    
    # Simulate memory-intensive operation
    start_critical_operation("memory_test")
    
    large_data = []
    for i in range(100):
        # Create some data to use memory
        large_data.append([0] * 10000)
        if i % 10 == 0:
            update_activity("memory_allocation")
            print(f"Memory allocation step {i+1}/100")
    
    time.sleep(2)
    
    # Clean up
    del large_data
    end_critical_operation("memory_test")
    print("Resource monitoring test completed")

def main():
    """Main test function."""
    setup_test_logging()
    
    print("=" * 60)
    print("Overlord Watchdog Monitor Test Suite")
    print("=" * 60)
    
    # Start watchdog monitoring
    print("Starting watchdog monitoring...")
    watchdog = start_watchdog_monitoring(
        check_interval=WATCHDOG_CONFIG["check_interval"],
        hang_timeout=WATCHDOG_CONFIG["hang_timeout"]
    )
    
    if not watchdog:
        print("ERROR: Failed to start watchdog monitoring")
        return 1
    
    print(f"Watchdog started with {WATCHDOG_CONFIG['check_interval']}s check interval and {WATCHDOG_CONFIG['hang_timeout']}s hang timeout")
    
    try:
        # Run tests
        tests = [
            ("Normal Operation", test_normal_operation),
            ("Critical Operation", test_critical_operation),
            ("Thread Monitoring", test_thread_monitoring),
            ("Resource Monitoring", test_resource_monitoring),
        ]
        
        # Add hang simulation test if enabled
        if DEBUG_CONFIG.get("simulate_hangs", False):
            tests.append(("Hang Simulation", test_hang_simulation))
        
        for test_name, test_func in tests:
            print(f"\n--- Running {test_name} Test ---")
            try:
                test_func()
                print(f"{test_name} test PASSED")
            except Exception as e:
                print(f"{test_name} test FAILED: {e}")
                logging.exception(f"Test failure in {test_name}")
            
            # Brief pause between tests
            time.sleep(2)
            update_activity("test_suite_progress")
        
        print("\n--- All Tests Completed ---")
        print("Watchdog monitor will continue running for 30 seconds to demonstrate monitoring...")
        
        # Keep running for a bit to show monitoring in action
        for i in range(30):
            time.sleep(1)
            if i % 5 == 0:
                update_activity("test_suite_monitoring")
                print(f"Monitoring demonstration: {30-i} seconds remaining")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test suite error: {e}")
        logging.exception("Test suite error")
    finally:
        # Stop watchdog monitoring
        print("Stopping watchdog monitoring...")
        stop_watchdog_monitoring()
        print("Test suite completed")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
