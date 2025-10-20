# GitHub Copilot Instructions for Overlord

## Project Overview

Overlord is an Electron-based desktop application that manages automated rendering workflows using Daz Studio and NVIDIA Iray Server. It provides a comprehensive GUI for long-running batch rendering operations, converting 3D models into 2D game assets.

### Technology Stack

- **Framework**: Electron 38.3.0
- **Language**: JavaScript (Node.js)
- **Architecture**: Single-file application (`overlord.js`)
- **UI**: HTML/CSS embedded via template literals and data URLs
- **IPC**: Electron's ipcMain/ipcRenderer for main-renderer communication
- **External Tools**: Daz Studio 4.x, NVIDIA Iray Server, PowerShell scripts
- **Build**: electron-builder for Windows executables

### Key Dependencies

- `electron`: Desktop application framework
- `winreg`: Windows registry access for startup configuration
- `archiver`: Creating zip archives for rendered assets
- `fs`, `path`, `child_process`: Node.js core modules for file/process management

## Architecture Principles

### Single-File Design

**CRITICAL**: The main application (`overlord.js`) is intentionally a single file (~2500 lines). This is a design choice for simplicity and portability.

- **Never** suggest splitting into multiple modules
- All HTML, CSS, and renderer JavaScript must be inline using template literals
- Use data URLs for loading HTML content: `win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html))`
- Keep utility scripts in `scripts/` folder (PowerShell, Daz Script, utility JS)

### Code Organization Within Single File

The file is organized into logical sections:

1. **Imports and Constants** (top)
2. **Global State Variables**
3. **Utility Functions** (file operations, parsing, etc.)
4. **IPC Handlers** (main process handlers)
5. **Window Management** (createWindow, splash screen, etc.)
6. **HTML/CSS/Renderer Code** (template literals at bottom)
7. **App Lifecycle** (initialization, ready events)

### IPC Communication Pattern

All communication between main and renderer processes uses:

```javascript
// Main process (handler)
ipcMain.handle('channel-name', async (event, arg1, arg2) => {
  // Process and return result
  return result;
});

// Renderer process (caller)
const result = await ipcRenderer.invoke('channel-name', arg1, arg2);
```

**Never** use `send`/`on` patterns - always use `handle`/`invoke` for consistency.

## Coding Guidelines

### JavaScript Style

- Use modern ES6+ syntax (async/await, arrow functions, destructuring)
- Prefer `const` over `let`, avoid `var`
- Use template literals for string concatenation
- Use async/await instead of Promise chains where appropriate
- Keep functions focused and modular despite single-file architecture

### Error Handling

- Always wrap file operations in try-catch blocks
- Log errors to console and Overlord log file
- Provide user-friendly error messages via dialogs
- Never let the application crash - handle all edge cases

```javascript
try {
  const data = fs.readFileSync(filePath, 'utf8');
  // Process data
} catch (error) {
  console.error('Failed to read file:', error);
  dialog.showErrorBox('Error', `Failed to read file: ${error.message}`);
}
```

### File Path Handling

- Always use `path.join()` for constructing paths
- Use `resourcePath()` helper for resources in development vs production
- Normalize paths with `path.resolve()` before file operations
- Handle both forward and backward slashes in user input

### Resource Management

- Clean up intervals and timeouts when stopping operations
- Close file handles properly
- Terminate child processes on app quit
- Clear monitoring intervals when windows close

## Feature-Specific Guidelines

### Rendering Pipeline

The rendering process involves:

1. **Template Generation**: Create .duf file from template with substitutions
2. **Daz Studio Launch**: Spawn headless Daz instances via PowerShell
3. **File Monitoring**: Watch output directory for new rendered images
4. **Progress Tracking**: Count images, calculate ETA, update UI
5. **Shadow Rendering**: Automatically double total count when enabled
6. **Cleanup**: Terminate processes, stop monitoring on completion

**Key Functions**:
- `startRender()`: Initiates rendering workflow
- `stopRender()`: Gracefully terminates all processes
- `startFileMonitoring()`: Watches directory during render (2s interval)
- `startContinuousImageMonitoring()`: Updates file details always (5s interval)
- `calculateAverageRenderTime()`: Uses recent file intervals (last 10) for accurate ETA

### Settings Management

Settings are stored in `%APPDATA%\Overlord\settings.json`:

- Auto-save on every change
- Registry integration for Windows startup (uses `winreg`)
- System tray integration via `minimize_to_tray`
- Hide DAZ instances option affects process creation

### Monitoring and Progress

**Two separate monitoring systems**:

1. **Render Monitoring** (`startFileMonitoring`):
   - Runs every 2 seconds during active render
   - Updates progress, ETA, and render statistics
   - Stops when render completes or is stopped

2. **Continuous Monitoring** (`startContinuousImageMonitoring`):
   - Runs every 5 seconds always (even when not rendering)
   - Updates File Details section with newest image info
   - Runs from app start until window close

**Never** combine these - they serve different purposes.

### Estimation Algorithm

```javascript
// Calculate average time between recent file creations
// NOT total elapsed time / file count
const intervals = [];
for (let i = 1; i < recentFiles.length; i++) {
  intervals.push(recentFiles[i].mtime - recentFiles[i-1].mtime);
}
const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
```

This provides more accurate ETAs than simple elapsed/count division.

### UI/UX Patterns

- **Monospace Fonts**: Use `'Consolas', 'Courier New', monospace` for file paths and technical data
- **Date Formatting**: Display as "3:14 PM, February 15th, 2025" with ordinal suffixes
- **Disable Controls**: Disable input fields during active render
- **Clear on Stop**: Reset output details (Images Completed, Remaining, ETA) to '-' when stopping
- **Square Preview**: Image preview is 1:1 aspect ratio, letterboxed if needed

### Log Viewing

Three log types with viewer dialogs:

1. **Overlord Log**: `%APPDATA%\Overlord\log.txt`
2. **Iray Server Log**: `%PROGRAMDATA%\NVIDIA Corporation\Iray Server\log\log.txt`
3. **DAZ Studio Log**: `%APPDATA%\DAZ 3D\Studio4\log.txt`

All use same modal pattern with monospace text display.

## Integration with External Tools

### Daz Studio

- Launched via PowerShell script (`scripts/stopIrayServer.ps1` for cleanup)
- Uses DAZ Script (.dsa files in `scripts/`)
- Headless mode when `hide_daz_instances` enabled
- Communication via file system (no direct API)

### PowerShell Scripts

- Located in `scripts/` folder
- Called via `child_process.spawn('powershell', ['-ExecutionPolicy', 'Bypass', '-File', scriptPath])`
- Monitor output for errors
- Handle process termination gracefully

### Template System

- Master template at `templates/masterTemplate.duf`
- Substitution markers: `%SUBJECT_FILE%`, `%ANIM_FILE%`, etc.
- Output to temp files in system temp directory
- Clean up temp files after render

## Common Tasks

### Adding New Settings

1. Add default value to `defaultSettings` object
2. Add UI element in settings dialog HTML
3. Add IPC handler logic in `save-settings` handler
4. Load value in `load-settings` handler
5. Use setting in relevant render/process logic

### Adding New IPC Channels

1. Create handler in main process:
   ```javascript
   ipcMain.handle('new-channel', async (event, arg) => {
     // Logic here
     return result;
   });
   ```

2. Call from renderer:
   ```javascript
   const result = await ipcRenderer.invoke('new-channel', arg);
   ```

3. Expose in `preload` context if needed (currently using `nodeIntegration: true`)

### Adding New Monitoring

- Use `setInterval` and store handle globally
- Clear interval with `clearInterval` on stop/close
- Choose appropriate interval (2s for active, 5s for passive)
- Update specific UI elements via `document.getElementById`

## Testing Considerations

- Test with actual Daz Studio and Iray Server installation
- Verify long-running stability (renders can take hours/days)
- Test resource cleanup (memory leaks, process orphans)
- Verify Windows registry modifications work correctly
- Test all file path edge cases (spaces, special chars, long paths)
- Verify system tray integration on minimize
- Test About dialog with GitHub API (rate limiting, offline scenarios)

## Building and Distribution

- Build with: `npm run build`
- Uses electron-builder with NSIS and portable targets
- Icon: `images/favicon.ico`
- Includes all resources: `images/`, `scripts/`, `templates/`
- Windows-only distribution (registry, PowerShell dependencies)

## Common Pitfalls to Avoid

1. **Don't** suggest multi-file architecture - single file is intentional
2. **Don't** use `send`/`on` IPC pattern - use `handle`/`invoke`
3. **Don't** forget to clear intervals/timeouts
4. **Don't** use absolute paths - use `path.join()` and `resourcePath()`
5. **Don't** forget error handling around file operations
6. **Don't** mix the two monitoring systems
7. **Don't** use simple elapsed/count for ETA - use interval averaging
8. **Don't** forget to update both total images when shadow rendering enabled
9. **Don't** leave output details populated after stopping render
10. **Don't** use PNG - always use WebP for images (90% quality)

## Documentation Standards

- Use JSDoc comments for complex functions
- Explain non-obvious logic with inline comments
- Keep comments up-to-date with code changes
- Document IPC channel purposes and parameters
- Note any Daz Studio or Iray Server specific behaviors

## Security Considerations

- Sanitize user input before file operations
- Validate file paths to prevent traversal attacks
- Be cautious with `child_process` execution
- Never execute user-provided code
- Validate data from GitHub API in About dialog
- Handle registry modifications safely (Windows startup)

## Performance Guidelines

- Use async file operations where possible
- Batch file system operations
- Debounce rapid UI updates
- Clean up resources promptly
- Monitor memory usage in long-running renders
- Use efficient data structures (Maps for lookups, Arrays for iteration)

## Future Considerations

When suggesting new features:

- Maintain single-file architecture
- Consider impact on long-running stability
- Ensure Windows compatibility
- Keep UI responsive during heavy operations
- Consider resource usage (CPU, memory, disk I/O)
- Maintain backward compatibility with existing settings
- Follow established IPC patterns
- Keep external dependencies minimal

## Related Projects

- **DaggerQuest**: Primary consumer of rendered assets
- **Plains of Shinar**: Another game using Overlord pipeline
- Asset repositories use organized output from constructZipper utility

---

Remember: Overlord is designed for stability, efficiency, and ease of use. Any suggestions should prioritize these qualities over complexity or cleverness.
