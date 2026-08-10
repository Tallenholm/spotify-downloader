import { cp, mkdir, rm } from 'node:fs/promises';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const target = resolve(root, 'spotdl/web/static');
await rm(target, { recursive: true, force: true });
await mkdir(resolve(target, 'assets'), { recursive: true });
await cp(resolve(import.meta.dirname, 'out/assets'), resolve(target, 'assets'), { recursive: true });
await cp(resolve(import.meta.dirname, 'index.html'), resolve(target, 'index.html'));
await cp(resolve(import.meta.dirname, 'styles.css'), resolve(target, 'assets/styles.css'));
console.log(`Built premium UI -> ${target}`);
