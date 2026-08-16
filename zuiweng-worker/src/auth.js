// JWT (HS256, WebCrypto) + PBKDF2 密码哈希
const enc = new TextEncoder();
const b64 = (s) => btoa(s).replace(/=+$/, '');
const unb64 = (s) => atob(s);

export async function hashPassword(pwd, salt) {
  const key = await crypto.subtle.importKey('raw', enc.encode(pwd), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', salt: enc.encode(salt), iterations: 100000, hash: 'SHA-256' },
    key, 256);
  return b64(String.fromCharCode(...new Uint8Array(bits)));
}

export function randomSalt() {
  const a = new Uint8Array(16);
  crypto.getRandomValues(a);
  return Array.from(a, b => b.toString(16).padStart(2, '0')).join('');
}

export async function signToken(payload, secret, expSec = 7 * 86400) {
  const header = b64(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const now = Math.floor(Date.now() / 1000);
  const body = b64(JSON.stringify({ ...payload, iat: now, exp: now + expSec }));
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(`${header}.${body}`));
  return `${header}.${body}.${b64(String.fromCharCode(...new Uint8Array(sig)))}`;
}

export async function verifyToken(token, secret) {
  try {
    const [h, p, s] = token.split('.');
    if (!h || !p || !s) return null;
    const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']);
    const ok = await crypto.subtle.verify('HMAC', key, Uint8Array.from(unb64(s), c => c.charCodeAt(0)), enc.encode(`${h}.${p}`));
    if (!ok) return null;
    const payload = JSON.parse(unb64(p));
    if (payload.exp < Date.now() / 1000) return null;
    return payload;
  } catch { return null; }
}