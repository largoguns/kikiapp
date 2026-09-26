/* Rasteriza los iconos SVG a los PNG que necesitan Android e iOS. */
import { mkdir, readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import sharp from 'sharp';

const raiz = resolve(import.meta.dirname, '..');
const salidas = [
  { fuente: 'static/icons/icon.svg', destino: 'static/icons/icon-192.png', tamano: 192 },
  { fuente: 'static/icons/icon.svg', destino: 'static/icons/icon-512.png', tamano: 512 },
  { fuente: 'static/icons/icon.svg', destino: 'static/icons/apple-touch-icon.png', tamano: 180 },
  { fuente: 'static/icons/icon-maskable.svg', destino: 'static/icons/icon-maskable-512.png', tamano: 512 },
];

for (const { fuente, destino, tamano } of salidas) {
  const svg = await readFile(resolve(raiz, fuente));
  const rutaDestino = resolve(raiz, destino);
  await mkdir(dirname(rutaDestino), { recursive: true });
  await sharp(svg, { density: 384 }).resize(tamano, tamano).png({ compressionLevel: 9 }).toFile(rutaDestino);
  console.log(`${destino} (${tamano}px)`);
}
