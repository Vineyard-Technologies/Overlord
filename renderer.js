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
  document.getElementById('animations').value = (settings.animations || []).join('\n');
  document.getElementById('prop-animations').value = (settings.prop_animations || []).join('\n');
  document.getElementById('gear').value = (settings.gear || []).join('\n');
  document.getElementById('gear-animations').value = (settings.gear_animations || []).join('\n');
  document.getElementById('output-dir').value = settings.output_directory || '';
  document.getElementById('instances').value = settings.number_of_instances || '1';
  document.getElementById('frame-rate').value = settings.frame_rate || '30';
  document.getElementById('cache-threshold').value = settings.cache_db_size_threshold_gb || '10';
  console.log('Settings applied to UI');
}

function getSettings() {
  const renderShadowsEl = document.getElementById('render-shadows');
  const shutdownOnFinishEl = document.getElementById('shutdown-on-finish');
  
  return {
    subject: document.getElementById('subject').value,
    animations: document.getElementById('animations').value.split('\n').filter(s => s.trim()),
    prop_animations: document.getElementById('prop-animations').value.split('\n').filter(s => s.trim()),
    gear: document.getElementById('gear').value.split('\n').filter(s => s.trim()),
    gear_animations: document.getElementById('gear-animations').value.split('\n').filter(s => s.trim()),
    output_directory: document.getElementById('output-dir').value,
    number_of_instances: document.getElementById('instances').value,
    frame_rate: document.getElementById('frame-rate').value,
    cache_db_size_threshold_gb: document.getElementById('cache-threshold').value,
    render_shadows: renderShadowsEl ? renderShadowsEl.checked : (currentSettings.render_shadows !== false),
    shutdown_on_finish: shutdownOnFinishEl ? shutdownOnFinishEl.checked : (currentSettings.shutdown_on_finish !== false),
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
  console.log('autoSave() called - will save in 500ms');
  clearTimeout(saveTimeout);
  saveTimeout = setTimeout(saveSettings, 500);
}

// Clamp number inputs to valid ranges
function clampNumberInputs() {
  const instances = document.getElementById('instances');
  const frameRate = document.getElementById('frame-rate');
  const cacheThreshold = document.getElementById('cache-threshold');
  
  // Clamp instances (min: 1, max: 99)
  if (instances.value) {
    let val = parseInt(instances.value);
    if (val < 1) {
      instances.value = '1';
    } else if (val > 99) {
      instances.value = '99';
    }
  }
  
  // Clamp frame rate (min: 1, max: 999)
  if (frameRate.value) {
    let val = parseInt(frameRate.value);
    if (val < 1) {
      frameRate.value = '1';
    } else if (val > 999) {
      frameRate.value = '999';
    }
  }
  
  // Clamp cache threshold (min: 5, max: 999)
  if (cacheThreshold.value) {
    let val = parseInt(cacheThreshold.value);
    if (val < 5) {
      cacheThreshold.value = '5';
    } else if (val > 999) {
      cacheThreshold.value = '999';
    }
  }
}

// Initialize when DOM is ready
window.addEventListener('DOMContentLoaded', () => {
  console.log('DOM loaded, initializing...');
  
  // Load saved settings
  loadSettings();
  
  // Attach auto-save event listeners
  const inputs = document.querySelectorAll('input, textarea');
  console.log(`Found ${inputs.length} input/textarea elements to attach listeners to`);
  inputs.forEach(el => {
    el.addEventListener('change', autoSave);
    el.addEventListener('input', autoSave);
    el.addEventListener('blur', autoSave);
    console.log(`Attached listeners to: ${el.id || el.name || el.tagName}`);
  });
  
  // Add clamping for number inputs
  const numberInputs = ['instances', 'frame-rate', 'cache-threshold'];
  numberInputs.forEach(id => {
    const input = document.getElementById(id);
    if (input) {
      input.addEventListener('input', clampNumberInputs);
      input.addEventListener('blur', clampNumberInputs);
      input.addEventListener('change', clampNumberInputs);
    }
  });
  
  console.log('Event listeners attached successfully');
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
    const currentValue = document.getElementById('animations').value.trim();
    const newFiles = currentValue ? currentValue + '\n' + result.join('\n') : result.join('\n');
    document.getElementById('animations').value = newFiles;
    autoSave();
  }
}

async function browsePropAnimations() {
  const result = await ipcRenderer.invoke('browse-files', { filters: [{ name: 'DAZ Files', extensions: ['duf'] }] });
  if (result && result.length) {
    const currentValue = document.getElementById('prop-animations').value.trim();
    const newFiles = currentValue ? currentValue + '\n' + result.join('\n') : result.join('\n');
    document.getElementById('prop-animations').value = newFiles;
    autoSave();
  }
}

async function browseGear() {
  const result = await ipcRenderer.invoke('browse-files', { filters: [{ name: 'DAZ Files', extensions: ['duf'] }] });
  if (result && result.length) {
    const currentValue = document.getElementById('gear').value.trim();
    const newFiles = currentValue ? currentValue + '\n' + result.join('\n') : result.join('\n');
    document.getElementById('gear').value = newFiles;
    autoSave();
  }
}

async function browseGearAnimations() {
  const result = await ipcRenderer.invoke('browse-files', { filters: [{ name: 'DAZ Files', extensions: ['duf'] }] });
  if (result && result.length) {
    const currentValue = document.getElementById('gear-animations').value.trim();
    const newFiles = currentValue ? currentValue + '\n' + result.join('\n') : result.join('\n');
    document.getElementById('gear-animations').value = newFiles;
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

function clearAnimations() {
  document.getElementById('animations').value = '';
  autoSave();
}

function clearPropAnimations() {
  document.getElementById('prop-animations').value = '';
  autoSave();
}

function clearGear() {
  document.getElementById('gear').value = '';
  autoSave();
}

function clearGearAnimations() {
  document.getElementById('gear-animations').value = '';
  autoSave();
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
  document.getElementById('session-images').textContent = '-';
  document.getElementById('total-images').textContent = '-';
  document.getElementById('images-remaining').textContent = '-';
  document.getElementById('est-completion').textContent = '-';
}

function copyPath() {
  if (currentImagePath) {
    ipcRenderer.invoke('copy-to-clipboard', currentImagePath);
  }
}

async function showOutputFolder() {
  const outputDir = document.getElementById('output-dir').value;
  if (outputDir) {
    await ipcRenderer.invoke('show-folder', outputDir);
  } else {
    alert('No output directory specified');
  }
}

async function showImageInFolder() {
  if (currentImagePath) {
    await ipcRenderer.invoke('show-folder', currentImagePath);
  } else {
    alert('No image has been rendered yet');
  }
}

async function openImageFile() {
  if (currentImagePath) {
    await ipcRenderer.invoke('open-file', currentImagePath);
  } else {
    alert('No image has been rendered yet');
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
  autoSave();
}

async function showSettings() {
  // Create modal overlay
  const modal = document.createElement('div');
  modal.id = 'settings-modal';
  modal.innerHTML = `
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
        <div class="setting-item">
          <label>
            <input type="checkbox" id="render-shadows" onchange="onSettingChange('render_shadows', this.checked)">
            Render Shadows
          </label>
        </div>
        <div class="setting-item">
          <label>
            <input type="checkbox" id="shutdown-on-finish" onchange="onSettingChange('shutdown_on_finish', this.checked)">
            Shut Down on Finish
          </label>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  
  // Close modal when clicking outside the content
  modal.addEventListener('click', closeSettings);
  
  // Load current settings
  const settings = await window.ipcRenderer.invoke('load-settings');
  document.getElementById('minimize-to-tray').checked = settings.minimize_to_tray || false;
  document.getElementById('start-on-startup').checked = settings.start_on_startup || false;
  document.getElementById('hide-daz-instances').checked = settings.hide_daz_instances || false;
  document.getElementById('render-shadows').checked = settings.render_shadows !== false;
  document.getElementById('shutdown-on-finish').checked = settings.shutdown_on_finish !== false;
}

function closeSettings() {
  const modal = document.getElementById('settings-modal');
  if (modal) {
    modal.classList.add('fade-out');
    setTimeout(() => {
      modal.remove();
    }, 200);
  }
}

async function onSettingChange(key, value) {
  // Save setting immediately
  const settings = await window.ipcRenderer.invoke('load-settings');
  settings[key] = value;
  await window.ipcRenderer.invoke('save-settings', settings);
  
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

function showIrayServerInterface() {
  const { shell } = require('electron');
  shell.openExternal('http://127.0.0.1:9090/');
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
  modal.innerHTML = `
    <div class="about-content" onclick="event.stopPropagation()">
      <div class="about-header">
        <h2>About Overlord</h2>
        <button class="close-btn" onclick="closeAbout()">&times;</button>
      </div>
      <div class="about-body">
        <div class="about-logo">
          <img src="${overlordLogoBase64}" alt="Overlord Logo" style="max-width: 100%; height: auto; cursor: pointer;" onclick="openUrl('https://github.com/Vineyard-Technologies/Overlord')">
        </div>
        <p style="text-align: center; margin: 10px 0;">
          <a href="#" onclick="openUrl('https://github.com/Vineyard-Technologies/Overlord'); return false;">https://github.com/Vineyard-Technologies/Overlord</a>
        </p>
        <p style="text-align: center; font-size: 16px; font-weight: bold; margin: 20px 0;">Version ${version}</p>
        
        <h3 style="margin: 20px 0 10px 0; font-size: 14px; font-weight: bold;">Latest Release Notes:</h3>
        <div id="patch-notes" style="height: 300px; overflow-y: auto; border: 1px solid var(--border); padding: 10px; background: var(--entry-bg); border-radius: 4px; font-size: 12px; line-height: 1.6;">
          Loading latest release notes...
        </div>
        
        <div class="about-logo" style="margin-top: 20px;">
          <img src="${vineyardLogoBase64}" alt="Vineyard Technologies Logo" style="max-width: 100%; height: auto; cursor: pointer;" onclick="openUrl('https://VineyardTechnologies.org')">
        </div>
        <p style="text-align: center; margin: 10px 0;">
          <a href="#" onclick="openUrl('https://VineyardTechnologies.org'); return false;">https://VineyardTechnologies.org</a>
        </p>
      </div>
    </div>
  `;
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
      throw new Error(`HTTP error! status: ${response.status}`);
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
    const formattedContent = renderMarkdown(`# ${releaseName} (${tagName})\n**Released:** ${formattedDate}\n\n${body}`);
    patchNotesDiv.innerHTML = formattedContent;
    
  } catch (error) {
    console.error('Failed to fetch patch notes:', error);
    patchNotesDiv.innerHTML = `
      <p>Could not load patch notes.</p>
      <p><strong>Error:</strong> ${error.message}</p>
      <p>Please visit: <a href="#" onclick="openUrl('https://github.com/Vineyard-Technologies/Overlord/releases/latest'); return false;">https://github.com/Vineyard-Technologies/Overlord/releases/latest</a></p>
    `;
  }
}

function renderMarkdown(text) {
  // Simple markdown renderer for patch notes
  let html = '';
  const lines = text.split('\n');
  const tripleBacktick = '```';
  
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    
    // Headers
    if (line.startsWith('# ')) {
      html += `<h1 style="font-size: 16px; font-weight: bold; margin: 10px 0 5px 0;">${escapeHtml(line.substring(2))}</h1>`;
    } else if (line.startsWith('## ')) {
      html += `<h2 style="font-size: 14px; font-weight: bold; margin: 10px 0 5px 0;">${escapeHtml(line.substring(3))}</h2>`;
    } else if (line.startsWith('### ')) {
      html += `<h3 style="font-size: 13px; font-weight: bold; margin: 10px 0 5px 0;">${escapeHtml(line.substring(4))}</h3>`;
    }
    // Bullet points
    else if (line.startsWith('- ') || line.startsWith('* ')) {
      html += `<div style="margin-left: 20px;">• ${processInlineMarkdown(line.substring(2))}</div>`;
    }
    // Code blocks
    else if (line.startsWith(tripleBacktick)) {
      // Skip the opening marker
      continue;
    }
    // Regular text
    else if (line.trim()) {
      html += `<p style="margin: 5px 0;">${processInlineMarkdown(line)}</p>`;
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
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Handle italic *text* (but not if it's part of ** which is already processed)
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
  
  // Handle code blocks - using split/join to avoid regex issues
  const parts = text.split('`');
  for (let i = 1; i < parts.length; i += 2) {
    if (parts[i]) {
      parts[i] = '<code style="background: rgba(128,128,128,0.2); padding: 2px 4px; border-radius: 3px; font-family: monospace;">' + parts[i] + '</code>';
    }
  }
  text = parts.join('');
  
  // Handle URLs - make them clickable
  text = text.replace(/(https?:\/\/[^\s<]+)/g, '<a href="#" onclick="openUrl(\'$1\'); return false;" style="color: #0078d4; text-decoration: none;">$1</a>');
  
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
    modal.classList.add('fade-out');
    setTimeout(() => {
      modal.remove();
    }, 200);
  }
}

function openUrl(url) {
  const { shell } = require('electron');
  shell.openExternal(url);
}

function autoStartRender() {
  startRender();
}

// Format date with day of week and ordinal suffix
function formatDateWithDay(date) {
  const dayOfWeek = date.toLocaleDateString('en-US', { weekday: 'long' });
  
  const timeStr = date.toLocaleTimeString('en-US', { 
    hour: 'numeric', 
    minute: '2-digit',
    hour12: true 
  });
  
  const day = date.getDate();
  const daySuffix = ['th', 'st', 'nd', 'rd'][(day % 10 > 3 || Math.floor(day / 10) === 1) ? 0 : day % 10];
  
  const monthStr = date.toLocaleDateString('en-US', { month: 'long' });
  const yearStr = date.getFullYear();
  
  return `${dayOfWeek}, ${timeStr}, ${monthStr} ${day}${daySuffix}, ${yearStr}`;
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
    
    // Create an image element to get dimensions
    const img = new Image();
    img.onload = function() {
      document.getElementById('info-resolution').textContent = `${this.width} × ${this.height}`;
    };
    img.src = 'data:' + mimeType + ';base64,' + base64Image;
    
    preview.innerHTML = '<img src="data:' + mimeType + ';base64,' + base64Image + '" alt="Rendered Image">';
  } catch (error) {
    console.error('Error loading image:', error);
    preview.innerHTML = '<img src="images/noImagesFound.webp" alt="No images found">';
    document.getElementById('info-resolution').textContent = '-';
  }
  
  // Update filename with clickable styling
  const infoFileElement = document.getElementById('info-file');
  infoFileElement.textContent = imageData.filename || '-';
  infoFileElement.style.cursor = 'pointer';
  infoFileElement.style.textDecoration = 'underline';
  infoFileElement.style.color = 'var(--select-bg)';
  infoFileElement.onclick = openImageFile;
  
  document.getElementById('info-size').textContent = formatSize(imageData.size) || '-';
  document.getElementById('info-created').textContent = imageData.created ? 
    formatDateWithDay(new Date(imageData.created)) : '-';
  
  if (document.getElementById('copy-btn')) {
    document.getElementById('copy-btn').disabled = false;
  }
});

// Listen for render progress updates
ipcRenderer.on('render-progress', (event, progressData) => {
  // Update progress bar
  const progressFill = document.getElementById('progress-fill');
  progressFill.style.width = progressData.progressPercent.toFixed(1) + '%';
  
  // Update output details
  document.getElementById('session-images').textContent = progressData.sessionCount;
  document.getElementById('total-images').textContent = progressData.renderedCount;
  document.getElementById('images-remaining').textContent = progressData.remaining;
  document.getElementById('est-completion').textContent = progressData.estimatedCompletion;
  
  // Re-enable Start Render button when render is complete
  if (progressData.isComplete) {
    document.getElementById('start-btn').disabled = false;
  }
});

// Listen for no images found event
ipcRenderer.on('no-images-found', () => {
  const preview = document.getElementById('image-preview');
  preview.innerHTML = '<img src="images/noImagesFound.webp" alt="No images found">';
  
  // Reset image info and remove clickable styling
  const infoFileElement = document.getElementById('info-file');
  infoFileElement.textContent = '-';
  infoFileElement.style.cursor = 'default';
  infoFileElement.style.textDecoration = 'none';
  infoFileElement.style.color = 'inherit';
  infoFileElement.onclick = null;
  
  document.getElementById('info-resolution').textContent = '-';
  document.getElementById('info-size').textContent = '-';
  document.getElementById('info-created').textContent = '-';
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

// ============================================================================
// CONSTRUCT EXPORTER
// ============================================================================

function showConstructExporter() {
  const modal = document.createElement('div');
  modal.id = 'construct-exporter-modal';
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
  `;
  
  modal.innerHTML = `
    <div style="background: var(--bg); border: 1px solid var(--border); border-radius: 8px; width: 700px; max-width: 90%; max-height: 80vh; display: flex; flex-direction: column; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);">
      <div style="padding: 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
        <h2 style="margin: 0;">Construct Exporter</h2>
        <button class="close-btn" onclick="closeConstructExporter()" style="font-size: 28px; border: none; background: none; color: var(--fg); cursor: pointer; padding: 0; width: 32px; height: 32px; line-height: 28px;">&times;</button>
      </div>
      
      <div id="exporter-content" style="padding: 20px; flex: 1; overflow-y: auto;">
        <p style="margin: 0 0 20px 0; font-size: 16px;">Run the Construct Exporter on all files in the output folder?</p>
        <p style="margin: 0 0 12px 0; font-size: 14px; opacity: 0.8; font-family: 'Consolas', 'Courier New', monospace;">Source folder: <span id="exporter-output-path"></span></p>
        
        <div style="margin-bottom: 20px;">
          <label style="display: block; margin-bottom: 6px; font-size: 14px;">Export Destination:</label>
          <div style="display: flex; gap: 8px;">
            <input type="text" id="exporter-destination-path" placeholder="Choose export destination folder" spellcheck="false" style="flex: 1; padding: 8px; background: var(--entry-bg); color: var(--entry-fg); border: 1px solid var(--border); border-radius: 4px; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px;">
            <button onclick="browseExportDestination()" style="padding: 8px 16px; white-space: nowrap;">Browse</button>
          </div>
        </div>
        
        <div id="exporter-log-container" style="display: none; margin-top: 20px; padding: 12px; background: var(--entry-bg); border: 1px solid var(--border); border-radius: 4px; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; max-height: 400px; overflow-y: auto; white-space: pre-wrap; word-break: break-word;"></div>
        
        <div id="exporter-progress" style="display: none; margin-top: 20px; text-align: center; font-style: italic; opacity: 0.8; font-size: 15px;">Running exporter...</div>
      </div>
      
      <div style="padding: 20px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 12px;">
        <button id="exporter-yes-btn" onclick="runConstructExporter()" class="btn-primary" style="padding: 10px 24px;">Yes</button>
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
  
  // Populate output path
  const settings = getSettings();
  const outputDir = settings.output_directory || '-';
  document.getElementById('exporter-output-path').textContent = outputDir;
  
  // Set default destination to same as source
  document.getElementById('exporter-destination-path').value = outputDir;
  
  // Close on background click
  modal.onclick = (e) => {
    if (e.target === modal) {
      closeConstructExporter();
    }
  };
}

async function browseExportDestination() {
  try {
    const directory = await ipcRenderer.invoke('browse-directory');
    if (directory) {
      document.getElementById('exporter-destination-path').value = directory;
    }
  } catch (error) {
    console.error('Error browsing for export destination:', error);
  }
}

function closeConstructExporter() {
  const modal = document.getElementById('construct-exporter-modal');
  if (modal) {
    modal.remove();
  }
}

async function runConstructExporter() {
  const yesBtn = document.getElementById('exporter-yes-btn');
  const logContainer = document.getElementById('exporter-log-container');
  const progressDiv = document.getElementById('exporter-progress');
  const destinationPath = document.getElementById('exporter-destination-path').value;
  
  // Validate destination path
  if (!destinationPath || !destinationPath.trim()) {
    alert('Please select an export destination folder.');
    return;
  }
  
  // Disable the Yes button and show progress
  yesBtn.disabled = true;
  yesBtn.textContent = 'Running...';
  logContainer.style.display = 'block';
  progressDiv.style.display = 'block';
  logContainer.textContent = 'Starting Construct Exporter...\n\n';
  
  try {
    // Listen for output updates
    const outputListener = (event, text) => {
      logContainer.textContent += text;
      // Auto-scroll to bottom
      logContainer.scrollTop = logContainer.scrollHeight;
    };
    
    ipcRenderer.on('construct-exporter-output', outputListener);
    
    // Run the exporter with destination path
    const result = await ipcRenderer.invoke('run-construct-exporter', destinationPath);
    
    // Remove the listener
    ipcRenderer.removeListener('construct-exporter-output', outputListener);
    
    // Update UI
    progressDiv.style.display = 'none';
    logContainer.textContent += '\n\n✓ Export completed successfully!';
    yesBtn.textContent = 'Done';
    yesBtn.disabled = false;
    yesBtn.onclick = closeConstructExporter;
    
    // Change button text to "Close"
    setTimeout(() => {
      yesBtn.textContent = 'Close';
    }, 100);
    
  } catch (error) {
    console.error('Construct Exporter error:', error);
    
    progressDiv.style.display = 'none';
    logContainer.textContent += '\n\n✗ Export failed: ' + error.message;
    yesBtn.textContent = 'Close';
    yesBtn.disabled = false;
    yesBtn.onclick = closeConstructExporter;
  }
}
