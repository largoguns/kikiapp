/* Copia las librerías de node_modules a static/vendor.

   Se sirven desde el propio contenedor en lugar de un CDN: la PWA tiene que
   arrancar sin red y la imagen no debe depender de terceros en tiempo de uso. */
import { copyFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

const raiz = resolve(import.meta.dirname, '..');
const destino = resolve(raiz, 'static/vendor');

const ARCHIVOS = [
  ['node_modules/alpinejs/dist/cdn.min.js', 'alpine.min.js'],
  ['node_modules/chart.js/dist/chart.umd.min.js', 'chart.umd.js'],
];

await mkdir(destino, { recursive: true });
for (const [origen, nombre] of ARCHIVOS) {
  await copyFile(resolve(raiz, origen), resolve(destino, nombre));
  console.log(`static/vendor/${nombre}`);
}
