#!/usr/bin/env node
/**
 * 风月AI 角色卡工作室 - 快捷配置启动脚本
 * 
 * 用法: node scripts/start.js
 * 
 * 功能:
 *   1. 检查 Python 环境和依赖
 *   2. 交互式配置 OpenAI Key 和账号
 *   3. 生成占位图片
 *   4. 启动 Flask Web 服务器
 *   5. 打开浏览器
 */

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const http = require('http');

const SCRIPTS_DIR = __dirname;
const ROOT_DIR = path.resolve(SCRIPTS_DIR, '..');
const SETTINGS_FILE = path.join(SCRIPTS_DIR, 'studio_settings.json');
const IMG_DIR = path.join(ROOT_DIR, 'generated_imgs');
let PYTHON = 'python';  // updated after user selects

// ============================================================
// 工具函数
// ============================================================

function q(s) { return s.includes(' ') ? `"${s}"` : s; }

function findAllPython() {
  const seen = new Set();
  const found = [];
  const candidates = [
    'python3', 'python',
    'D:\\Program Files\\bin\\python.exe',
    'D:\\Program Files\\Python312\\python.exe',
    'D:\\Program Files\\Python310\\python.exe',
    'D:\\Program Files\\Python313\\python.exe',
    'C:\\Program Files\\Python312\\python.exe',
    'C:\\Program Files\\Python310\\python.exe',
    'C:\\Program Files\\Python313\\python.exe',
    'C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python312\\python.exe',
    'C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python310\\python.exe',
    'C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\python.exe',
  ];
  for (const cmd of candidates) {
    const norm = cmd.toLowerCase().replace(/"/g, '');
    if (seen.has(norm)) continue;
    seen.add(norm);
    try {
      const out = execSync(`"${cmd}" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"`, { encoding: 'utf-8', stdio: 'pipe' }).trim();
      const hasPip = execSync(`"${cmd}" -m pip --version 2>nul`, { encoding: 'utf-8', stdio: 'pipe' }).trim();
      found.push({ cmd: q(cmd), version: out, pip: !hasPip.includes('No module') });
    } catch {}
  }
  return found;
}

function run(cmd, opts = {}) {
  const stdio = opts.silent ? 'pipe' : 'inherit';
  return execSync(cmd, { encoding: 'utf-8', stdio, ...opts });
}

function runCapture(cmd) {
  try {
    return execSync(cmd, { encoding: 'utf-8', stdio: 'pipe' }).trim();
  } catch (e) {
    return e.stderr ? e.stderr.toString() : '';
  }
}

function checkPkg(name) {
  try {
    run(`${PYTHON} -c "import ${name}"`, { silent: true });
    return true;
  } catch { return false; }
}

function ask(query) {
  return new Promise(resolve => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(query, ans => { rl.close(); resolve(ans.trim()); });
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function loadSettings() {
  try { return JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf-8')); } catch { return {}; }
}

function saveSettings(data) {
  const old = loadSettings();
  Object.assign(old, data);
  fs.writeFileSync(SETTINGS_FILE, JSON.stringify(old, null, 2), 'utf-8');
  console.log('  ✓ 设置已保存');
}

// ============================================================
// 步骤 1: 检查环境
// ============================================================

async function checkEnvironment() {
  console.log('\n━━━━ 环境检查 ━━━━');

  const allPython = findAllPython();
  if (allPython.length === 0) {
    console.error('  ✗ 未找到任何 Python，请安装 Python 3.10+');
    process.exit(1);
  }

  // Print available Pythons
  console.log('  找到以下 Python:');
  allPython.forEach((p, i) => {
    console.log(`    [${i}] ${p.cmd}  (v${p.version})  pip: ${p.pip ? '✓' : '✗'}`);
  });

  // Auto-select: prefer one with pip
  let selectedIndex = allPython.findIndex(p => p.pip);
  if (selectedIndex === -1) selectedIndex = 0;

  // Only ask if multiple choices
  if (allPython.length > 1) {
    const ans = await ask(`  选择 Python [0-${allPython.length - 1}] (默认 ${selectedIndex}): `);
    const n = parseInt(ans);
    if (!isNaN(n) && n >= 0 && n < allPython.length) selectedIndex = n;
  }

  const selected = allPython[selectedIndex];
  PYTHON = selected.cmd;
  console.log(`  → 使用: ${selected.cmd}`);

  if (!selected.pip) {
    console.log('  ! 所选 Python 没有 pip，尝试安装...');
    const out = runCapture(`${PYTHON} -m ensurepip --upgrade 2>&1`);
    if (out.includes('Error') || out.includes('No module')) {
      console.log('  ✗ 无法自动安装 pip。试试选择另一个 Python，或手动安装:');
      console.log(`    ${out.slice(0, 200)}`);
      process.exit(1);
    }
    console.log('  ✓ pip 安装成功');
  }

  // 依赖
  const required = [
    ['flask', 'Flask'],
    ['openai', 'openai'],
    ['playwright', 'playwright'],
    ['PIL', 'Pillow (PIL)'],
  ];
  const missing = required.filter(([m]) => !checkPkg(m)).map(([, n]) => n);
  
  if (missing.length > 0) {
    console.log(`  ! 缺少依赖: ${missing.join(', ')}`);
    const ans = await ask('  是否自动安装? (Y/n): ');
    if (ans.toLowerCase() !== 'n') {
      run(`${PYTHON} -m pip install flask openai playwright pillow`);
      // Install playwright browser
      try {
        run(`${PYTHON} -m playwright install chromium`, { silent: true });
        console.log('  ✓ Playwright Chromium 已安装');
      } catch { console.log('  ! Playwright 浏览器安装失败，可手动运行: python -m playwright install chromium'); }
    } else {
      console.log('  ! 请手动安装缺少的依赖');
      process.exit(1);
    }
  } else {
    console.log('  ✓ 所有 Python 依赖已就绪');
  }

  // Playwright browser
  try {
    run(`${PYTHON} -c "from playwright.sync_api import sync_playwright; sync_playwright().__enter__().chromium.launch(headless=True).close()"`, { silent: true });
    console.log('  ✓ Playwright Chromium 可用');
  } catch {
    console.log('  ! Playwright Chromium 未安装');
    const ans = await ask('  是否安装? (Y/n): ');
    if (ans.toLowerCase() !== 'n') {
      run(`${PYTHON} -m playwright install chromium`);
    }
  }
}

// ============================================================
// 步骤 2: 配置
// ============================================================

async function configure() {
  console.log('\n━━━━ 配置向导 ━━━━');
  const cfg = loadSettings();

  if (cfg.api_key && cfg.email) {
    console.log('  已有配置:');
    console.log(`    API: ${cfg.api_url || 'https://api.openai.com/v1'}`);
    console.log(`    Model: ${cfg.model || 'gpt-4o-mini'}`);
    console.log(`    账号: ${cfg.email}`);
    const ans = await ask('  使用现有配置? (Y/n): ');
    if (ans.toLowerCase() !== 'n') return cfg;
  }

  // API Key
  if (!cfg.api_key) {
    const key = await ask('  OpenAI 兼容 API Key (留空跳过): ');
    if (key) cfg.api_key = key;
  }

  // API URL
  if (!cfg.api_url) {
    const url = await ask(`  API 接口地址 (默认 https://api.openai.com/v1): `);
    if (url) cfg.api_url = url;
  }
  if (!cfg.api_url) cfg.api_url = 'https://api.openai.com/v1';

  // Model
  if (!cfg.model) {
    const model = await ask(`  模型名称 (默认 gpt-4o-mini): `);
    if (model) cfg.model = model;
  }
  if (!cfg.model) cfg.model = 'gpt-4o-mini';

  // Account
  if (!cfg.email) {
    const email = await ask('  风月账号邮箱: ');
    if (email) cfg.email = email;
  }
  if (!cfg.password && cfg.email) {
    const pw = await ask('  风月账号密码: ');
    if (pw) cfg.password = pw;
  }

  // Images paths (use defaults if not set)
  const coverDefault = path.join(IMG_DIR, 'cover.png');
  if (!cfg.cover) cfg.cover = coverDefault;
  if (!cfg.chat_bg) cfg.chat_bg = path.join(IMG_DIR, 'chat_bg.png');
  if (!cfg.mobile_bg) cfg.mobile_bg = path.join(IMG_DIR, 'mobile_bg.png');
  console.log('  ✓ 图片路径已设（自动生成占位图）');

  saveSettings(cfg);
  return cfg;
}

// ============================================================
// 步骤 3: 生成占位图片
// ============================================================

async function generateImages(cfg) {
  console.log('\n━━━━ 图片检查 ━━━━');
  
  const images = [
    { key: 'cover', label: '封面', size: '400x300' },
    { key: 'chat_bg', label: '聊天背景', size: '800x450' },
    { key: 'mobile_bg', label: '移动背景', size: '360x640' },
  ];

  let needsGen = false;
  for (const img of images) {
    const p = cfg[img.key];
    if (!p || !fs.existsSync(p)) {
      needsGen = true;
      console.log(`  ! ${img.label} (${img.size}) 不存在: ${p || '未配置'}`);
    } else {
      console.log(`  ✓ ${img.label}: ${p}`);
    }
  }

  if (needsGen && checkPkg('PIL')) {
    const ans = await ask('  是否自动生成占位图片? (Y/n): ');
    if (ans.toLowerCase() !== 'n') {
      if (!fs.existsSync(IMG_DIR)) fs.mkdirSync(IMG_DIR, { recursive: true });
      
      const { execSync } = require('child_process');
      const script = `
from PIL import Image, ImageDraw
import os, json
os.makedirs('${IMG_DIR.replace(/\\/g, '\\\\')}', exist_ok=True)
cfg_path = '${SETTINGS_FILE.replace(/\\/g, '\\\\')}'
with open(cfg_path, 'r', encoding='utf-8') as f: cfg = json.load(f)
for key, size, color, text in [
  ('cover', (400,300), '#4A90D9', '封面'),
  ('chat_bg', (800,450), '#2C3E50', '聊天背景'),
  ('mobile_bg', (360,640), '#34495E', '移动背景'),
]:
  p = cfg.get(key, '')
  if not p: p = os.path.join('${IMG_DIR.replace(/\\/g, '\\\\')}', key + '.png')
  if os.path.exists(p):
    print(f'  exists: {p}')
    continue
  img = Image.new('RGB', size, color)
  d = ImageDraw.Draw(img)
  b = d.textbbox((0,0), text)
  d.text(((size[0]-(b[2]-b[0]))/2, (size[1]-(b[3]-b[1]))/2), text, fill='white')
  img.save(p)
  cfg[key] = p
  print(f'  generated: {p}')
with open(cfg_path, 'w', encoding='utf-8') as f: json.dump(cfg, f, ensure_ascii=False, indent=2)
`;
      const tmpScript = path.join(require('os').tmpdir(), 'gen_imgs.py');
      fs.writeFileSync(tmpScript, script, 'utf-8');
      run(`${PYTHON} "${tmpScript}"`);
      try { fs.unlinkSync(tmpScript); } catch {}
      
      // Reload cfg
      Object.assign(cfg, loadSettings());
    }
  }
}

// ============================================================
// 步骤 4: 启动服务器
// ============================================================

async function startServer(cfg) {
  console.log('\n━━━━ 启动服务器 ━━━━');
  
  const serverScript = path.join(SCRIPTS_DIR, 'character_studio.py');
  if (!fs.existsSync(serverScript)) {
    console.error(`  ✗ 未找到 ${serverScript}`);
    process.exit(1);
  }

  // Check if already running
  const isRunning = await new Promise(resolve => {
    const req = http.get('http://127.0.0.1:5000/api/settings', res => {
      res.resume();
      resolve(true);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => { req.destroy(); resolve(false); });
  });

  if (isRunning) {
    console.log('  ✓ 服务器已在运行 http://127.0.0.1:5000');
    return;
  }

  console.log('  启动 Flask 服务器...');
  const proc = spawn(PYTHON, [serverScript], {
    cwd: SCRIPTS_DIR,
    stdio: 'pipe',
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });

  proc.stdout.on('data', d => process.stdout.write(d));
  proc.stderr.on('data', d => process.stderr.write(d));

  // Wait for server
  for (let i = 0; i < 30; i++) {
    await sleep(1000);
    try {
      await new Promise((resolve, reject) => {
        const req = http.get('http://127.0.0.1:5000/', res => { res.resume(); resolve(); });
        req.on('error', reject);
        req.setTimeout(2000, () => { req.destroy(); reject(); });
      });
      console.log('  ✓ 服务器已就绪!');
      return proc;
    } catch {}
  }
  console.error('  ✗ 服务器启动超时');
  process.exit(1);
}

// ============================================================
// 步骤 5: 打开浏览器
// ============================================================

function openBrowser() {
  console.log('\n━━━━ 启动浏览器 ━━━━');
  const url = 'http://127.0.0.1:5000';
  
  try {
    const platform = process.platform;
    if (platform === 'win32') {
      run(`start "" "${url}"`, { silent: true });
    } else if (platform === 'darwin') {
      run(`open "${url}"`, { silent: true });
    } else {
      run(`xdg-open "${url}"`, { silent: true });
    }
    console.log(`  ✓ 浏览器已打开: ${url}`);
  } catch {
    console.log(`  请手动打开: ${url}`);
  }
}

// ============================================================
// 主流程
// ============================================================

async function main() {
  console.log('');
  console.log('╔══════════════════════════════════╗');
  console.log('║   ✦ 风月AI 角色卡工作室          ║');
  console.log('║   快捷配置启动工具                ║');
  console.log('╚══════════════════════════════════╝');

  await checkEnvironment();
  const cfg = await configure();
  await generateImages(cfg);
  const proc = await startServer(cfg);
  openBrowser();

  console.log('\n━━━━ 启动完成 ━━━━');
  console.log('  工作室地址: http://127.0.0.1:5000');
  console.log('  按 Ctrl+C 停止服务器\n');

  // Keep running
  if (proc) {
    process.on('SIGINT', () => {
      console.log('\n  正在停止服务器...');
      proc.kill();
      process.exit(0);
    });
  }
}

main().catch(e => {
  console.error('错误:', e.message);
  process.exit(1);
});
