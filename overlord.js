// ============================================================================
// OVERLORD - Asset Creation Pipeline Management Tool
// Electron/JavaScript Version
// ============================================================================

const { app, BrowserWindow, ipcMain, Menu, Tray, dialog, nativeTheme, shell, clipboard } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

// ============================================================================
// CONSTANTS AND CONFIGURATION
// ============================================================================

const APP_VERSION = '2.1.7';
const LOG_SIZE_MB = 10;
const LOG_SIZE_DAZ = '10m';
const RECENT_RENDER_TIMES_LIMIT = 25;

// Process startup delays (milliseconds)
const DAZ_STUDIO_STARTUP_DELAY = 5000;
const OVERLORD_CLOSE_DELAY = 2000;

// File extensions
const IMAGE_EXTENSIONS = ['.png'];
const PNG_EXTENSION = '.png';

// Default paths
const DEFAULT_OUTPUT_SUBDIR = 'Downloads/output';
const APPDATA_SUBFOLDER = 'Overlord';

// UI dimensions
const SPLASH_WIDTH = 400;
const SPLASH_HEIGHT = 400;

// Theme colors
const THEME_COLORS = {
  light: {
    bg: '#f0f0f0', fg: '#000000', entry_bg: '#ffffff', entry_fg: '#000000',
    button_bg: '#e1e1e1', button_fg: '#000000', frame_bg: '#f0f0f0',
    text_bg: '#ffffff', text_fg: '#000000', select_bg: '#0078d4',
    select_fg: '#ffffff', highlight_bg: '#cccccc', border: '#cccccc'
  },
  dark: {
    bg: '#2d2d30', fg: '#ffffff', entry_bg: '#3c3c3c', entry_fg: '#ffffff',
    button_bg: '#404040', button_fg: '#ffffff', frame_bg: '#2d2d30',
    text_bg: '#1e1e1e', text_fg: '#ffffff', select_bg: '#0078d4',
    select_fg: '#ffffff', highlight_bg: '#404040', border: '#555555'
  }
};

// Process names for monitoring
const DAZ_STUDIO_PROCESSES = ['DAZStudio.exe'];
const IRAY_SERVER_PROCESSES = ['iray_server.exe', 'iray_server_worker.exe'];

// Validation limits
const VALIDATION_LIMITS = {
  max_instances: 99, min_instances: 1,
  max_frame_rate: 999, min_frame_rate: 1,
};

// ============================================================================
// GLOBAL STATE
// ============================================================================

let mainWindow = null;
let tray = null;
let isRendering = false;
let initialTotalImages = 0;
let renderStartTime = null;
let shutdownTimerHandle = null;
let periodicMonitoringHandle = null;
let fileWatcherHandle = null;
let currentImagePath = null;
let currentTheme = 'dark';

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function getAppDataPath(subfolder = APPDATA_SUBFOLDER) {
  const appData = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
  return path.join(appData, subfolder);
}

function getLocalAppDataPath(subfolder = APPDATA_SUBFOLDER) {
  const localAppData = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
  return path.join(localAppData, subfolder);
}

function getDefaultOutputDirectory() {
  return path.join(os.homedir(), DEFAULT_OUTPUT_SUBDIR);
}

function getDisplayVersion() {
  return app.isPackaged ? APP_VERSION : 'dev';
}

function formatFileSize(sizeBytes) {
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`;
  } else if (sizeBytes < 1024 * 1024 * 1024) {
    return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
  } else {
    return `${(sizeBytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  }
}

function normalizePathForLogging(filePath) {
  if (filePath) {
    return filePath.replace(/\\/g, '/');
  }
  return filePath;
}

function resourcePath(relativePath) {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, relativePath);
  }
  return path.join(__dirname, relativePath);
}

function detectWindowsTheme() {
  return nativeTheme.shouldUseDarkColors ? 'dark' : 'light';
}

// ============================================================================
// LOGGING
// ============================================================================

function setupLogger() {
  const logDir = getAppDataPath();
  if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true });
  }
  
  const logPath = path.join(logDir, 'log.txt');
  console.log(`--- Overlord started --- (log file: ${normalizePathForLogging(logPath)}, max size: ${LOG_SIZE_MB} MB)`);
  
  // Redirect console to file (simple implementation)
  const logStream = fs.createWriteStream(logPath, { flags: 'a' });
  const originalLog = console.log;
  const originalError = console.error;
  const originalWarn = console.warn;
  
  console.log = function(...args) {
    const timestamp = new Date().toISOString();
    const message = `${timestamp} INFO: ${args.join(' ')}\n`;
    logStream.write(message);
    originalLog.apply(console, args);
  };
  
  console.error = function(...args) {
    const timestamp = new Date().toISOString();
    const message = `${timestamp} ERROR: ${args.join(' ')}\n`;
    logStream.write(message);
    originalError.apply(console, args);
  };
  
  console.warn = function(...args) {
    const timestamp = new Date().toISOString();
    const message = `${timestamp} WARNING: ${args.join(' ')}\n`;
    logStream.write(message);
    originalWarn.apply(console, args);
  };
}

// ============================================================================
// FILE AND JSON UTILITIES
// ============================================================================

function getFramesFromAnimationFile(animationFilepath) {
  const defaultFrames = 1;
  
  try {
    if (!animationFilepath || !fs.existsSync(animationFilepath)) {
      console.warn(`Animation file not found: ${normalizePathForLogging(animationFilepath)}. Using default of ${defaultFrames} frame.`);
      return defaultFrames;
    }
    
    const data = fs.readFileSync(animationFilepath, 'utf8');
    const animationData = JSON.parse(data);
    
    if (animationData.scene && animationData.scene.animations) {
      const animationsArray = animationData.scene.animations;
      
      for (const animation of animationsArray) {
        if (animation.keys) {
          const numFrames = animation.keys.length;
          if (numFrames > 1) {
            console.log(`Found ${numFrames} frames in animation file: ${normalizePathForLogging(animationFilepath)}`);
            return numFrames;
          }
        }
      }
      
      console.log(`No multi-frame animations found in ${normalizePathForLogging(animationFilepath)}. Using ${defaultFrames} frame.`);
      return defaultFrames;
    } else {
      console.warn(`No scene.animations found in animation file ${normalizePathForLogging(animationFilepath)}. Using default of ${defaultFrames} frame.`);
      return defaultFrames;
    }
  } catch (error) {
    console.error(`Error reading animation file ${normalizePathForLogging(animationFilepath)}: ${error.message}. Using default of ${defaultFrames} frame.`);
    return defaultFrames;
  }
}

function getAnglesFromSubjectFile(subjectFilepath) {
  const defaultAngles = 16;
  
  try {
    if (!subjectFilepath || !fs.existsSync(subjectFilepath)) {
      console.warn(`Subject file not found: ${normalizePathForLogging(subjectFilepath)}. Using default of ${defaultAngles} angles.`);
      return defaultAngles;
    }
    
    const data = fs.readFileSync(subjectFilepath, 'utf8');
    const subjectData = JSON.parse(data);
    
    if (subjectData.asset_info && subjectData.asset_info.angles) {
      const angles = subjectData.asset_info.angles;
      if (typeof angles === 'number' && angles > 0) {
        console.log(`Found ${angles} angles in subject file: ${normalizePathForLogging(subjectFilepath)}`);
        return angles;
      }
    }
    
    console.warn(`Number of angles not found in the JSON for ${normalizePathForLogging(subjectFilepath)}. Using default value of ${defaultAngles} angles.`);
    return defaultAngles;
  } catch (error) {
    console.error(`Error reading subject file ${normalizePathForLogging(subjectFilepath)}: ${error.message}. Using default of ${defaultAngles} angles.`);
    return defaultAngles;
  }
}

function calculateTotalImages(subjectFilepath, animationFilepaths, gearFilepaths = null) {
  if (!animationFilepaths || !animationFilepaths[0]) {
    console.log('No animation files specified, using 1 frame (static render)');
    animationFilepaths = ['static'];
  }
  
  let gearCount = 1;
  if (!gearFilepaths || !gearFilepaths[0] || gearFilepaths[0].trim() === '') {
    console.log('No gear files specified');
  } else {
    const validGearFiles = gearFilepaths.filter(gear => gear && gear.trim());
    gearCount = validGearFiles.length;
    console.log(`Found ${gearCount} gear files - will multiply render count`);
  }
  
  const angles = getAnglesFromSubjectFile(subjectFilepath);
  let totalImages = 0;
  
  for (const animationFilepath of animationFilepaths) {
    if (animationFilepath === 'static' || !animationFilepath.trim()) {
      const frames = 1;
      const imagesForThisAnimation = angles * frames * gearCount;
      totalImages += imagesForThisAnimation;
      console.log(`Static render: ${angles} angles × ${frames} frame × ${gearCount} gear = ${imagesForThisAnimation} images`);
    } else {
      const frames = getFramesFromAnimationFile(animationFilepath.trim());
      const imagesForThisAnimation = angles * frames * gearCount;
      totalImages += imagesForThisAnimation;
      console.log(`Animation ${normalizePathForLogging(animationFilepath)}: ${angles} angles × ${frames} frames × ${gearCount} gear = ${imagesForThisAnimation} images`);
    }
  }
  
  console.log(`Total images to render: ${totalImages}`);
  return totalImages;
}

function findNewestImage(directory) {
  const imageFiles = [];
  const maxFiles = 100;
  
  function walkDir(dir) {
    try {
      const files = fs.readdirSync(dir);
      
      for (const file of files) {
        const filePath = path.join(dir, file);
        const stat = fs.statSync(filePath);
        
        if (stat.isDirectory()) {
          walkDir(filePath);
        } else if (IMAGE_EXTENSIONS.some(ext => file.toLowerCase().endsWith(ext))) {
          imageFiles.push({ path: filePath, mtime: stat.mtime.getTime() });
          
          if (imageFiles.length > maxFiles * 2) {
            imageFiles.sort((a, b) => b.mtime - a.mtime);
            imageFiles.splice(maxFiles);
          }
        }
      }
    } catch (error) {
      // Ignore errors for inaccessible directories
    }
  }
  
  walkDir(directory);
  imageFiles.sort((a, b) => b.mtime - a.mtime);
  
  return imageFiles.slice(0, maxFiles).map(f => f.path);
}

// ============================================================================
// PROCESS MANAGEMENT
// ============================================================================

async function checkProcessRunning(processNames) {
  try {
    const { stdout } = await execPromise('tasklist');
    
    for (const name of processNames) {
      if (stdout.toLowerCase().includes(name.toLowerCase())) {
        return true;
      }
    }
    return false;
  } catch (error) {
    return false;
  }
}

async function killProcessesByName(processNames) {
  let killedCount = 0;
  
  for (const processName of processNames) {
    try {
      await execPromise(`taskkill /F /IM ${processName}`);
      console.log(`Killed process: ${processName}`);
      killedCount++;
    } catch (error) {
      // Process might not be running
    }
  }
  
  return killedCount;
}

async function isDazStudioRunning() {
  return checkProcessRunning(DAZ_STUDIO_PROCESSES);
}

async function isIrayServerRunning() {
  return checkProcessRunning(IRAY_SERVER_PROCESSES);
}

async function stopIrayServer() {
  try {
    const scriptPath = app.isPackaged
      ? path.join(process.resourcesPath, 'scripts', 'stopIrayServer.ps1')
      : path.join(__dirname, 'scripts', 'stopIrayServer.ps1');
    
    if (!fs.existsSync(scriptPath)) {
      console.error(`stopIrayServer.ps1 not found at: ${normalizePathForLogging(scriptPath)}`);
      return 0;
    }
    
    console.log('Stopping Iray Server using stopIrayServer.ps1');
    
    return new Promise((resolve) => {
      const ps = spawn('powershell.exe', [
        '-ExecutionPolicy', 'Bypass',
        '-File', scriptPath
      ]);
      
      ps.on('close', (code) => {
        if (code === 0) {
          console.log('Iray Server stopped successfully via PowerShell script');
          resolve(1);
        } else {
          console.warn(`stopIrayServer.ps1 returned non-zero exit code: ${code}`);
          resolve(0);
        }
      });
      
      ps.on('error', (error) => {
        console.error('Failed to run stopIrayServer.ps1:', error);
        resolve(0);
      });
      
      setTimeout(() => {
        ps.kill();
        console.error('stopIrayServer.ps1 timed out after 30 seconds');
        resolve(0);
      }, 30000);
    });
  } catch (error) {
    console.error('Error stopping Iray Server:', error);
    return 0;
  }
}

async function stopAllRenderProcesses() {
  console.log('Stopping all render-related processes (DAZStudio, Iray Server)');
  
  const results = {
    daz_studio: await killProcessesByName(DAZ_STUDIO_PROCESSES),
    iray_server: await stopIrayServer()
  };
  
  const total = results.daz_studio + results.iray_server;
  console.log(`Stopped ${total} total process(es): ${results.daz_studio} DAZ Studio, ${results.iray_server} Iray Server`);
  
  return results;
}

// ============================================================================
// SETTINGS MANAGEMENT
// ============================================================================

class SettingsManager {
  constructor() {
    this.settingsDir = getAppDataPath();
    this.settingsFile = path.join(this.settingsDir, 'settings.json');
    
    this.defaultSettings = {
      subject: '',
      animations: [],
      prop_animations: [],
      gear: [],
      gear_animations: [],
      output_directory: getDefaultOutputDirectory(),
      number_of_instances: '1',
      frame_rate: '30',
      render_shadows: true,
      shutdown_on_finish: true,
      hide_daz_instances: true,
      cache_db_size_threshold_gb: '10',
      minimize_to_tray: true,
      start_on_startup: true,
      last_directories: {
        subject: '', animations: '', prop_animations: '',
        gear: '', gear_animations: '', output_directory: '',
        template: '', general_file: '', general_folder: ''
      }
    };
    
    if (!fs.existsSync(this.settingsDir)) {
      fs.mkdirSync(this.settingsDir, { recursive: true });
    }
  }
  
  loadSettings() {
    try {
      if (fs.existsSync(this.settingsFile)) {
        const data = fs.readFileSync(this.settingsFile, 'utf8');
        const settings = JSON.parse(data);
        const merged = { ...this.defaultSettings, ...settings };
        console.log('Settings loaded from', this.settingsFile);
        return merged;
      } else {
        console.log('No settings file found, using defaults');
      }
    } catch (error) {
      console.warn('Failed to load settings:', error.message, ', using defaults');
    }
    
    return { ...this.defaultSettings };
  }
  
  saveSettings(settings) {
    try {
      const issues = this.validateSettings(settings);
      if (issues.length > 0) {
        console.warn('Settings validation warnings:', issues);
      }
      
      fs.writeFileSync(this.settingsFile, JSON.stringify(settings, null, 2), 'utf8');
      console.log('Settings saved to', this.settingsFile);
      return true;
    } catch (error) {
      console.error('Failed to save settings:', error);
      return false;
    }
  }
  
  validateSettings(settings) {
    const issues = [];
    
    const instances = parseInt(settings.number_of_instances);
    if (isNaN(instances) || instances < VALIDATION_LIMITS.min_instances || instances > VALIDATION_LIMITS.max_instances) {
      issues.push('Invalid number of instances');
    }
    
    const frameRate = parseInt(settings.frame_rate);
    if (isNaN(frameRate) || frameRate < VALIDATION_LIMITS.min_frame_rate || frameRate > VALIDATION_LIMITS.max_frame_rate) {
      issues.push('Invalid frame rate');
    }
    
    const cacheThreshold = parseFloat(settings.cache_db_size_threshold_gb);
    if (isNaN(cacheThreshold) || cacheThreshold < 0.1 || cacheThreshold > 1000) {
      issues.push('Invalid cache size threshold');
    }
    
    return issues;
  }
}

const settingsManager = new SettingsManager();

// ============================================================================
// RENDER MANAGEMENT
// ============================================================================

async function startRender(settings) {
  if (isRendering) {
    throw new Error('Render already in progress');
  }
  
  isRendering = true;
  renderStartTime = Date.now();
  
  // Calculate total images
  initialTotalImages = calculateTotalImages(
    settings.subject,
    settings.animations,
    settings.gear
  );
  
  const appDataDir = getLocalAppDataPath();
  const resultsDir = path.join(appDataDir, 'IrayServer', 'results', 'admin');
  const finalOutputDir = settings.output_directory;
  
  // Create directories
  if (!fs.existsSync(resultsDir)) {
    fs.mkdirSync(resultsDir, { recursive: true });
  }
  if (!fs.existsSync(finalOutputDir)) {
    fs.mkdirSync(finalOutputDir, { recursive: true });
  }
  
  console.log('Skipping Iray Server startup - will be handled by DAZ Script');
  
  // Prepare file paths
  const subjectFile = settings.subject.replace(/\\/g, '/');
  const animations = settings.animations.map(a => a.replace(/\\/g, '/'));
  const propAnimations = (settings.prop_animations || []).map(a => a.replace(/\\/g, '/'));
  const gear = (settings.gear || []).map(g => g.replace(/\\/g, '/'));
  const gearAnimations = (settings.gear_animations || []).map(a => a.replace(/\\/g, '/'));
  
  // Get DAZ executable path
  const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
  const dazExecutablePath = path.join(programFiles, 'DAZ 3D', 'DAZStudio4', 'DAZStudio.exe');
  
  // Get template and script paths
  let renderScriptPath, templatePath;
  
  if (app.isPackaged) {
    renderScriptPath = path.join(process.resourcesPath, 'scripts', 'masterRenderer.dsa').replace(/\\/g, '/');
    templatePath = path.join(process.resourcesPath, 'templates', 'masterTemplate.duf').replace(/\\/g, '/');
  } else {
    renderScriptPath = path.join(__dirname, 'scripts', 'masterRenderer.dsa').replace(/\\/g, '/');
    templatePath = path.join(__dirname, 'templates', 'masterTemplate.duf').replace(/\\/g, '/');
  }
  
  // Create JSON map for DAZ Studio
  const jsonMap = {
    num_instances: settings.number_of_instances.toString(),
    image_output_dir: finalOutputDir.replace(/\\/g, '/'),
    frame_rate: settings.frame_rate.toString(),
    subject_file: subjectFile,
    animations: animations,
    prop_animations: propAnimations,
    gear: gear,
    gear_animations: gearAnimations,
    template_path: templatePath,
    render_shadows: settings.render_shadows,
    results_directory_path: resultsDir.replace(/\\/g, '/'),
    cache_db_size_threshold_gb: settings.cache_db_size_threshold_gb.toString()
  };
  
  if (!fs.existsSync(dazExecutablePath)) {
    throw new Error(`DAZ Studio executable not found: ${dazExecutablePath}`);
  }
  
  if (!fs.existsSync(renderScriptPath)) {
    throw new Error(`Render script not found: ${renderScriptPath}`);
  }
  
  const jsonMapStr = JSON.stringify(jsonMap);
  const numInstances = parseInt(settings.number_of_instances);
  
  // Launch DAZ Studio instances
  for (let i = 0; i < numInstances; i++) {
    const command = [
      '-scriptArg', jsonMapStr,
      '-instanceName', '#',
      '-logSize', LOG_SIZE_DAZ,
    ];
    
    if (settings.hide_daz_instances) {
      command.push('-headless');
    }
    
    command.push('-noPrompt', renderScriptPath);
    
    console.log(`Launching DAZ Studio instance ${i + 1}/${numInstances}`);
    spawn(dazExecutablePath, command, { detached: true, stdio: 'ignore' });
    
    if (i < numInstances - 1) {
      await new Promise(resolve => setTimeout(resolve, 5000));
    }
  }
  
  console.log('All render instances launched');
  
  // Start file monitoring
  startFileMonitoring(finalOutputDir);
  
  return { success: true, message: 'Render started successfully' };
}

async function stopRender() {
  isRendering = false;
  stopFileMonitoring();
  await stopAllRenderProcesses();
  return { success: true, message: 'Render stopped successfully' };
}

function getRenderStatus() {
  return {
    isRendering,
    stats: {
      totalImages: initialTotalImages,
      renderedCount: 0, // TODO: Implement actual counting
      progress: 0
    }
  };
}

// ============================================================================
// FILE MONITORING
// ============================================================================

function startFileMonitoring(directory) {
  stopFileMonitoring();
  
  fileWatcherHandle = setInterval(() => {
    const images = findNewestImage(directory);
    
    if (images && images.length > 0) {
      const latestImage = images[0];
      
      if (latestImage !== currentImagePath) {
        currentImagePath = latestImage;
        
        try {
          const stats = fs.statSync(latestImage);
          const imageData = {
            path: latestImage,
            filename: path.basename(latestImage),
            size: stats.size,
            modified: stats.mtime
          };
          
          if (mainWindow) {
            mainWindow.webContents.send('image-updated', imageData);
          }
        } catch (error) {
          console.error('Error getting image stats:', error);
        }
      }
    }
  }, 2000);
}

function stopFileMonitoring() {
  if (fileWatcherHandle) {
    clearInterval(fileWatcherHandle);
    fileWatcherHandle = null;
  }
}

// ============================================================================
// SINGLE INSTANCE CHECK
// ============================================================================

const singleInstanceLock = app.requestSingleInstanceLock();

if (!singleInstanceLock) {
  dialog.showMessageBoxSync({
    type: 'info',
    title: 'Overlord Already Running',
    message: 'Another instance of Overlord is already running.\n\nOnly one instance can run at a time.'
  });
  app.quit();
  process.exit(0);
}

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

// ============================================================================
// WINDOW CREATION
// ============================================================================

function createWindow() {
  currentTheme = detectWindowsTheme();
  
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    icon: resourcePath(path.join('images', 'favicon.ico')),
    backgroundColor: THEME_COLORS[currentTheme].bg,
    show: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });
  
  // Hide default Electron menu bar (we have our own in the HTML)
  mainWindow.setMenuBarVisibility(false);
  mainWindow.setMenu(null);
  
  // Create HTML content
  const htmlContent = generateHTML();
  mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(htmlContent)}`);
  
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.maximize();
    
    // Check for auto-start
    const autoStart = process.argv.includes('--startRender');
    if (autoStart) {
      mainWindow.webContents.executeJavaScript('if (window.autoStartRender) window.autoStartRender();');
    }
  });
  
  mainWindow.on('minimize', () => {
    const settings = settingsManager.loadSettings();
    if (settings.minimize_to_tray && tray) {
      mainWindow.hide();
    }
  });
  
  mainWindow.on('close', () => {
    stopFileMonitoring();
    if (tray) {
      tray.destroy();
      tray = null;
    }
  });
  
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
  
  // Development mode
  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }
}

// ============================================================================
// SYSTEM TRAY
// ============================================================================

function createTray() {
  const settings = settingsManager.loadSettings();
  if (!settings.minimize_to_tray) return;
  
  const iconPath = resourcePath(path.join('images', 'favicon.ico'));
  if (!fs.existsSync(iconPath)) return;
  
  tray = new Tray(iconPath);
  
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Overlord',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    },
    {
      label: 'Quit',
      click: () => {
        app.quit();
      }
    }
  ]);
  
  tray.setToolTip('Overlord Render Manager');
  tray.setContextMenu(contextMenu);
  
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// ============================================================================
// HTML GENERATION
// ============================================================================

function generateHTML() {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Overlord ${getDisplayVersion()}</title>
  <style>
    ${generateCSS()}
  </style>
</head>
<body class="theme-${currentTheme}">
  ${generateBodyHTML()}
  <script>
    ${generateJavaScript()}
  </script>
</body>
</html>`;
}

function generateCSS() {
  return `
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 14px;
      overflow: hidden;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }
    
    .theme-light {
      --bg: #f0f0f0; --fg: #000; --entry-bg: #fff; --entry-fg: #000;
      --button-bg: #e1e1e1; --button-fg: #000; --border: #ccc;
      --select-bg: #0078d4; --select-fg: #fff;
    }
    
    .theme-dark {
      --bg: #2d2d30; --fg: #fff; --entry-bg: #3c3c3c; --entry-fg: #fff;
      --button-bg: #404040; --button-fg: #fff; --border: #555;
      --select-bg: #0078d4; --select-fg: #fff;
    }
    
    body { background: var(--bg); color: var(--fg); }
    
    .menu-bar {
      background: var(--bg);
      border-bottom: 1px solid var(--border);
      display: flex;
      padding: 0 8px;
      user-select: none;
    }
    
    .menu-item {
      padding: 6px 12px;
      cursor: pointer;
      position: relative;
    }
    
    .menu-item:hover { background: var(--button-bg); }
    
    .container {
      display: flex;
      flex: 1;
      overflow: hidden;
    }
    
    .left-panel, .right-panel {
      padding: 20px;
      overflow-y: auto;
    }
    
    .left-panel {
      flex: 1;
      border-right: 1px solid var(--border);
      min-width: 500px;
    }
    
    .right-panel {
      flex: 1;
      min-width: 400px;
    }
    
    h2 {
      margin-bottom: 16px;
      font-size: 18px;
    }
    
    .form-group {
      margin-bottom: 16px;
    }
    
    .form-group label {
      display: block;
      margin-bottom: 4px;
      font-weight: 500;
    }
    
    input[type="text"], input[type="number"], textarea {
      width: 100%;
      padding: 8px;
      background: var(--entry-bg);
      color: var(--entry-fg);
      border: 1px solid var(--border);
      border-radius: 4px;
      font-family: inherit;
      font-size: 13px;
    }
    
    textarea {
      resize: vertical;
      min-height: 60px;
      font-family: "Courier New", monospace;
    }
    
    .input-row {
      display: flex;
      gap: 8px;
    }
    
    .input-row input {
      flex: 1;
    }
    
    button {
      padding: 8px 16px;
      background: var(--button-bg);
      color: var(--button-fg);
      border: 1px solid var(--border);
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
    }
    
    button:hover { opacity: 0.9; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    
    .btn-primary {
      background: var(--select-bg);
      color: var(--select-fg);
    }
    
    .btn-danger {
      background: #dc3545;
      color: #fff;
    }
    
    .button-group {
      display: flex;
      gap: 12px;
      margin-top: 20px;
    }
    
    .button-group button {
      flex: 1;
      padding: 12px;
      font-weight: 600;
    }
    
    .progress-section {
      margin-top: 20px;
    }
    
    .progress-bar {
      width: 100%;
      height: 24px;
      background: var(--entry-bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      overflow: hidden;
      position: relative;
    }
    
    .progress-fill {
      height: 100%;
      background: var(--select-bg);
      transition: width 0.3s;
      width: 0%;
    }
    
    .progress-text {
      margin-top: 8px;
      text-align: center;
      font-size: 13px;
    }
    
    .image-preview {
      width: 100%;
      height: 400px;
      background: var(--entry-bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 16px;
      overflow: hidden;
    }
    
    .image-preview img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }
    
    .no-image {
      opacity: 0.5;
    }
    
    .info-box {
      background: var(--entry-bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 12px;
      margin-bottom: 12px;
    }
    
    .info-row {
      display: flex;
      justify-content: space-between;
      padding: 4px 0;
    }
    
    .info-label {
      font-weight: 500;
    }
    
    .footer {
      background: var(--bg);
      border-top: 1px solid var(--border);
      padding: 6px 12px;
      display: flex;
      justify-content: space-between;
      font-size: 12px;
    }
    
    ::-webkit-scrollbar { width: 12px; }
    ::-webkit-scrollbar-track { background: var(--entry-bg); }
    ::-webkit-scrollbar-thumb { background: var(--button-bg); border-radius: 6px; }
  `;
}

function generateBodyHTML() {
  return `
    <div class="menu-bar">
      <div class="menu-item" onclick="showFileMenu()">File</div>
      <div class="menu-item" onclick="showEditMenu()">Edit</div>
      <div class="menu-item" onclick="showHelpMenu()">Help</div>
    </div>
    
    <div class="container">
      <div class="left-panel">
        <h2>Options</h2>
        
        <div class="form-group">
          <label>Subject:</label>
          <div class="input-row">
            <input type="text" id="subject" placeholder="Path to subject .duf file">
            <button onclick="browseSubject()">Browse</button>
          </div>
        </div>
        
        <div class="form-group">
          <label>Animations:</label>
          <textarea id="animations" rows="3" placeholder="Paths to animation .duf files (one per line)"></textarea>
          <button onclick="browseAnimations()" style="margin-top: 4px;">Browse</button>
        </div>
        
        <div class="form-group">
          <label>Prop Animations:</label>
          <textarea id="prop-animations" rows="3" placeholder="Paths to prop animation .duf files (one per line)"></textarea>
          <button onclick="browsePropAnimations()" style="margin-top: 4px;">Browse</button>
        </div>
        
        <div class="form-group">
          <label>Gear:</label>
          <textarea id="gear" rows="3" placeholder="Paths to gear .duf files (one per line)"></textarea>
          <button onclick="browseGear()" style="margin-top: 4px;">Browse</button>
        </div>
        
        <div class="form-group">
          <label>Gear Animations:</label>
          <textarea id="gear-animations" rows="3" placeholder="Paths to gear animation .duf files (one per line)"></textarea>
          <button onclick="browseGearAnimations()" style="margin-top: 4px;">Browse</button>
        </div>
        
        <div class="form-group">
          <label>Output Directory:</label>
          <div class="input-row">
            <input type="text" id="output-dir" placeholder="Output directory for rendered images">
            <button onclick="browseOutputDir()">Browse</button>
          </div>
        </div>
        
        <div class="form-group">
          <div class="input-row">
            <div style="flex: 1;">
              <label>Instances:</label>
              <input type="number" id="instances" min="1" max="99" value="1">
            </div>
            <div style="flex: 1;">
              <label>Frame Rate:</label>
              <input type="number" id="frame-rate" min="1" max="999" value="30">
            </div>
          </div>
        </div>
        
        <div class="form-group">
          <label>Cache Threshold (GB):</label>
          <input type="number" id="cache-threshold" min="0.1" max="1000" step="0.1" value="10">
        </div>
        
        <div class="form-group">
          <label><input type="checkbox" id="render-shadows" checked> Render Shadows</label>
        </div>
        
        <div class="form-group">
          <label><input type="checkbox" id="shutdown-on-finish" checked> Shutdown PC on Finish</label>
        </div>
        
        <div class="button-group">
          <button id="start-btn" class="btn-primary" onclick="startRender()">Start Render</button>
          <button id="stop-btn" class="btn-danger" onclick="stopRender()" disabled>Stop Render</button>
        </div>
        
        <div class="progress-section">
          <div class="progress-bar">
            <div class="progress-fill" id="progress-fill"></div>
          </div>
          <div class="progress-text" id="progress-text">Ready to render</div>
        </div>
      </div>
      
      <div class="right-panel">
        <h2>Last Rendered Image</h2>
        
        <div class="image-preview" id="image-preview">
          <div class="no-image">No image rendered yet</div>
        </div>
        
        <div class="info-box">
          <div class="info-row">
            <span class="info-label">File:</span>
            <span id="info-file">-</span>
          </div>
          <div class="info-row">
            <span class="info-label">Size:</span>
            <span id="info-size">-</span>
          </div>
          <div class="info-row">
            <span class="info-label">Modified:</span>
            <span id="info-modified">-</span>
          </div>
        </div>
        
        <button onclick="copyPath()" id="copy-btn" disabled>Copy Path</button>
        
        <h2 style="margin-top: 24px;">Output Details</h2>
        
        <div class="info-box">
          <div class="info-row">
            <span class="info-label">Total Images:</span>
            <span id="total-images">0</span>
          </div>
          <div class="info-row">
            <span class="info-label">Rendered:</span>
            <span id="rendered-count">0</span>
          </div>
          <div class="info-row">
            <span class="info-label">Est. Time:</span>
            <span id="est-time">-</span>
          </div>
        </div>
      </div>
    </div>
    
    <div class="footer">
      <span>Overlord v${getDisplayVersion()}</span>
      <span id="status">Ready</span>
    </div>
  `;
}

function generateJavaScript() {
  return `
    const { ipcRenderer } = require('electron');
    const { dialog } = require('electron').remote || require('@electron/remote');
    
    let currentImagePath = null;
    let currentSettings = {};
    
    // Load settings on start
    loadSettings();
    
    async function loadSettings() {
      const settings = await ipcRenderer.invoke('load-settings');
      applySettings(settings);
    }
    
    function applySettings(settings) {
      currentSettings = settings;
      document.getElementById('subject').value = settings.subject || '';
      document.getElementById('animations').value = (settings.animations || []).join('\\n');
      document.getElementById('prop-animations').value = (settings.prop_animations || []).join('\\n');
      document.getElementById('gear').value = (settings.gear || []).join('\\n');
      document.getElementById('gear-animations').value = (settings.gear_animations || []).join('\\n');
      document.getElementById('output-dir').value = settings.output_directory || '';
      document.getElementById('instances').value = settings.number_of_instances || '1';
      document.getElementById('frame-rate').value = settings.frame_rate || '30';
      document.getElementById('cache-threshold').value = settings.cache_db_size_threshold_gb || '10';
      document.getElementById('render-shadows').checked = settings.render_shadows !== false;
      document.getElementById('shutdown-on-finish').checked = settings.shutdown_on_finish !== false;
    }
    
    function getSettings() {
      return {
        subject: document.getElementById('subject').value,
        animations: document.getElementById('animations').value.split('\\n').filter(s => s.trim()),
        prop_animations: document.getElementById('prop-animations').value.split('\\n').filter(s => s.trim()),
        gear: document.getElementById('gear').value.split('\\n').filter(s => s.trim()),
        gear_animations: document.getElementById('gear-animations').value.split('\\n').filter(s => s.trim()),
        output_directory: document.getElementById('output-dir').value,
        number_of_instances: document.getElementById('instances').value,
        frame_rate: document.getElementById('frame-rate').value,
        cache_db_size_threshold_gb: document.getElementById('cache-threshold').value,
        render_shadows: document.getElementById('render-shadows').checked,
        shutdown_on_finish: document.getElementById('shutdown-on-finish').checked,
        hide_daz_instances: currentSettings.hide_daz_instances !== false,
        minimize_to_tray: currentSettings.minimize_to_tray !== false,
        start_on_startup: currentSettings.start_on_startup !== false,
        last_directories: currentSettings.last_directories || {}
      };
    }
    
    async function saveSettings() {
      const settings = getSettings();
      await ipcRenderer.invoke('save-settings', settings);
    }
    
    // Auto-save debounced
    let saveTimeout;
    function autoSave() {
      clearTimeout(saveTimeout);
      saveTimeout = setTimeout(saveSettings, 500);
    }
    
    document.querySelectorAll('input, textarea').forEach(el => {
      el.addEventListener('change', autoSave);
      el.addEventListener('blur', autoSave);
    });
    
    async function browseSubject() {
      const result = await ipcRenderer.invoke('browse-file', { filters: [{ name: 'DAZ Files', extensions: ['duf'] }] });
      if (result) {
        document.getElementById('subject').value = result;
        autoSave();
      }
    }
    
    async function browseAnimations() {
      const result = await ipcRenderer.invoke('browse-files', { filters: [{ name: 'DAZ Files', extensions: ['duf'] }] });
      if (result && result.length) {
        document.getElementById('animations').value = result.join('\\n');
        autoSave();
      }
    }
    
    async function browsePropAnimations() {
      const result = await ipcRenderer.invoke('browse-files', { filters: [{ name: 'DAZ Files', extensions: ['duf'] }] });
      if (result && result.length) {
        document.getElementById('prop-animations').value = result.join('\\n');
        autoSave();
      }
    }
    
    async function browseGear() {
      const result = await ipcRenderer.invoke('browse-files', { filters: [{ name: 'DAZ Files', extensions: ['duf'] }] });
      if (result && result.length) {
        document.getElementById('gear').value = result.join('\\n');
        autoSave();
      }
    }
    
    async function browseGearAnimations() {
      const result = await ipcRenderer.invoke('browse-files', { filters: [{ name: 'DAZ Files', extensions: ['duf'] }] });
      if (result && result.length) {
        document.getElementById('gear-animations').value = result.join('\\n');
        autoSave();
      }
    }
    
    async function browseOutputDir() {
      const result = await ipcRenderer.invoke('browse-directory');
      if (result) {
        document.getElementById('output-dir').value = result;
        autoSave();
      }
    }
    
    async function startRender() {
      const settings = getSettings();
      
      if (!settings.subject) {
        alert('Please select a subject file');
        return;
      }
      if (!settings.animations.length) {
        alert('Please select at least one animation');
        return;
      }
      if (!settings.output_directory) {
        alert('Please select an output directory');
        return;
      }
      
      document.getElementById('start-btn').disabled = true;
      document.getElementById('stop-btn').disabled = false;
      document.getElementById('status').textContent = 'Rendering...';
      document.getElementById('progress-text').textContent = 'Starting render...';
      
      const result = await ipcRenderer.invoke('start-render', settings);
      
      if (!result.success) {
        alert('Failed to start render: ' + result.message);
        document.getElementById('start-btn').disabled = false;
        document.getElementById('stop-btn').disabled = true;
        document.getElementById('status').textContent = 'Ready';
      }
    }
    
    async function stopRender() {
      document.getElementById('stop-btn').disabled = true;
      document.getElementById('status').textContent = 'Stopping...';
      
      await ipcRenderer.invoke('stop-render');
      
      document.getElementById('start-btn').disabled = false;
      document.getElementById('stop-btn').disabled = true;
      document.getElementById('status').textContent = 'Ready';
      document.getElementById('progress-text').textContent = 'Render stopped';
    }
    
    function copyPath() {
      if (currentImagePath) {
        ipcRenderer.invoke('copy-to-clipboard', currentImagePath);
      }
    }
    
    function showFileMenu() {
      alert('File menu - implement dropdown');
    }
    
    function showEditMenu() {
      alert('Edit menu - implement dropdown');
    }
    
    function showHelpMenu() {
      alert('Help menu - implement dropdown');
    }
    
    function autoStartRender() {
      startRender();
    }
    
    // Listen for image updates
    ipcRenderer.on('image-updated', (event, imageData) => {
      currentImagePath = imageData.path;
      
      const preview = document.getElementById('image-preview');
      preview.innerHTML = '<img src="file://' + imageData.path + '" alt="Rendered">';
      
      document.getElementById('info-file').textContent = imageData.filename || '-';
      document.getElementById('info-size').textContent = formatSize(imageData.size) || '-';
      document.getElementById('info-modified').textContent = imageData.modified ? 
        new Date(imageData.modified).toLocaleString() : '-';
      
      document.getElementById('copy-btn').disabled = false;
    });
    
    function formatSize(bytes) {
      if (!bytes) return '0 KB';
      if (bytes < 1024 * 1024) {
        return (bytes / 1024).toFixed(1) + ' KB';
      } else if (bytes < 1024 * 1024 * 1024) {
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
      } else {
        return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
      }
    }
  `;
}

// ============================================================================
// IPC HANDLERS
// ============================================================================

ipcMain.handle('load-settings', () => {
  return settingsManager.loadSettings();
});

ipcMain.handle('save-settings', (event, settings) => {
  return settingsManager.saveSettings(settings);
});

ipcMain.handle('browse-file', async (event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: options.filters || []
  });
  return result.filePaths[0];
});

ipcMain.handle('browse-files', async (event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile', 'multiSelections'],
    filters: options.filters || []
  });
  return result.filePaths;
});

ipcMain.handle('browse-directory', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  return result.filePaths[0];
});

ipcMain.handle('start-render', async (event, settings) => {
  try {
    return await startRender(settings);
  } catch (error) {
    console.error('Render error:', error);
    return { success: false, message: error.message };
  }
});

ipcMain.handle('stop-render', async () => {
  return await stopRender();
});

ipcMain.handle('get-render-status', () => {
  return getRenderStatus();
});

ipcMain.handle('copy-to-clipboard', (event, text) => {
  clipboard.writeText(text);
});

// ============================================================================
// APP LIFECYCLE
// ============================================================================

app.whenReady().then(() => {
  setupLogger();
  createWindow();
  createTray();
  
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopFileMonitoring();
  if (tray) {
    tray.destroy();
  }
});

// Theme change listener
nativeTheme.on('updated', () => {
  currentTheme = detectWindowsTheme();
  if (mainWindow) {
    const htmlContent = generateHTML();
    mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(htmlContent)}`);
  }
});

console.log('Overlord Electron application initialized');
