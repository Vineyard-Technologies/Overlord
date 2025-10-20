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
let splashWindow = null;
let splashStartTime = null;
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

function calculateTotalImages(subjectFilepath, animationFilepaths, gearFilepaths = null, renderShadows = true) {
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
  
  // Double the count if render shadows is enabled (renders both with and without shadows)
  if (renderShadows) {
    totalImages *= 2;
    console.log(`Render shadows enabled - doubling image count to: ${totalImages}`);
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

function calculateAverageRenderTime(directory, maxFiles = 10) {
  /**
   * Calculate average time between file creations based on the most recent files.
   * Returns average interval in seconds, or null if not enough data.
   */
  try {
    if (!directory || !fs.existsSync(directory)) {
      return null;
    }
    
    // Get all image files with their modification times
    const filesWithTimes = [];
    
    function walkDir(dir) {
      try {
        const files = fs.readdirSync(dir);
        
        for (const file of files) {
          const filePath = path.join(dir, file);
          const stat = fs.statSync(filePath);
          
          if (stat.isDirectory()) {
            walkDir(filePath);
          } else if (IMAGE_EXTENSIONS.some(ext => file.toLowerCase().endsWith(ext))) {
            const mtime = stat.mtime.getTime() / 1000; // Convert to seconds
            
            // Only include files modified after render started
            if (renderStartTime && mtime < renderStartTime / 1000) {
              continue;
            }
            
            filesWithTimes.push({ path: filePath, mtime: mtime });
          }
        }
      } catch (error) {
        // Ignore errors for inaccessible directories
      }
    }
    
    walkDir(directory);
    
    if (filesWithTimes.length < 2) {
      return null; // Need at least 2 files to calculate intervals
    }
    
    // Sort by modification time (newest first)
    filesWithTimes.sort((a, b) => b.mtime - a.mtime);
    
    // Take the most recent files (up to maxFiles)
    const recentFiles = filesWithTimes.slice(0, maxFiles);
    
    if (recentFiles.length < 2) {
      return null;
    }
    
    // Calculate time intervals between consecutive files
    const intervals = [];
    for (let i = 0; i < recentFiles.length - 1; i++) {
      const newerTime = recentFiles[i].mtime;
      const olderTime = recentFiles[i + 1].mtime;
      const interval = newerTime - olderTime;
      if (interval > 0) { // Only include positive intervals
        intervals.push(interval);
      }
    }
    
    if (intervals.length === 0) {
      return null;
    }
    
    // Return average interval in seconds
    return intervals.reduce((a, b) => a + b, 0) / intervals.length;
    
  } catch (error) {
    console.error('Error calculating average render time:', error);
    return null;
  }
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
    settings.gear,
    settings.render_shadows
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

function countImagesInDirectory(directory) {
  let count = 0;
  
  function walkDir(dir) {
    try {
      const files = fs.readdirSync(dir);
      
      for (const file of files) {
        const filePath = path.join(dir, file);
        try {
          const stat = fs.statSync(filePath);
          
          if (stat.isDirectory()) {
            walkDir(filePath);
          } else if (IMAGE_EXTENSIONS.some(ext => file.toLowerCase().endsWith(ext))) {
            count++;
          }
        } catch (error) {
          // Ignore inaccessible files
        }
      }
    } catch (error) {
      // Ignore inaccessible directories
    }
  }
  
  walkDir(directory);
  return count;
}

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
    
    // Count total images and send progress update
    if (isRendering && mainWindow) {
      const renderedCount = countImagesInDirectory(directory);
      const remaining = Math.max(0, initialTotalImages - renderedCount);
      const progressPercent = initialTotalImages > 0 ? (renderedCount / initialTotalImages) * 100 : 0;
      
      // Calculate estimated completion time
      let estimatedCompletion = '-';
      if (remaining > 0) {
        const avgRenderTime = calculateAverageRenderTime(directory);
        if (avgRenderTime && avgRenderTime > 0) {
          const totalSecondsRemaining = remaining * avgRenderTime;
          const completionTime = new Date(Date.now() + (totalSecondsRemaining * 1000));
          
          // Format as "3:14 PM, February 15th, 2025"
          const timeStr = completionTime.toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit',
            hour12: true 
          });
          
          const day = completionTime.getDate();
          const daySuffix = ['th', 'st', 'nd', 'rd'][(day % 10 > 3 || Math.floor(day / 10) === 1) ? 0 : day % 10];
          
          const monthStr = completionTime.toLocaleDateString('en-US', { month: 'long' });
          const yearStr = completionTime.getFullYear();
          
          estimatedCompletion = `${timeStr}, ${monthStr} ${day}${daySuffix}, ${yearStr}`;
        } else {
          estimatedCompletion = 'Calculating...';
        }
      } else {
        estimatedCompletion = 'Complete';
      }
      
      mainWindow.webContents.send('render-progress', {
        totalImages: initialTotalImages,
        renderedCount: renderedCount,
        remaining: remaining,
        progressPercent: progressPercent,
        estimatedCompletion: estimatedCompletion
      });
    }
  }, 2000);
}

function stopFileMonitoring() {
  if (fileWatcherHandle) {
    clearInterval(fileWatcherHandle);
    fileWatcherHandle = null;
  }
}

function startContinuousImageMonitoring(outputDirectory) {
  if (!outputDirectory || !fs.existsSync(outputDirectory)) {
    return;
  }
  
  // Monitor for newest image every 5 seconds
  const checkForNewestImage = () => {
    const images = findNewestImage(outputDirectory);
    
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
  };
  
  // Check immediately
  checkForNewestImage();
  
  // Then check every 5 seconds
  if (periodicMonitoringHandle) {
    clearInterval(periodicMonitoringHandle);
  }
  periodicMonitoringHandle = setInterval(checkForNewestImage, 5000);
}

function stopContinuousImageMonitoring() {
  if (periodicMonitoringHandle) {
    clearInterval(periodicMonitoringHandle);
    periodicMonitoringHandle = null;
  }
}

// ============================================================================
// SINGLE INSTANCE CHECK
// ============================================================================

const singleInstanceLock = app.requestSingleInstanceLock();

if (!singleInstanceLock) {
  console.log('Another instance of Overlord is already running. Exiting...');
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

function createSplashScreen() {
  currentTheme = detectWindowsTheme();
  const bgColor = THEME_COLORS[currentTheme].bg;
  
  splashWindow = new BrowserWindow({
    width: SPLASH_WIDTH,
    height: SPLASH_HEIGHT,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });
  
  // Check if splash image exists
  const splashImagePath = resourcePath(path.join('images', 'splashScreen.webp'));
  const hasSplashImage = fs.existsSync(splashImagePath);
  
  let splashHTML;
  if (hasSplashImage) {
    // Use image splash - no text, no border
    const imageData = fs.readFileSync(splashImagePath);
    const base64Image = imageData.toString('base64');
    splashHTML = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <style>
          * { margin: 0; padding: 0; }
          body {
            width: 100vw;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: transparent;
            overflow: hidden;
          }
          .splash-image {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
          }
        </style>
      </head>
      <body>
        <img src="data:image/png;base64,${base64Image}" class="splash-image" alt="Overlord">
      </body>
      </html>
    `;
  } else {
    // Fallback to text splash
    splashHTML = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <style>
          * { margin: 0; padding: 0; }
          body {
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: #2c2c2c;
            color: white;
            font-family: Arial, sans-serif;
          }
          .title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
          }
          .subtitle {
            font-size: 16px;
            margin-bottom: 20px;
          }
          .status {
            font-size: 12px;
            margin-top: 20px;
            opacity: 0.8;
          }
        </style>
      </head>
      <body>
        <div class="title">Overlord ${getDisplayVersion()}</div>
        <div class="subtitle">Render Pipeline Manager</div>
        <div class="status">Starting up...</div>
      </body>
      </html>
    `;
  }
  
  splashWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(splashHTML)}`);
  splashWindow.center();
  splashWindow.once('ready-to-show', () => {
    splashWindow.show();
    splashStartTime = Date.now(); // Track when splash was shown
  });
}

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
    // Ensure splash screen is shown for at least 1 second
    const minSplashTime = 1000; // 1 second
    const elapsed = splashStartTime ? Date.now() - splashStartTime : 0;
    const remainingTime = Math.max(0, minSplashTime - elapsed);
    
    setTimeout(() => {
      // Close splash screen
      if (splashWindow) {
        splashWindow.close();
        splashWindow = null;
      }
      
      mainWindow.show();
      mainWindow.maximize();
      
      // Start continuous image monitoring with current output directory
      const settings = settingsManager.loadSettings();
      if (settings.output_directory) {
        startContinuousImageMonitoring(settings.output_directory);
      }
      
      // Check for auto-start
      const autoStart = process.argv.includes('--startRender');
      if (autoStart) {
        mainWindow.webContents.executeJavaScript('if (window.autoStartRender) window.autoStartRender();');
      }
    }, remainingTime);
  });
  
  mainWindow.on('minimize', () => {
    const settings = settingsManager.loadSettings();
    if (settings.minimize_to_tray && tray) {
      mainWindow.hide();
    }
  });
  
  mainWindow.on('close', () => {
    stopFileMonitoring();
    stopContinuousImageMonitoring();
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
    
    .dropdown-menu {
      position: absolute;
      top: 100%;
      left: 0;
      background: var(--entry-bg);
      border: 1px solid var(--border);
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
      min-width: 220px;
      z-index: 1000;
      display: none;
    }
    
    .dropdown-menu.show {
      display: block;
    }
    
    .dropdown-item {
      padding: 8px 16px;
      cursor: pointer;
      white-space: nowrap;
    }
    
    .dropdown-item:hover {
      background: var(--button-bg);
    }
    
    .dropdown-separator {
      height: 1px;
      background: var(--border);
      margin: 4px 0;
    }
    
    .container {
      display: flex;
      flex: 1;
      overflow: hidden;
    }
    
    .left-panel, .right-panel {
      padding: 20px;
    }
    
    .left-panel {
      flex: 1;
      border-right: 1px solid var(--border);
      min-width: 500px;
    }
    
    .right-panel {
      flex: 1;
      min-width: 400px;
      display: flex;
      flex-direction: column;
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
      font-family: "Consolas", "Courier New", monospace;
      font-size: 13px;
    }
    
    textarea {
      resize: vertical;
      min-height: 60px;
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
    
    .image-preview {
      width: 100%;
      aspect-ratio: 1 / 1;
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
    
    ::-webkit-scrollbar { width: 12px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 6px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--button-bg); }
    
    /* Settings Modal */
    #settings-modal {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.6);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
    }
    
    .settings-content {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      width: 450px;
      max-width: 90%;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    }
    
    .settings-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 20px;
      border-bottom: 1px solid var(--border);
    }
    
    .settings-header h2 {
      margin: 0;
      font-size: 18px;
    }
    
    .close-btn {
      background: none;
      border: none;
      color: var(--fg);
      font-size: 24px;
      cursor: pointer;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 4px;
    }
    
    .close-btn:hover {
      background: var(--button-bg);
    }
    
    .settings-body {
      padding: 20px;
    }
    
    .setting-item {
      margin-bottom: 16px;
    }
    
    .setting-item label {
      display: flex;
      align-items: center;
      cursor: pointer;
      user-select: none;
    }
    
    .setting-item input[type="checkbox"] {
      margin-right: 10px;
      width: 18px;
      height: 18px;
      cursor: pointer;
    }
    
    /* About Modal */
    #about-modal {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.6);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
    }
    
    .about-content {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      width: 650px;
      max-width: 90%;
      max-height: 90vh;
      overflow-y: auto;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    }
    
    .about-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 20px;
      border-bottom: 1px solid var(--border);
    }
    
    .about-header h2 {
      margin: 0;
      font-size: 18px;
    }
    
    .about-body {
      padding: 20px;
    }
    
    .about-logo {
      text-align: center;
      margin-bottom: 10px;
    }
    
    .about-body a {
      color: #0078d4;
      text-decoration: none;
    }
    
    .about-body a:hover {
      text-decoration: underline;
    }
  `;
}

function generateBodyHTML() {
  return `
    <div class="menu-bar">
      <div class="menu-item" onclick="toggleMenu('file-menu')">
        File
        <div id="file-menu" class="dropdown-menu">
          <div class="dropdown-item" onclick="event.stopPropagation(); browseSubject(); closeAllMenus();">Choose Subject</div>
          <div class="dropdown-item" onclick="event.stopPropagation(); browseAnimations(); closeAllMenus();">Choose Animations</div>
          <div class="dropdown-item" onclick="event.stopPropagation(); browsePropAnimations(); closeAllMenus();">Choose Prop Animations</div>
          <div class="dropdown-item" onclick="event.stopPropagation(); browseGear(); closeAllMenus();">Choose Gear</div>
          <div class="dropdown-item" onclick="event.stopPropagation(); browseGearAnimations(); closeAllMenus();">Choose Gear Animations</div>
          <div class="dropdown-item" onclick="event.stopPropagation(); browseOutputDir(); closeAllMenus();">Choose Output Directory</div>
          <div class="dropdown-separator"></div>
          <div class="dropdown-item" onclick="event.stopPropagation(); showSettings(); closeAllMenus();">Settings</div>
          <div class="dropdown-separator"></div>
          <div class="dropdown-item" onclick="event.stopPropagation(); exitOverlord(); closeAllMenus();">Exit Overlord</div>
        </div>
      </div>
      <div class="menu-item" onclick="toggleMenu('edit-menu')">
        Edit
        <div id="edit-menu" class="dropdown-menu">
          <div class="dropdown-item" onclick="event.stopPropagation(); clearAllFields(); closeAllMenus();">Clear All Input Fields</div>
          <div class="dropdown-item" onclick="event.stopPropagation(); restoreDefaults(); closeAllMenus();">Restore Default Settings</div>
        </div>
      </div>
      <div class="menu-item" onclick="toggleMenu('help-menu')">
        Help
        <div id="help-menu" class="dropdown-menu">
          <div class="dropdown-item" onclick="event.stopPropagation(); showOverlordLog(); closeAllMenus();">Show Overlord Log</div>
          <div class="dropdown-item" onclick="event.stopPropagation(); showIrayServerLog(); closeAllMenus();">Show Iray Server Log</div>
          <div class="dropdown-item" onclick="event.stopPropagation(); showDazStudioLog(); closeAllMenus();">Show DAZ Studio Log</div>
          <div class="dropdown-separator"></div>
          <div class="dropdown-item" onclick="event.stopPropagation(); showAbout(); closeAllMenus();">About Overlord</div>
        </div>
      </div>
    </div>
    
    <div class="container">
      <div class="left-panel">
        <h2>Options</h2>
        
        <div class="form-group">
          <label>Subject:</label>
          <div class="input-row">
            <input type="text" id="subject" placeholder="Path to subject .duf file" spellcheck="false">
            <button onclick="browseSubject()">Browse</button>
          </div>
        </div>
        
        <div class="form-group">
          <label>Animations:</label>
          <div class="input-row">
            <textarea id="animations" rows="3" placeholder="Paths to animation .duf files (one per line)" spellcheck="false"></textarea>
            <button onclick="browseAnimations()">Browse</button>
          </div>
        </div>
        
        <div class="form-group">
          <label>Prop Animations:</label>
          <div class="input-row">
            <textarea id="prop-animations" rows="3" placeholder="Paths to prop animation .duf files (one per line)" spellcheck="false"></textarea>
            <button onclick="browsePropAnimations()">Browse</button>
          </div>
        </div>
        
        <div class="form-group">
          <label>Gear:</label>
          <div class="input-row">
            <textarea id="gear" rows="3" placeholder="Paths to gear .duf files (one per line)" spellcheck="false"></textarea>
            <button onclick="browseGear()">Browse</button>
          </div>
        </div>
        
        <div class="form-group">
          <label>Gear Animations:</label>
          <div class="input-row">
            <textarea id="gear-animations" rows="3" placeholder="Paths to gear animation .duf files (one per line)" spellcheck="false"></textarea>
            <button onclick="browseGearAnimations()">Browse</button>
          </div>
        </div>
        
        <div class="form-group">
          <label>Output Directory:</label>
          <div class="input-row">
            <input type="text" id="output-dir" placeholder="Output directory for rendered images" spellcheck="false">
            <button onclick="browseOutputDir()">Browse</button>
          </div>
        </div>
        
        <div class="form-group">
          <div class="input-row" style="align-items: flex-end; gap: 16px;">
            <div style="flex: 0 0 auto;">
              <label>Instances:</label>
              <input type="number" id="instances" min="1" max="99" value="1" style="width: 60px;">
            </div>
            <div style="flex: 0 0 auto;">
              <label>Frame Rate:</label>
              <input type="number" id="frame-rate" min="1" max="999" value="30" style="width: 70px;">
            </div>
            <div style="flex: 0 0 auto;">
              <label>Cache (GB):</label>
              <input type="number" id="cache-threshold" min="0.1" max="1000" step="0.1" value="10" style="width: 70px;">
            </div>
            <div style="flex: 0 0 auto;">
              <label style="display: flex; align-items: center; margin-bottom: 0;"><input type="checkbox" id="render-shadows" checked style="margin-right: 4px;"> Render Shadows</label>
            </div>
            <div style="flex: 0 0 auto;">
              <label style="display: flex; align-items: center; margin-bottom: 0;"><input type="checkbox" id="shutdown-on-finish" checked style="margin-right: 4px;"> Shutdown on Finish</label>
            </div>
          </div>
        </div>
        
        <div class="button-group">
          <button id="start-btn" class="btn-primary" onclick="startRender()">Start Render</button>
          <button id="stop-btn" class="btn-danger" onclick="stopRender()">Stop Render</button>
        </div>
        
        <div class="progress-section">
          <div class="progress-bar">
            <div class="progress-fill" id="progress-fill"></div>
          </div>
        </div>
        
        <div style="display: flex; gap: 16px; margin-top: 24px;">
          <div style="flex: 1;">
            <h3 style="margin-bottom: 12px;">Output Details</h3>
            <div class="info-box">
              <div class="info-row">
                <span class="info-label">Images Completed:</span>
                <span id="total-images">-</span>
              </div>
              <div class="info-row">
                <span class="info-label">Images Remaining:</span>
                <span id="images-remaining">-</span>
              </div>
              <div class="info-row">
                <span class="info-label">Estimated Completion at:</span>
                <span id="est-completion">-</span>
              </div>
            </div>
          </div>
          
          <div style="flex: 1;">
            <h3 style="margin-bottom: 12px;">Last Rendered Image Details</h3>
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
          </div>
        </div>
      </div>
      
      <div class="right-panel">
        <h2>Last Rendered Image</h2>
        
        <div class="image-preview" id="image-preview">
          <div class="no-image">No image rendered yet</div>
        </div>
      </div>
    </div>
  `;
}

function generateJavaScript() {
  return `
    const { ipcRenderer } = require('electron');
    
    let currentImagePath = null;
    let currentSettings = {};
    
    async function loadSettings() {
      try {
        console.log('Loading settings...');
        const settings = await ipcRenderer.invoke('load-settings');
        console.log('Settings loaded:', settings);
        applySettings(settings);
      } catch (error) {
        console.error('Error loading settings:', error);
      }
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
      console.log('Settings applied to UI');
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
      try {
        const settings = getSettings();
        console.log('Saving settings:', settings);
        await ipcRenderer.invoke('save-settings', settings);
        console.log('Settings saved successfully');
      } catch (error) {
        console.error('Error saving settings:', error);
      }
    }
    
    // Auto-save debounced
    let saveTimeout;
    function autoSave() {
      clearTimeout(saveTimeout);
      saveTimeout = setTimeout(saveSettings, 500);
    }
    
    // Initialize when DOM is ready
    window.addEventListener('DOMContentLoaded', () => {
      console.log('DOM loaded, initializing...');
      
      // Load saved settings
      loadSettings();
      
      // Attach auto-save event listeners
      document.querySelectorAll('input, textarea').forEach(el => {
        el.addEventListener('change', autoSave);
        el.addEventListener('input', autoSave);
        el.addEventListener('blur', autoSave);
      });
      
      console.log('Event listeners attached');
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
      
      const result = await ipcRenderer.invoke('start-render', settings);
      
      if (!result.success) {
        alert('Failed to start render: ' + result.message);
        document.getElementById('start-btn').disabled = false;
      }
    }
    
    async function stopRender() {
      await ipcRenderer.invoke('stop-render');
      
      document.getElementById('start-btn').disabled = false;
      
      // Reset progress bar
      document.getElementById('progress-fill').style.width = '0%';
      
      // Clear output details
      document.getElementById('total-images').textContent = '-';
      document.getElementById('images-remaining').textContent = '-';
      document.getElementById('est-completion').textContent = '-';
    }
    
    function copyPath() {
      if (currentImagePath) {
        ipcRenderer.invoke('copy-to-clipboard', currentImagePath);
      }
    }
    
    function toggleMenu(menuId) {
      const menu = document.getElementById(menuId);
      const isOpen = menu.classList.contains('show');
      
      // Close all menus first
      closeAllMenus();
      
      // Toggle this menu
      if (!isOpen) {
        menu.classList.add('show');
      }
    }
    
    function closeAllMenus() {
      document.querySelectorAll('.dropdown-menu').forEach(menu => {
        menu.classList.remove('show');
      });
    }
    
    // Close menus when clicking outside
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.menu-item')) {
        closeAllMenus();
      }
    });
    
    function clearAllFields() {
      document.getElementById('subject').value = '';
      document.getElementById('animations').value = '';
      document.getElementById('prop-animations').value = '';
      document.getElementById('gear').value = '';
      document.getElementById('gear-animations').value = '';
      document.getElementById('output-dir').value = '';
      autoSave();
    }
    
    function restoreDefaults() {
      document.getElementById('instances').value = '1';
      document.getElementById('frame-rate').value = '30';
      document.getElementById('cache-threshold').value = '10';
      document.getElementById('render-shadows').checked = true;
      document.getElementById('shutdown-on-finish').checked = true;
      autoSave();
    }
    
    async function showSettings() {
      // Create modal overlay
      const modal = document.createElement('div');
      modal.id = 'settings-modal';
      modal.innerHTML = \`
        <div class="settings-content" onclick="event.stopPropagation()">
          <div class="settings-header">
            <h2>Overlord Settings</h2>
            <button class="close-btn" onclick="closeSettings()">&times;</button>
          </div>
          <div class="settings-body">
            <div class="setting-item">
              <label>
                <input type="checkbox" id="minimize-to-tray" onchange="onSettingChange('minimize_to_tray', this.checked)">
                Minimize Overlord to system tray
              </label>
            </div>
            <div class="setting-item">
              <label>
                <input type="checkbox" id="start-on-startup" onchange="onSettingChange('start_on_startup', this.checked)">
                Start Overlord on Windows startup
              </label>
            </div>
            <div class="setting-item">
              <label>
                <input type="checkbox" id="hide-daz-instances" onchange="onSettingChange('hide_daz_instances', this.checked)">
                Hide Daz Studio Instance(s) when rendering
              </label>
            </div>
          </div>
        </div>
      \`;
      document.body.appendChild(modal);
      
      // Close modal when clicking outside the content
      modal.addEventListener('click', closeSettings);
      
      // Load current settings
      const settings = await window.ipcRenderer.invoke('load-settings');
      document.getElementById('minimize-to-tray').checked = settings.minimize_to_tray || false;
      document.getElementById('start-on-startup').checked = settings.start_on_startup || false;
      document.getElementById('hide-daz-instances').checked = settings.hide_daz_instances || false;
    }
    
    function closeSettings() {
      const modal = document.getElementById('settings-modal');
      if (modal) {
        modal.remove();
      }
    }
    
    async function onSettingChange(key, value) {
      // Save setting immediately
      const settings = await window.ipcRenderer.invoke('load-settings');
      settings[key] = value;
      window.ipcRenderer.send('save-settings', settings);
      
      // If it's the startup setting, also update Windows registry
      if (key === 'start_on_startup') {
        await window.ipcRenderer.invoke('manage-windows-startup', value);
      }
    }
    
    async function exitOverlord() {
      const { remote } = require('@electron/remote') || require('electron');
      if (remote) {
        remote.app.quit();
      } else {
        window.close();
      }
    }
    
    async function showOverlordLog() {
      const { shell } = require('electron');
      const path = require('path');
      const os = require('os');
      
      const appData = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
      const logPath = path.join(appData, 'Overlord', 'log.txt');
      
      shell.openPath(logPath);
    }
    
    async function showIrayServerLog() {
      const { shell } = require('electron');
      const path = require('path');
      const os = require('os');
      const fs = require('fs');
      
      const appData = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
      
      // Look for iray_server.log in multiple locations
      const possiblePaths = [
        path.join(appData, 'Overlord', 'iray_server.log'),
        path.join(process.cwd(), 'iray_server.log')
      ];
      
      let logPath = null;
      for (const p of possiblePaths) {
        if (fs.existsSync(p)) {
          logPath = p;
          break;
        }
      }
      
      if (logPath) {
        shell.openPath(logPath);
      } else {
        alert('Iray Server log file not found. The server may not have been started yet.');
      }
    }
    
    async function showDazStudioLog() {
      const { shell } = require('electron');
      const path = require('path');
      const os = require('os');
      const fs = require('fs');
      
      const appData = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
      const logPath = path.join(appData, 'DAZ 3D', 'Studio4 [1]', 'log.txt');
      
      if (fs.existsSync(logPath)) {
        shell.openPath(logPath);
      } else {
        alert('DAZ Studio log file not found. DAZ Studio may not have been run yet.');
      }
    }
    
    async function showAbout() {
      const version = await ipcRenderer.invoke('get-version');
      const fs = require('fs');
      const path = require('path');
      
      // Load images as base64
      let overlordLogoBase64 = '';
      let vineyardLogoBase64 = '';
      
      try {
        const overlordLogoPath = path.join(process.cwd(), 'images', 'overlordLogo.webp');
        const overlordLogoBuffer = fs.readFileSync(overlordLogoPath);
        overlordLogoBase64 = 'data:image/webp;base64,' + overlordLogoBuffer.toString('base64');
      } catch (error) {
        console.error('Failed to load Overlord logo:', error);
      }
      
      try {
        const vineyardLogoPath = path.join(process.cwd(), 'images', 'VineyardTechnologiesLogo.webp');
        const vineyardLogoBuffer = fs.readFileSync(vineyardLogoPath);
        vineyardLogoBase64 = 'data:image/webp;base64,' + vineyardLogoBuffer.toString('base64');
      } catch (error) {
        console.error('Failed to load Vineyard Technologies logo:', error);
      }
      
      // Create modal overlay
      const modal = document.createElement('div');
      modal.id = 'about-modal';
      modal.innerHTML = \`
        <div class="about-content" onclick="event.stopPropagation()">
          <div class="about-header">
            <h2>About Overlord</h2>
            <button class="close-btn" onclick="closeAbout()">&times;</button>
          </div>
          <div class="about-body">
            <div class="about-logo">
              <img src="\${overlordLogoBase64}" alt="Overlord Logo" style="max-width: 100%; height: auto; cursor: pointer;" onclick="openUrl('https://github.com/Vineyard-Technologies/Overlord')">
            </div>
            <p style="text-align: center; margin: 10px 0;">
              <a href="#" onclick="openUrl('https://github.com/Vineyard-Technologies/Overlord'); return false;">https://github.com/Vineyard-Technologies/Overlord</a>
            </p>
            <p style="text-align: center; font-size: 16px; font-weight: bold; margin: 20px 0;">Version \${version}</p>
            
            <h3 style="margin: 20px 0 10px 0; font-size: 14px; font-weight: bold;">Latest Release Notes:</h3>
            <div id="patch-notes" style="height: 300px; overflow-y: auto; border: 1px solid var(--border); padding: 10px; background: var(--entry-bg); border-radius: 4px; font-size: 12px; line-height: 1.6;">
              Loading latest release notes...
            </div>
            
            <div class="about-logo" style="margin-top: 20px;">
              <img src="\${vineyardLogoBase64}" alt="Vineyard Technologies Logo" style="max-width: 100%; height: auto; cursor: pointer;" onclick="openUrl('https://VineyardTechnologies.org')">
            </div>
            <p style="text-align: center; margin: 10px 0;">
              <a href="#" onclick="openUrl('https://VineyardTechnologies.org'); return false;">https://VineyardTechnologies.org</a>
            </p>
          </div>
        </div>
      \`;
      document.body.appendChild(modal);
      
      // Close modal when clicking outside the content
      modal.addEventListener('click', closeAbout);
      
      // Fetch patch notes
      fetchPatchNotes();
    }
    
    async function fetchPatchNotes() {
      const patchNotesDiv = document.getElementById('patch-notes');
      
      try {
        const response = await fetch('https://api.github.com/repos/Vineyard-Technologies/Overlord/releases/latest');
        
        if (!response.ok) {
          throw new Error(\`HTTP error! status: \${response.status}\`);
        }
        
        const releaseData = await response.json();
        
        // Extract release information
        const tagName = releaseData.tag_name || 'Unknown';
        const releaseName = releaseData.name || 'Unknown Release';
        const body = releaseData.body || 'No release notes available.';
        const publishedAt = releaseData.published_at || '';
        
        // Format the date
        let formattedDate = 'Unknown date';
        if (publishedAt) {
          try {
            const dateObj = new Date(publishedAt);
            formattedDate = dateObj.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
          } catch (e) {
            formattedDate = publishedAt;
          }
        }
        
        // Render markdown-style content
        const formattedContent = renderMarkdown(\`# \${releaseName} (\${tagName})\\n**Released:** \${formattedDate}\\n\\n\${body}\`);
        patchNotesDiv.innerHTML = formattedContent;
        
      } catch (error) {
        console.error('Failed to fetch patch notes:', error);
        patchNotesDiv.innerHTML = \`
          <p>Could not load patch notes.</p>
          <p><strong>Error:</strong> \${error.message}</p>
          <p>Please visit: <a href="#" onclick="openUrl('https://github.com/Vineyard-Technologies/Overlord/releases/latest'); return false;">https://github.com/Vineyard-Technologies/Overlord/releases/latest</a></p>
        \`;
      }
    }
    
    function renderMarkdown(text) {
      // Simple markdown renderer for patch notes
      let html = '';
      const lines = text.split('\\n');
      const tripleBacktick = String.fromCharCode(96) + String.fromCharCode(96) + String.fromCharCode(96);
      
      for (let i = 0; i < lines.length; i++) {
        let line = lines[i];
        
        // Headers
        if (line.startsWith('# ')) {
          html += \`<h1 style="font-size: 16px; font-weight: bold; margin: 10px 0 5px 0;">\${escapeHtml(line.substring(2))}</h1>\`;
        } else if (line.startsWith('## ')) {
          html += \`<h2 style="font-size: 14px; font-weight: bold; margin: 10px 0 5px 0;">\${escapeHtml(line.substring(3))}</h2>\`;
        } else if (line.startsWith('### ')) {
          html += \`<h3 style="font-size: 13px; font-weight: bold; margin: 10px 0 5px 0;">\${escapeHtml(line.substring(4))}</h3>\`;
        }
        // Bullet points
        else if (line.startsWith('- ') || line.startsWith('* ')) {
          html += \`<div style="margin-left: 20px;">• \${processInlineMarkdown(line.substring(2))}</div>\`;
        }
        // Code blocks
        else if (line.startsWith(tripleBacktick)) {
          // Skip the opening marker
          continue;
        }
        // Regular text
        else if (line.trim()) {
          html += \`<p style="margin: 5px 0;">\${processInlineMarkdown(line)}</p>\`;
        } else {
          html += '<br>';
        }
      }
      
      return html;
    }
    
    function processInlineMarkdown(text) {
      // First escape any existing HTML in the text
      text = escapeHtml(text);
      
      // Now replace markdown patterns with HTML tags
      // Handle bold **text**
      text = text.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
      // Handle italic *text* (but not if it's part of ** which is already processed)
      text = text.replace(/\\*(.+?)\\*/g, '<em>$1</em>');
      
      // Handle code blocks - using split/join to avoid regex issues in template literals
      const parts = text.split(String.fromCharCode(96));
      for (let i = 1; i < parts.length; i += 2) {
        if (parts[i]) {
          parts[i] = '<code style="background: rgba(128,128,128,0.2); padding: 2px 4px; border-radius: 3px; font-family: monospace;">' + parts[i] + '</code>';
        }
      }
      text = parts.join('');
      
      // Handle URLs - make them clickable
      text = text.replace(/(https?:\\/\\/[^\\s<]+)/g, '<a href="#" onclick="openUrl(\\\'$1\\\'); return false;" style="color: #0078d4; text-decoration: none;">$1</a>');
      
      return text;
    }
    
    function escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
    
    function closeAbout() {
      const modal = document.getElementById('about-modal');
      if (modal) {
        modal.remove();
      }
    }
    
    function openUrl(url) {
      const { shell } = require('electron');
      shell.openExternal(url);
    }
    
    function autoStartRender() {
      startRender();
    }
    
    // Listen for image updates
    ipcRenderer.on('image-updated', (event, imageData) => {
      currentImagePath = imageData.path;
      
      const preview = document.getElementById('image-preview');
      
      // Read the image file as base64 and display it
      const fs = require('fs');
      try {
        const imageBuffer = fs.readFileSync(imageData.path);
        const base64Image = imageBuffer.toString('base64');
        const mimeType = 'image/png'; // Always PNG as specified
        preview.innerHTML = '<img src="data:' + mimeType + ';base64,' + base64Image + '" alt="Rendered Image">';
      } catch (error) {
        console.error('Error loading image:', error);
        preview.innerHTML = '<div class="no-image">Error loading image</div>';
      }
      
      document.getElementById('info-file').textContent = imageData.filename || '-';
      document.getElementById('info-size').textContent = formatSize(imageData.size) || '-';
      document.getElementById('info-modified').textContent = imageData.modified ? 
        new Date(imageData.modified).toLocaleString() : '-';
      
      document.getElementById('copy-btn').disabled = false;
    });
    
    // Listen for render progress updates
    ipcRenderer.on('render-progress', (event, progressData) => {
      // Update progress bar
      const progressFill = document.getElementById('progress-fill');
      progressFill.style.width = progressData.progressPercent.toFixed(1) + '%';
      
      // Update output details
      document.getElementById('total-images').textContent = progressData.renderedCount;
      document.getElementById('images-remaining').textContent = progressData.remaining;
      document.getElementById('est-completion').textContent = progressData.estimatedCompletion;
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
  console.log('IPC: load-settings called');
  const settings = settingsManager.loadSettings();
  console.log('IPC: Returning settings:', JSON.stringify(settings, null, 2));
  return settings;
});

ipcMain.handle('save-settings', (event, settings) => {
  console.log('IPC: save-settings called with:', JSON.stringify(settings, null, 2));
  const result = settingsManager.saveSettings(settings);
  console.log('IPC: Save result:', result);
  
  // Start monitoring the output directory for newest image
  if (settings.output_directory) {
    startContinuousImageMonitoring(settings.output_directory);
  }
  
  return result;
});

ipcMain.handle('manage-windows-startup', async (event, enable) => {
  try {
    const Registry = require('winreg');
    const regKey = new Registry({
      hive: Registry.HKCU,
      key: '\\Software\\Microsoft\\Windows\\CurrentVersion\\Run'
    });
    
    const appName = 'Overlord';
    const exePath = process.execPath;
    
    if (enable) {
      // Add to startup
      return new Promise((resolve, reject) => {
        regKey.set(appName, Registry.REG_SZ, exePath, (err) => {
          if (err) {
            console.error('Failed to add Overlord to Windows startup:', err);
            logMessage(`Failed to add to Windows startup: ${err.message}`);
            reject(err);
          } else {
            console.log('Added Overlord to Windows startup:', exePath);
            logMessage('Added Overlord to Windows startup');
            resolve(true);
          }
        });
      });
    } else {
      // Remove from startup
      return new Promise((resolve, reject) => {
        regKey.remove(appName, (err) => {
          if (err && err.message.indexOf('The system cannot find the file specified') === -1) {
            // Ignore "file not found" errors (registry key doesn't exist)
            console.error('Failed to remove Overlord from Windows startup:', err);
            logMessage(`Failed to remove from Windows startup: ${err.message}`);
            reject(err);
          } else {
            console.log('Removed Overlord from Windows startup');
            logMessage('Removed Overlord from Windows startup');
            resolve(true);
          }
        });
      });
    }
  } catch (error) {
    console.error('Error managing Windows startup:', error);
    logMessage(`Error managing Windows startup: ${error.message}`);
    return false;
  }
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

ipcMain.handle('get-version', () => {
  return getDisplayVersion();
});

// ============================================================================
// APP LIFECYCLE
// ============================================================================

app.whenReady().then(() => {
  setupLogger();
  
  // Show splash screen first
  createSplashScreen();
  
  // Create main window after a short delay to ensure splash is visible
  setTimeout(() => {
    createWindow();
    createTray();
  }, 500);
  
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
  stopContinuousImageMonitoring();
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
