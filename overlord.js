const { app, BrowserWindow, ipcMain, Menu, Tray, dialog, nativeTheme, clipboard } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');
const util = require('util');
const { exec } = require('child_process');
const execPromise = util.promisify(exec);

// ============================================================================
// CONSTANTS AND CONFIGURATION
// ============================================================================

const APP_VERSION = '3.0.3';
const LOG_SIZE_MB = 10;
const LOG_SIZE_DAZ = '10m';


// File extensions
const IMAGE_EXTENSIONS = ['.png'];

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
let sessionStartImageCount = 0;
let renderStartTime = null;
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
    // When packaged with asar disabled, files are in resources/app/
    return path.join(process.resourcesPath, 'app', relativePath);
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
  try {
    const logDir = getAppDataPath();
    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }
    
    const logPath = path.join(logDir, 'log.txt');
    console.log(`--- Overlord started --- (log file: ${normalizePathForLogging(logPath)}, max size: ${LOG_SIZE_MB} MB)`);
    
    // Redirect console to file (simple implementation)
    const logStream = fs.createWriteStream(logPath, { flags: 'a', encoding: 'utf8' });
    const originalLog = console.log;
    const originalError = console.error;
    const originalWarn = console.warn;
    
    console.log = function(...args) {
      const timestamp = new Date().toISOString();
      const message = `${timestamp} INFO: ${args.join(' ')}\n`;
      try {
        logStream.write(message);
      } catch (e) {
        // Silently fail if log write fails
      }
      originalLog.apply(console, args);
    };
    
    console.error = function(...args) {
      const timestamp = new Date().toISOString();
      const message = `${timestamp} ERROR: ${args.join(' ')}\n`;
      try {
        logStream.write(message);
      } catch (e) {
        // Silently fail if log write fails
      }
      originalError.apply(console, args);
    };
    
    console.warn = function(...args) {
      const timestamp = new Date().toISOString();
      const message = `${timestamp} WARNING: ${args.join(' ')}\n`;
      try {
        logStream.write(message);
      } catch (e) {
        // Silently fail if log write fails
      }
      originalWarn.apply(console, args);
    };
  } catch (error) {
    // If logger setup fails, continue without file logging
    console.error('Failed to setup logger:', error);
    throw error; // Re-throw so app initialization can handle it
  }
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
      console.log(`Static render: ${angles} angles x ${frames} frame x ${gearCount} gear = ${imagesForThisAnimation} images`);
    } else {
      const frames = getFramesFromAnimationFile(animationFilepath.trim());
      const imagesForThisAnimation = angles * frames * gearCount;
      totalImages += imagesForThisAnimation;
      console.log(`Animation ${normalizePathForLogging(animationFilepath)}: ${angles} angles x ${frames} frames x ${gearCount} gear = ${imagesForThisAnimation} images`);
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

async function stopIrayServer() {
  try {
    console.log('Stopping Iray Server using Node.js native process management');
    
    // Kill Iray Server processes
    const irayProcessNames = ['iray_server.exe', 'iray_server_worker.exe'];
    let killedCount = 0;
    
    for (const processName of irayProcessNames) {
      try {
        await execPromise(`taskkill /F /IM ${processName}`);
        console.log(`Killed Iray Server process: ${processName}`);
        killedCount++;
      } catch (error) {
        // Process might not be running (taskkill returns error if process not found)
        console.log(`No ${processName} process found`);
      }
    }
    
    // Wait a moment for processes to fully terminate
    if (killedCount > 0) {
      console.log('Waiting for processes to fully terminate...');
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    
    // Clean up Iray Server directory
    const irayServerDir = path.join(getLocalAppDataPath(), 'IrayServer');
    
    if (fs.existsSync(irayServerDir)) {
      console.log(`Cleaning Iray Server directory: ${normalizePathForLogging(irayServerDir)}`);
      
      try {
        // Use Node.js built-in recursive removal with retry logic
        fs.rmSync(irayServerDir, { 
          recursive: true, 
          force: true, 
          maxRetries: 10, 
          retryDelay: 1000 
        });
        console.log('Iray Server directory cleaned successfully');
      } catch (error) {
        console.error(`Failed to clean Iray Server directory: ${error.message}`);
        // Try to continue anyway
      }
    } else {
      console.log('Iray Server directory does not exist, nothing to clean');
    }
    
    console.log(`Iray Server stopped successfully (${killedCount} processes terminated)`);
    return killedCount > 0 ? 1 : 0;
    
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
    if (isNaN(cacheThreshold) || cacheThreshold < 5 || cacheThreshold > 1000) {
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
  
  // Count existing images at session start
  sessionStartImageCount = countImagesInDirectory(finalOutputDir);
  
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
    renderScriptPath = path.join(process.resourcesPath, 'app', 'scripts', 'masterRenderer.dsa').replace(/\\/g, '/');
    templatePath = path.join(process.resourcesPath, 'app', 'templates', 'masterTemplate.duf').replace(/\\/g, '/');
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
            created: stats.birthtime
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
          
          // Format as "Monday, 3:14 PM, February 15th, 2025"
          const dayOfWeek = completionTime.toLocaleDateString('en-US', { weekday: 'long' });
          
          const timeStr = completionTime.toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit',
            hour12: true 
          });
          
          const day = completionTime.getDate();
          const daySuffix = ['th', 'st', 'nd', 'rd'][(day % 10 > 3 || Math.floor(day / 10) === 1) ? 0 : day % 10];
          
          const monthStr = completionTime.toLocaleDateString('en-US', { month: 'long' });
          const yearStr = completionTime.getFullYear();
          
          estimatedCompletion = `${dayOfWeek}, ${timeStr}, ${monthStr} ${day}${daySuffix}, ${yearStr}`;
        } else {
          estimatedCompletion = 'Calculating...';
        }
      } else {
        estimatedCompletion = 'Complete';
      }
      
      mainWindow.webContents.send('render-progress', {
        totalImages: initialTotalImages,
        renderedCount: renderedCount,
        sessionCount: Math.max(0, renderedCount - sessionStartImageCount),
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
  if (!outputDirectory) {
    return;
  }
  
  // Monitor for newest image every 5 seconds
  const checkForNewestImage = () => {
    // Check if directory exists
    if (!fs.existsSync(outputDirectory)) {
      if (currentImagePath !== null && mainWindow) {
        currentImagePath = null;
        mainWindow.webContents.send('no-images-found');
      }
      return;
    }
    
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
            created: stats.birthtime
          };
          
          if (mainWindow) {
            mainWindow.webContents.send('image-updated', imageData);
          }
        } catch (error) {
          console.error('Error getting image stats:', error);
        }
      }
    } else if (currentImagePath !== null) {
      // No images found and we previously had an image - send no-images-found event
      currentImagePath = null;
      if (mainWindow) {
        mainWindow.webContents.send('no-images-found');
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
  try {
    currentTheme = detectWindowsTheme();
    
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
    let hasSplashImage = false;
    
    try {
      hasSplashImage = fs.existsSync(splashImagePath);
    } catch (error) {
      console.warn('Could not check for splash image:', error);
    }
    
    let splashHTML;
    if (hasSplashImage) {
      try {
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
            <img src="data:image/webp;base64,${base64Image}" class="splash-image" alt="Overlord">
          </body>
          </html>
        `;
      } catch (error) {
        console.warn('Failed to load splash image, using fallback:', error);
        hasSplashImage = false;
      }
    }
    
    if (!hasSplashImage) {
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
  } catch (error) {
    console.error('Failed to create splash screen:', error);
    // Continue without splash screen
  }
}

function createWindow() {
  try {
    currentTheme = detectWindowsTheme();
    
    // Check if icon exists before creating window
    const iconPath = resourcePath(path.join('images', 'favicon.ico'));
    let windowOptions = {
      width: 1200,
      height: 900,
      minWidth: 800,
      minHeight: 600,
      backgroundColor: THEME_COLORS[currentTheme].bg,
      show: false,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false
      }
    };
    
    // Only set icon if it exists
    try {
      if (fs.existsSync(iconPath)) {
        windowOptions.icon = iconPath;
      } else {
        console.warn('Window icon not found at:', iconPath);
      }
    } catch (error) {
      console.warn('Could not check for window icon:', error);
    }
    
    mainWindow = new BrowserWindow(windowOptions);
    
    // Hide default Electron menu bar (we have our own in the HTML)
    mainWindow.setMenuBarVisibility(false);
    mainWindow.setMenu(null);
    
    // Load HTML file
    const htmlPath = resourcePath('index.html');
    mainWindow.loadFile(htmlPath);
    
    // Apply theme after page loads
    mainWindow.webContents.on('did-finish-load', () => {
      const themeClass = currentTheme === 'light' ? 'theme-light' : 'theme-dark';
      mainWindow.webContents.executeJavaScript(`document.body.className = '${themeClass}';`);
    });
    
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
        try {
          const settings = settingsManager.loadSettings();
          if (settings.output_directory) {
            startContinuousImageMonitoring(settings.output_directory);
          }
        } catch (error) {
          console.error('Error starting continuous monitoring:', error);
        }
        
        // Check for auto-start
        const autoStart = process.argv.includes('--startRender');
        if (autoStart) {
          mainWindow.webContents.executeJavaScript('if (window.autoStartRender) window.autoStartRender();');
        }
      }, remainingTime);
    });
    
    mainWindow.on('minimize', () => {
      try {
        const settings = settingsManager.loadSettings();
        if (settings.minimize_to_tray && tray) {
          mainWindow.hide();
        }
      } catch (error) {
        console.error('Error handling minimize:', error);
      }
    });
    
    mainWindow.on('close', () => {
      try {
        stopFileMonitoring();
        stopContinuousImageMonitoring();
        if (tray) {
          tray.destroy();
          tray = null;
        }
      } catch (error) {
        console.error('Error handling window close:', error);
      }
    });
    
    mainWindow.on('closed', () => {
      mainWindow = null;
    });
    
    // Development mode
    if (process.argv.includes('--dev')) {
      mainWindow.webContents.openDevTools();
    }
  } catch (error) {
    console.error('Failed to create main window:', error);
    throw error; // Re-throw so app initialization can handle it
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

ipcMain.handle('copy-to-clipboard', (event, text) => {
  clipboard.writeText(text);
});

ipcMain.handle('show-folder', async (event, folderPath) => {
  const { shell } = require('electron');
  try {
    // Check if folder exists
    if (fs.existsSync(folderPath)) {
      // Open parent folder and select the output folder
      shell.showItemInFolder(folderPath);
    } else {
      dialog.showErrorBox('Folder Not Found', `The folder does not exist:\n${folderPath}`);
    }
  } catch (error) {
    console.error('Error opening folder:', error);
    dialog.showErrorBox('Error', `Failed to open folder: ${error.message}`);
  }
});

ipcMain.handle('open-file', async (event, filePath) => {
  const { shell } = require('electron');
  try {
    // Check if file exists
    if (fs.existsSync(filePath)) {
      // Open the file with default application
      shell.openPath(filePath);
    } else {
      dialog.showErrorBox('File Not Found', `The file does not exist:\n${filePath}`);
    }
  } catch (error) {
    console.error('Error opening file:', error);
    dialog.showErrorBox('Error', `Failed to open file: ${error.message}`);
  }
});

ipcMain.handle('get-version', () => {
  return getDisplayVersion();
});

// ============================================================================
// APP LIFECYCLE
// ============================================================================

// Global error handlers
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  dialog.showErrorBox('Fatal Error', `An unexpected error occurred:\n\n${error.message}\n\nThe application will now exit.`);
  app.quit();
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

app.whenReady().then(() => {
  try {
    setupLogger();
    
    // Show splash screen first
    createSplashScreen();
    
    // Create main window after a short delay to ensure splash is visible
    setTimeout(() => {
      try {
        createWindow();
        createTray();
      } catch (error) {
        console.error('Error creating main window or tray:', error);
        dialog.showErrorBox('Startup Error', `Failed to create application window:\n\n${error.message}`);
      }
    }, 500);
    
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
      }
    });
  } catch (error) {
    console.error('Error during app initialization:', error);
    dialog.showErrorBox('Startup Error', `Failed to initialize application:\n\n${error.message}`);
    app.quit();
  }
}).catch((error) => {
  console.error('Error in app.whenReady:', error);
  dialog.showErrorBox('Fatal Error', `Application failed to start:\n\n${error.message}`);
  app.quit();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  try {
    stopFileMonitoring();
    stopContinuousImageMonitoring();
    if (tray) {
      tray.destroy();
    }
  } catch (error) {
    console.error('Error during cleanup:', error);
  }
});

// Theme change listener
nativeTheme.on('updated', () => {
  try {
    currentTheme = detectWindowsTheme();
    if (mainWindow) {
      // Reload the page and apply the new theme
      const themeClass = currentTheme === 'light' ? 'theme-light' : 'theme-dark';
      mainWindow.webContents.executeJavaScript(`document.body.className = '${themeClass}';`);
    }
  } catch (error) {
    console.error('Error updating theme:', error);
  }
});

console.log('Overlord Electron application initialized');
