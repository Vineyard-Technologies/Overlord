# Contributing to Overlord

Thank you for your interest in contributing to Overlord! This is a Python dashboard that controls Daz Studio for long-running operations.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a new branch for your feature or bug fix
4. Set up the development environment
5. Make your changes
6. Test your changes thoroughly
7. Submit a pull request

## About Overlord

Overlord is designed to:

- Control Daz Studio through Python automation
- Run for months with low CPU/GPU footprint
- Provide a dashboard interface for long-running operations
- Interface with Daz Script (QtScript-based scripting language)

## Development Environment

To contribute to Overlord:

- Python 3.x knowledge
- Understanding of GUI frameworks (likely tkinter, PyQt, or similar)
- Familiarity with Daz Studio and Daz Script
- Knowledge of long-running application design patterns
- Understanding of system resource optimization

### Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Ensure Daz Studio is installed and accessible
3. Set up any required Daz Studio scripts or plugins
4. Configure environment variables if needed

## Architecture Guidelines

### Performance Considerations

- Prioritize low CPU/GPU usage
- Implement efficient memory management
- Use appropriate threading for long-running tasks
- Minimize resource consumption during idle periods
- Implement proper cleanup and resource disposal

### Stability Requirements

- Design for months of continuous operation
- Implement robust error handling and recovery
- Use appropriate logging for debugging
- Handle edge cases and unexpected shutdowns gracefully
- Implement health monitoring and self-diagnostics

## Code Style and Standards

- Follow PEP 8 Python style guidelines
- Use type hints where appropriate
- Write comprehensive docstrings
- Implement proper error handling
- Use meaningful variable and function names
- Keep functions focused and modular

## Daz Studio Integration

- Understand Daz Script (QtScript-based) syntax
- Follow Daz Studio API best practices
- Handle Daz Studio communication errors gracefully
- Implement proper session management
- Consider Daz Studio version compatibility

## Submitting Changes

### Pull Requests

1. Ensure code follows style guidelines
2. Add/update tests for new functionality
3. Test with actual Daz Studio integration
4. Verify resource usage remains low
5. Include clear commit messages
6. Provide detailed description of changes
7. Update documentation if needed

### Bug Reports

When reporting bugs:

- Describe the issue clearly
- Include steps to reproduce
- Provide system information (OS, Python version, Daz Studio version)
- Include relevant log files or error messages
- Note resource usage patterns if relevant
- Specify duration of operation before issue occurred

### Feature Requests

For new features:

- Describe the functionality and use case
- Consider impact on performance and stability
- Discuss integration with existing dashboard
- Consider Daz Studio compatibility requirements
- Evaluate resource usage implications

## Testing

### Test Requirements

- Unit tests for core functionality
- Integration tests with Daz Studio (where possible)
- Performance testing for resource usage
- Long-running stability tests
- Error handling and recovery tests

### Test Environment

- Test with actual Daz Studio installation
- Verify cross-platform compatibility
- Test various Daz Studio versions if applicable
- Monitor resource usage during testing
- Test error recovery scenarios

## Code Review Process

All submissions are reviewed for:

- Code quality and maintainability
- Performance and resource efficiency
- Proper error handling
- Daz Studio integration best practices
- Documentation completeness
- Test coverage

## Documentation

When contributing:

- Update relevant documentation
- Include inline code comments
- Document any new Daz Script interactions
- Update installation/setup instructions if needed
- Document configuration options

## Questions?

If you have questions about Overlord, Daz Studio integration, or contributing, feel free to open an issue for discussion.

Thank you for contributing to Overlord!
