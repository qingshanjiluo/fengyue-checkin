#!/usr/bin/env node
/**
 * 图片文件名清洗工具
 * 自动去掉末尾十六进制哈希段，给文件加 _tagged 标记
 *
 * 用法: 双击 tag_images.bat
 *       或 node scripts/tag_images.js [选项]
 *
 * 选项:
 *   --name xxx.jpg    处理单张
 *   --all             处理全部未标注（默认）
 *   --dry-run         预览不改名
 *   --force           强制覆盖已有标签
 *   --vision          调用 AI vision 识图标注（需配置 API Key）
 */
const fs = require('fs');
const path = require('path');

let PYTHON = 'python';
function findPython() {
  const candidates = [
    'C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python310\\python.exe',
    'C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\python.exe',
    'python3', 'python',
  ];
  const { execSync } = require('child_process');
  for (const cmd of candidates) {
    try {
      execSync(`"${cmd}" -c "from transformers import VisionEncoderDecoderModel; print('ok')"`, { encoding: 'utf-8', stdio: 'pipe', timeout: 15000 });
      PYTHON = cmd; return;
    } catch {}
  }
}

const SCRIPTS_DIR = __dirname;
const ROOT_DIR = path.resolve(SCRIPTS_DIR, '..');
const IMG_DIR = path.join(ROOT_DIR, 'generated_imgs');
const SETTINGS_FILE = path.join(SCRIPTS_DIR, 'studio_settings.json');
const ALLOWED_EXT = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']);
const TAGGED_MARKER = '_tagged';

function loadSettings() {
  try { return JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf-8')); } catch { return {}; }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/**
 * 从文件名提取有意义的部分：去掉 _tagged 标记和末尾十六进制哈希段
 * 如 23373414_037_fd05.jpg → 23373414_037
 *    suck.jpg            → suck
 */
function extractTags(fname) {
  const dot = fname.lastIndexOf('.');
  let base = dot >= 0 ? fname.slice(0, dot) : fname;
  // Strip _tagged marker if present
  const idx = base.indexOf(TAGGED_MARKER);
  if (idx >= 0) base = base.slice(0, idx).replace(/_+$/, '');

  const segs = base.split('_').filter(Boolean);
  // Remove trailing hex hashes (e.g. fd05, 6c50)
  while (segs.length > 1 && /^[a-f0-9]+$/i.test(segs[segs.length - 1])) {
    segs.pop();
  }
  // Remove trailing Chinese/non-numeric segments (e.g. 未分类 from failed API)
  while (segs.length > 1 && /^[^\d]+$/.test(segs[segs.length - 1])) {
    segs.pop();
  }
  return segs.join('_') || base;
}

function buildNewName(tags, ext) {
  return `${tags}${TAGGED_MARKER}${ext}`;
}

async function callVision(apiUrl, apiKey, model, imageB64, fname) {
  const http = apiUrl.startsWith('https') ? require('https') : require('http');
  const payload = JSON.stringify({
    model,
    messages: [
      { role: 'system', content: '你是一个图片标签生成器。分析图片内容，输出3-6个中文关键词标签，用下划线连接。\n规则：\n1. 只输出关键词，不要任何解释\n2. 关键词要准确描述图片中的主体、场景、风格、色调\n3. 用下划线连接，如：古风_少女_竹林_淡雅\n4. 控制在4-20个汉字之间' },
      { role: 'user', content: [
        { type: 'text', text: `为这张图片生成关键词标签（图片名: ${fname}）` },
        { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${imageB64}` } }
      ]}
    ],
    max_tokens: 100,
    temperature: 0.3,
  });
  const url = new URL(apiUrl.replace(/\/+$/, '') + '/chat/completions');
  return new Promise((resolve, reject) => {
    const req = http.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
        'Content-Length': Buffer.byteLength(payload),
      },
      timeout: 15000,
    }, res => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        if (res.statusCode !== 200) return reject(new Error(`HTTP ${res.statusCode}`));
        try {
          const d = JSON.parse(body);
          const content = d.choices?.[0]?.message?.content?.trim();
          if (!content) return reject(new Error('空响应'));
          const cleaned = content.replace(/[^\u4e00-\u9fff_a-zA-Z0-9]/g, '').replace(/_+/g, '_').replace(/^_|_$/g, '');
          if (!cleaned || /抱歉|无法|拒绝|不能|不符合|规范|安全/i.test(cleaned)) {
            return reject(new Error('模型拒绝'));
          }
          resolve(cleaned.slice(0, 40));
        } catch (e) { reject(new Error('JSON 解析失败')); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('超时')); });
    req.write(payload);
    req.end();
  });
}

async function processImage(fname, settings, dryRun, force, useVision) {
  const filePath = path.join(IMG_DIR, fname);

  if (fname.includes(TAGGED_MARKER) && !force) {
    console.log(`  SKIP (已标注): ${fname}`);
    return { name: fname, ok: false };
  }

  console.log(`\n  处理: ${fname}`);

  let tags;
  if (useVision) {
    console.log(`  → AI 识图...`);
    const imageB64 = fs.readFileSync(filePath).toString('base64');
    try {
      tags = await callVision(
        settings.api_url, settings.api_key, settings.model || 'gpt-4o-mini', imageB64, fname
      );
    } catch (e) {
      console.log(`  [!] AI 失败: ${e.message}，回退到文件名清洗`);
    }
  }

  if (!tags) {
    tags = extractTags(fname);
    console.log(`  → 文件名清洗: ${tags}`);
  }

  const dot = fname.lastIndexOf('.');
  const ext = dot >= 0 ? fname.slice(dot) : '';
  const newName = buildNewName(tags, ext);
  const newPath = path.join(IMG_DIR, newName);
  console.log(`  新名: ${newName}`);

  if (dryRun) {
    console.log('  [DRY RUN] 未实际改名');
    return { name: fname, ok: true, newName, tags };
  }

  let finalName = newName;
  let finalPath = newPath;
  let counter = 1;
  while (fs.existsSync(finalPath)) {
    const dot = finalName.lastIndexOf('.');
    finalName = `${finalName.slice(0, dot)}_${counter}${finalName.slice(dot)}`;
    finalPath = path.join(IMG_DIR, finalName);
    counter++;
  }

  try {
    fs.renameSync(filePath, finalPath);
    console.log(`  [OK] → ${finalName}`);
    return { name: fname, ok: true, newName: finalName, tags };
  } catch (e) {
    console.log(`  [!] 改名失败: ${e.message}`);
    return { name: fname, ok: false };
  }
}

async function main() {
  console.log('');
  console.log('╔══════════════════════════════════╗');
  console.log('║   ✦ 风月AI 图片文件名清洗工具    ║');
  console.log('╚══════════════════════════════════╝');

  const args = {};
  for (let i = 2; i < process.argv.length; i++) {
    const a = process.argv[i];
    if (a === '--help' || a === '-h') {
      console.log('\n用法: node scripts/tag_images.js [选项]\n');
      console.log('选项:');
      console.log('  --name <file>     处理单张图片');
      console.log('  --dry-run         预览不改名');
      console.log('  --force           强制覆盖已有标签');
      console.log('  --vision          调用 AI vision 识图标注（需 API Key）');
      console.log('  --help, -h        显示帮助\n');
      console.log('说明: 不加 --name 时自动处理全部未标注图片\n');
      process.exit(0);
    } else if (a === '--all') { /* default behavior, ignore */ }
    else if (a === '--dry-run') args.dryRun = true;
    else if (a === '--force') args.force = true;
    else if (a === '--vision') args.vision = true;
    else if (a.startsWith('--name=')) args.name = a.split('=')[1];
    else if (a === '--name' && i + 1 < process.argv.length) args.name = process.argv[++i];
  }

  if (!fs.existsSync(IMG_DIR)) {
    console.error(`[!] 图库目录不存在: ${IMG_DIR}`);
    process.exit(1);
  }

  const settings = loadSettings();
  if (args.vision && !settings.api_key) {
    console.error('[!] --vision 需要配置 API Key（studio_settings.json）');
    process.exit(1);
  }

  const allFiles = fs.readdirSync(IMG_DIR).sort();
  let targets = [];

  if (args.name) {
    if (allFiles.includes(args.name)) {
      targets = [args.name];
    } else {
      console.error(`[!] 文件不存在: ${args.name}`);
      process.exit(1);
    }
  } else {
    for (const f of allFiles) {
      const ext = path.extname(f).toLowerCase();
      if (ALLOWED_EXT.has(ext)) {
        if (!args.force && f.includes(TAGGED_MARKER)) continue;
        targets.push(f);
      }
    }
  }

  if (targets.length === 0) {
    console.log('[!] 没有需要处理的图片');
    process.exit(1);
  }

  const mode = args.vision ? 'AI 识图（本地模型）' : '文件名清洗';
  console.log(`共 ${targets.length} 张图片（模式: ${mode}）\n`);

  let ok = 0;

  if (args.vision) {
    findPython();
    // Batch call Python vision tagger
    const { execSync } = require('child_process');
    const pyScript = path.join(SCRIPTS_DIR, 'vision_tagger.py');
    const imgPaths = targets.map(f => path.join(IMG_DIR, f));
    const cmd = `"${pyScript}" ${imgPaths.map(p => `"${p}"`).join(' ')}`;

    try {
      const out = execSync(`"${PYTHON}" ${cmd}`, {
        encoding: 'utf-8',
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env, HF_ENDPOINT: 'https://hf-mirror.com' },
        timeout: 300000,
      });
      const lines = out.trim().split('\n').filter(Boolean);
      for (const line of lines) {
        const result = JSON.parse(line);
        const fname = result.path;
        const tags = result.tags;
        const filePath = path.join(IMG_DIR, fname);
        console.log(`\n  处理: ${fname}`);
        console.log(`  → AI 标签: ${tags || '无'}`);

        if (!tags) {
          const fallbackTags = extractTags(fname);
          console.log(`  → 回退到文件名清洗: ${fallbackTags}`);
          const dot = fname.lastIndexOf('.');
          const ext = dot >= 0 ? fname.slice(dot) : '';
          const newName = buildNewName(fallbackTags, ext);
          const newPath = path.join(IMG_DIR, newName);
          console.log(`  新名: ${newName}`);
          if (!args.dryRun) { try { fs.renameSync(filePath, newPath); console.log(`  [OK]`); ok++; } catch(e) { console.log(`  [!] ${e.message}`); } }
          else { ok++; }
          continue;
        }

        const dot = fname.lastIndexOf('.');
        const ext = dot >= 0 ? fname.slice(dot) : '';
        const newName = buildNewName(tags, ext);
        const newPath = path.join(IMG_DIR, newName);
        console.log(`  新名: ${newName}`);

        if (args.dryRun) { ok++; continue; }

        let finalName = newName;
        let finalPath = newPath;
        let counter = 1;
        while (fs.existsSync(finalPath)) {
          const d = finalName.lastIndexOf('.');
          finalName = `${finalName.slice(0, d)}_${counter}${finalName.slice(d)}`;
          finalPath = path.join(IMG_DIR, finalName);
          counter++;
        }
        try { fs.renameSync(filePath, finalPath); console.log(`  [OK] → ${finalName}`); ok++; }
        catch(e) { console.log(`  [!] 改名失败: ${e.message}`); }
      }
    } catch (e) {
      console.log(`\n[!] AI 识图失败: ${e.message}`);
    }
  } else {
    for (const f of targets) {
      const r = await processImage(f, settings, args.dryRun, args.force, false);
      if (r.ok) ok++;
    }
  }

  console.log(`\n${'='.repeat(40)}`);
  console.log(`${args.dryRun ? '预览' : '处理'}完成: ${ok}/${targets.length}`);
  console.log(`图库: ${IMG_DIR}`);
}

main().catch(e => {
  console.error('错误:', e.message);
  process.exit(1);
});
