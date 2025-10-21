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
  document.getElementById('render-shadows').checked = settings.render_shadows !== false;
  document.getElementById('shutdown-on-finish').checked = settings.shutdown_on_finish !== false;
  console.log('Settings applied to UI');
}

function getSettings() {
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
  
  // Clamp cache threshold (min: 10, max: 999)
  if (cacheThreshold.value) {
    let val = parseInt(cacheThreshold.value);
    if (val < 10) {
      cacheThreshold.value = '10';
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
  document.querySelectorAll('input, textarea').forEach(el => {
    el.addEventListener('change', autoSave);
    el.addEventListener('input', autoSave);
    el.addEventListener('blur', autoSave);
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
    document.getElementById('animations').value = result.join('\n');
    autoSave();
  }
}

async function browsePropAnimations() {
  const result = await ipcRenderer.invoke('browse-files', { filters: [{ name: 'DAZ Files', extensions: ['duf'] }] });
  if (result && result.length) {
    document.getElementById('prop-animations').value = result.join('\n');
    autoSave();
  }
}

async function browseGear() {
  const result = await ipcRenderer.invoke('browse-files', { filters: [{ name: 'DAZ Files', extensions: ['duf'] }] });
  if (result && result.length) {
    document.getElementById('gear').value = result.join('\n');
    autoSave();
  }
}

async function browseGearAnimations() {
  const result = await ipcRenderer.invoke('browse-files', { filters: [{ name: 'DAZ Files', extensions: ['duf'] }] });
  if (result && result.length) {
    document.getElementById('gear-animations').value = result.join('\n');
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
  document.getElementById('render-shadows').checked = true;
  document.getElementById('shutdown-on-finish').checked = true;
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
    preview.innerHTML = '<img src="data:' + mimeType + ';base64,' + base64Image + '" alt="Rendered Image">';
  } catch (error) {
    console.error('Error loading image:', error);
    preview.innerHTML = '<div class="no-image">Error loading image</div>';
  }
  
  document.getElementById('info-file').textContent = imageData.filename || '-';
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
