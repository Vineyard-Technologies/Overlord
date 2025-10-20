# Support

Thank you for your interest in Overlord! This document outlines how to get help and support for the Asset Creation Pipeline Management Tool.

## Getting Help

### Overlord Support

If you're experiencing issues with Overlord:

1. **Check Documentation**: Review the comprehensive [README.md](README.md) for installation and usage instructions
2. **Browse Known Issues**: Check our [Issues](https://github.com/Vineyard-Technologies/Overlord/issues) page for known problems and solutions
3. **Community Discussion**: Join discussions in our [Discussions](https://github.com/Vineyard-Technologies/Overlord/discussions) section

### Technical Support

For technical issues, bugs, or setup problems:

1. **Search Existing Issues**: Check if your issue has already been reported
2. **Create a Bug Report**: If you find a new bug, please [open an issue](https://github.com/Vineyard-Technologies/Overlord/issues/new) with:
   - Clear description of the problem
   - Steps to reproduce the issue
   - System specifications (OS, Node.js version, Electron version, Daz Studio version)
   - Iray Server version and configuration
   - Complete error messages and stack traces
   - Log files if available

### Development Support

For questions about contributing to Overlord:

1. **Read Contributing Guidelines**: Check our [CONTRIBUTING.md](CONTRIBUTING.md) file
2. **Code of Conduct**: Review our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
3. **Start a Discussion**: Ask questions in [Discussions](https://github.com/Vineyard-Technologies/Overlord/discussions)

## Contact Information

### Primary Channels

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For general questions and community interaction
- **Documentation**: Comprehensive guides in the repository

### Response Times

- **Critical Issues**: Response within 24-48 hours
- **Bug Reports**: We aim to acknowledge within 48-72 hours
- **Feature Requests**: Response within 1 week
- **General Questions**: Response within 1 week
- **Security Issues**: See our [SECURITY.md](SECURITY.md) policy

## What We Support

### Supported Platforms

- **Operating Systems**: Windows 10/11 (primary), Windows Server
- **Node.js Versions**: 18 or higher
- **Electron**: Latest stable version
- **Daz Studio**: Version 4.x
- **Iray Server**: Latest versions from IrayPlugins.com
- **Hardware**: NVIDIA GPUs with CUDA support (recommended for rendering)

### What's Included

- Installation and setup assistance
- Bug fixes for confirmed issues
- Performance optimization guidance
- Feature development based on community feedback
- Security updates and patches
- Documentation updates

### What's Not Included

- Custom asset creation services
- Third-party software troubleshooting (Daz Studio, Iray Server issues)
- Hardware recommendations or purchasing advice
- Real-time rendering support
- Training on Daz Studio or 3D modeling

## System Requirements

### Minimum Requirements

- **OS**: Windows 10 64-bit
- **RAM**: 8GB (16GB+ recommended)
- **Storage**: 10GB free space
- **GPU**: DirectX 11 compatible (NVIDIA GPU with CUDA support recommended)
- **Network**: Internet connection for downloads and updates

### Recommended Requirements

- **OS**: Windows 11 64-bit
- **RAM**: 32GB or more
- **Storage**: SSD with 50GB+ free space
- **GPU**: NVIDIA RTX series with 8GB+ VRAM
- **CPU**: Multi-core processor (8+ cores recommended)

## Community Guidelines

When seeking support:

- **Be Respectful**: Follow our Code of Conduct
- **Be Specific**: Provide detailed information about your issue
- **Be Patient**: Our team responds as quickly as possible
- **Search First**: Check if your question has already been answered
- **Help Others**: Share your knowledge with the community

## Frequently Asked Questions

### Installation Issues

**Q: Daz Studio installation fails**
- Download from official Daz3D website
- Ensure you have administrator privileges
- Check system requirements
- Disable antivirus temporarily during installation

**Q: Iray Server connection issues**
- Verify Iray Server is installed and running
- Check firewall settings
- Ensure correct ports are open
- Review Iray Server logs

**Q: Node.js dependency issues**
- Use Node.js 18 or higher
- Install with npm: `npm install`
- Check for conflicting packages
- Clear npm cache if needed: `npm cache clean --force`

### Performance Issues

**Q: Rendering is very slow**
- Ensure NVIDIA GPU drivers are up to date
- Check CUDA installation
- Monitor GPU memory usage
- Consider reducing render quality for testing

**Q: Overlord uses too much CPU/RAM**
- Adjust process priorities in configuration
- Limit concurrent render tasks
- Close unnecessary applications
- Consider upgrading hardware

### Workflow Issues

**Q: Assets not generating correctly**
- Check Daz Studio scene setup
- Verify export settings
- Review asset templates
- Check file permissions

**Q: Pipeline automation fails**
- Review command line arguments
- Check script permissions
- Verify file paths
- Monitor log files for errors

## Troubleshooting Steps

### Basic Diagnostics

1. **Check Prerequisites**:
   - Daz Studio 4 installed and functional
   - Iray Server installed and running
   - Node.js 18+ with all dependencies

2. **Verify Installation**:
   - Run Overlord with `npm start`
   - Check all required files are present
   - Test basic functionality

3. **Review Logs**:
   - Check Overlord log files
   - Review Daz Studio logs
   - Monitor Iray Server logs

### Advanced Troubleshooting

1. **Network Connectivity**:
   - Test Iray Server connection
   - Check firewall configuration
   - Verify port accessibility

2. **Performance Monitoring**:
   - Monitor CPU and RAM usage
   - Check GPU utilization
   - Review disk I/O performance

## Contributing to Support

You can help improve support for everyone:

- **Answer Questions**: Help other users in discussions
- **Report Issues**: Submit clear, detailed bug reports
- **Suggest Improvements**: Share ideas for better workflows
- **Share Solutions**: Document solutions you've found
- **Contribute Code**: Help improve the codebase
- **Update Documentation**: Help keep guides current

## Resources

### Documentation

- **Main Repository**: [Overlord](https://github.com/Vineyard-Technologies/Overlord)
- **Installation Guide**: Detailed setup instructions in README.md
- **API Documentation**: Code documentation and examples

### External Resources

- **Daz Studio**: [Daz3D.com](https://www.daz3d.com)
- **Iray Server**: [IrayPlugins.com](https://www.irayplugins.com)
- **Node.js**: [Node.js.org](https://nodejs.org)
- **Electron**: [Electronjs.org](https://www.electronjs.org)
- **NVIDIA CUDA**: [Developer.nvidia.com](https://developer.nvidia.com/cuda-zone)

### Related Projects

- **DaggerQuest**: [Main game repository](https://github.com/Vineyard-Technologies/DaggerQuest)
- **Assets Repository**: Where generated assets are stored

## Emergency Contacts

For critical issues that require immediate attention:

- **Security Issues**: Follow responsible disclosure in [SECURITY.md](SECURITY.md)
- **Legal Issues**: Contact through official channels
- **Urgent Bug Reports**: Mark as "critical" in GitHub issues

---

Thank you for using Overlord! Your feedback and contributions help make the asset creation pipeline better for everyone.
