const fs = require('fs');
const path = require('path');
const os = require('os');
const archiver = require('archiver');

/**
 * Parse a filename to extract the components needed for organization.
 * Expected format: prefix-action_rotation-sequence.extension
 * Example: woman_shadow-powerUp_-67.5-014.webp
 * Returns: { prefix, action, baseName }
 */
function parseFilename(filename) {
  // Remove extension
  const stem = path.parse(filename).name;
  
  // Pattern to match: prefix-action_rotation-sequence
  // This handles cases like: woman_shadow-powerUp_-67.5-014
  const pattern = /^([^-]+)-([^_]+)_(.+)-\d+$/;
  const match = stem.match(pattern);
  
  if (match) {
    const prefix = match[1];  // woman_shadow
    const action = match[2];  // powerUp
    const rotationPart = match[3];  // -67.5
    
    // Create the base name without sequence number
    const baseName = `${prefix}-${action}_${rotationPart}`;
    
    return { prefix, action, baseName };
  } else {
    // Fallback for files that don't match expected pattern
    const parts = stem.split('-');
    if (parts.length >= 2) {
      const prefix = parts[0];
      const action = parts[1].includes('_') ? parts[1].split('_')[0] : parts[1];
      return { prefix, action, baseName: stem };
    } else {
      return { prefix: stem, action: 'unknown', baseName: stem };
    }
  }
}

/**
 * Create a single zip archive from a group of files.
 * Returns a Promise that resolves when the zip is created.
 */
async function createZipArchive(baseName, files, outputPath) {
  if (!files || files.length === 0) {
    return null;
  }
  
  // Use the first file's metadata for folder structure
  const firstFile = files[0];
  const { prefix, action } = firstFile;
  
  // Create directory structure: ConstructZips/prefix/action/
  const targetDir = path.join(outputPath, prefix, action);
  fs.mkdirSync(targetDir, { recursive: true });
  
  // Create zip file: action_rotation.zip (without prefix)
  // Extract action and rotation from baseName (format: prefix-action_rotation)
  const actionRotation = baseName.includes('-') ? baseName.split('-').slice(1).join('-') : baseName;
  const zipPath = path.join(targetDir, `${actionRotation}.zip`);
  
  return new Promise((resolve, reject) => {
    // Create a write stream for the zip file
    const output = fs.createWriteStream(zipPath);
    const archive = archiver('zip', {
      store: true // No compression - maximum speed
    });
    
    output.on('close', () => {
      resolve(`Created ${zipPath} with ${files.length} files (${archive.pointer()} bytes)`);
    });
    
    archive.on('error', (err) => {
      reject(`Error creating ${zipPath}: ${err.message}`);
    });
    
    // Pipe archive data to the file
    archive.pipe(output);
    
    // Add files to the archive
    for (const fileInfo of files) {
      const filePath = fileInfo.filePath;
      const fileName = path.basename(filePath);
      archive.file(filePath, { name: fileName });
    }
    
    // Finalize the archive
    archive.finalize();
  });
}

/**
 * Organize files from sourceDir into folders and zip archives in outputBaseDir.
 * Uses Promise.all with batching to process multiple zips concurrently.
 */
async function organizeFiles(sourceDir, outputBaseDir, maxConcurrent = null) {
  const sourcePath = path.resolve(sourceDir);
  const outputPath = path.join(path.resolve(outputBaseDir), 'ConstructZips');
  
  if (!fs.existsSync(sourcePath)) {
    throw new Error(`Source directory does not exist: ${sourceDir}`);
  }
  
  // Group files by their base name (without sequence number)
  const fileGroups = {};
  
  console.log('Scanning files...');
  
  // Scan all files in the source directory
  const entries = fs.readdirSync(sourcePath, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isFile()) {
      const filePath = path.join(sourcePath, entry.name);
      const { prefix, action, baseName } = parseFilename(entry.name);
      
      if (!fileGroups[baseName]) {
        fileGroups[baseName] = [];
      }
      
      fileGroups[baseName].push({
        filePath,
        prefix,
        action,
        baseName
      });
    }
  }
  
  const groupCount = Object.keys(fileGroups).length;
  console.log(`Found ${groupCount} unique file groups`);
  
  // Prepare tasks for processing
  const zipTasks = Object.entries(fileGroups).map(([baseName, files]) => ({
    baseName,
    files,
    outputPath
  }));
  
  // Determine maximum concurrent operations
  if (maxConcurrent === null) {
    maxConcurrent = Math.min(32, (os.cpus().length || 1) + 4);
  }
  
  console.log(`Processing ${zipTasks.length} zip archives using ${maxConcurrent} concurrent operations...`);
  
  // Process tasks in batches
  let completedCount = 0;
  const batchSize = maxConcurrent;
  
  for (let i = 0; i < zipTasks.length; i += batchSize) {
    const batch = zipTasks.slice(i, i + batchSize);
    
    const results = await Promise.allSettled(
      batch.map(task => createZipArchive(task.baseName, task.files, task.outputPath))
    );
    
    // Process results
    for (const result of results) {
      if (result.status === 'fulfilled' && result.value) {
        console.log(result.value);
        completedCount++;
        
        if (completedCount % 50 === 0) {
          console.log(`Progress: ${completedCount}/${zipTasks.length} archives completed`);
        }
      } else if (result.status === 'rejected') {
        console.error(result.reason);
      }
    }
  }
  
  console.log(`Completed processing ${completedCount} zip archives`);
}

/**
 * Main function to organize files.
 */
async function main() {
  // Get source directory from command line argument or environment variable
  let sourceDirectory = process.argv[2] || process.env.OUTPUT_DIR;
  
  // Get destination directory from command line argument (if different from source)
  let destinationDirectory = process.argv[3];
  
  // Fallback to Downloads/output if no source directory specified
  if (!sourceDirectory) {
    const downloadsPath = path.join(os.homedir(), 'Downloads');
    sourceDirectory = path.join(downloadsPath, 'output');
  }
  
  // Resolve to absolute paths
  sourceDirectory = path.resolve(sourceDirectory);
  
  // If no destination specified, use source directory
  if (!destinationDirectory) {
    destinationDirectory = sourceDirectory;
  } else {
    destinationDirectory = path.resolve(destinationDirectory);
  }
  
  console.log('Starting file organization...');
  console.log(`Source directory: ${sourceDirectory}`);
  console.log(`Destination directory: ${destinationDirectory}`);
  
  try {
    await organizeFiles(sourceDirectory, destinationDirectory);
    console.log('File organization complete!');
  } catch (error) {
    console.error('Error during file organization:', error);
    process.exit(1);
  }
}

// Run if executed directly
if (require.main === module) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { organizeFiles, parseFilename, createZipArchive };
