/* Utilidades compartidas por el dashboard y la PWA: cliente de API, formato
   y los tokens de color de la paleta validada. */
(function (global) {
  'use strict';

  const TIPOS = ['Kiki', 'No Kiki', 'Marea'];

  const COLOR = {
    kiki: '#199e70',
    nokiki: '#d95926',
    marea: '#9085e9',
    surface: '#14141a',
    surface2: '#1c1c24',
    ink: '#f6f7f9',
    ink2: '#b9bcc6',
    ink3: '#8b8f9a',
    grid: '#262631',
    axis: '#373845',
  };

  const COLOR_POR_TIPO = {
    'Kiki': COLOR.kiki,
    'No Kiki': COLOR.nokiki,
    'Marea': COLOR.marea,
  };

  const CLASE_POR_TIPO = {
    'Kiki': 'chip-kiki',
    'No Kiki': 'chip-nokiki',
    'Marea': 'chip-marea',
  };

  /* Rampa secuencial de un solo tono (verde Kiki) para la intensidad del
     calendario: 0 = casi fundido con la superficie, 4 = tono pleno. */
  const RAMPA_KIKI = [
    'rgba(25, 158, 112, 0.30)',
    'rgba(25, 158, 112, 0.46)',
    'rgba(25, 158, 112, 0.62)',
    'rgba(25, 158, 112, 0.80)',
    'rgba(25, 158, 112, 1)',
  ];

  function intensidadKiki(nivel) {
    return RAMPA_KIKI[Math.max(0, Math.min(4, nivel | 0))];
  }


  /* Elige tinta clara u oscura sobre un relleno concreto, mezclando primero
     el alfa contra la superficie: así una etiqueta dentro de una celda de
     color siempre supera el contraste, sea cual sea el nivel de la rampa. */
  function _componentes(color) {
    const rgba = color.match(/rgba?\(([^)]+)\)/);
    if (rgba) {
      const partes = rgba[1].split(',').map((valor) => parseFloat(valor));
      return { r: partes[0], g: partes[1], b: partes[2], a: partes.length > 3 ? partes[3] : 1 };
    }
    const hex = parseInt(color.replace('#', ''), 16);
    return { r: (hex >> 16) & 255, g: (hex >> 8) & 255, b: hex & 255, a: 1 };
  }

  function _luminancia(r, g, b) {
    const canal = (valor) => {
      const normalizado = valor / 255;
      return normalizado <= 0.03928
        ? normalizado / 12.92
        : Math.pow((normalizado + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
  }

  function _contraste(a, b) {
    const claro = Math.max(a, b);
    const oscuro = Math.min(a, b);
    return (claro + 0.05) / (oscuro + 0.05);
  }

  function tintaSobre(relleno, base) {
    const frente = _componentes(relleno);
    const fondo = _componentes(base || COLOR.surface);
    const mezcla = ['r', 'g', 'b'].map(
      (canal) => frente[canal] * frente.a + fondo[canal] * (1 - frente.a)
    );
    const luz = _luminancia(mezcla[0], mezcla[1], mezcla[2]);
    const conClaro = _contraste(luz, _luminancia(246, 247, 249));
    const conOscuro = _contraste(luz, _luminancia(13, 13, 16));
    return conOscuro > conClaro ? '#0d0d10' : COLOR.ink;
  }

  function mezclarSobre(relleno, base) {
    const frente = _componentes(relleno);
    const fondo = _componentes(base || COLOR.surface);
    const mezcla = ['r', 'g', 'b'].map((canal) =>
      Math.round(frente[canal] * frente.a + fondo[canal] * (1 - frente.a))
    );
    return `rgb(${mezcla[0]}, ${mezcla[1]}, ${mezcla[2]})`;
  }

  // --- Cliente HTTP --------------------------------------------------------
  async function request(url, options) {
    const response = await fetch(url, Object.assign({ headers: {} }, options));
    if (response.status === 204) return null;
    const cuerpo = await response.text();
    const datos = cuerpo ? JSON.parse(cuerpo) : null;
    if (!response.ok) {
      const detalle = datos && datos.detail;
      throw new Error(
        typeof detalle === 'string' ? detalle : `Error ${response.status}`
      );
    }
    return datos;
  }

  const api = {
    get: (url) => request(url, { method: 'GET' }),
    post: (url, body) =>
      request(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    put: (url, body) =>
      request(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    del: (url) => request(url, { method: 'DELETE' }),
  };

  // --- Formato -------------------------------------------------------------
  const MESES_LARGOS = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

  function hoyISO() {
    const ahora = new Date();
    const desplazado = new Date(ahora.getTime() - ahora.getTimezoneOffset() * 60000);
    return desplazado.toISOString().slice(0, 10);
  }

  function fechaCorta(iso) {
    if (!iso) return '—';
    const [a, m, d] = iso.split('-');
    return `${d}/${m}/${a}`;
  }

  function fechaLarga(iso) {
    if (!iso) return '—';
    const [a, m, d] = iso.split('-').map(Number);
    return `${d} de ${MESES_LARGOS[m - 1].toLowerCase()} de ${a}`;
  }

  function numero(valor, sufijo) {
    if (valor === null || valor === undefined || Number.isNaN(valor)) return '—';
    return `${valor}${sufijo || ''}`;
  }

  function queryString(params) {
    const busqueda = new URLSearchParams();
    Object.entries(params || {}).forEach(([clave, valor]) => {
      if (valor === null || valor === undefined || valor === '') return;
      if (Array.isArray(valor)) {
        valor.forEach((item) => item !== '' && busqueda.append(clave, item));
      } else {
        busqueda.append(clave, valor);
      }
    });
    const texto = busqueda.toString();
    return texto ? `?${texto}` : '';
  }

  global.Kiki = {
    TIPOS,
    COLOR,
    COLOR_POR_TIPO,
    CLASE_POR_TIPO,
    MESES_LARGOS,
    intensidadKiki,
    tintaSobre,
    mezclarSobre,
    api,
    hoyISO,
    fechaCorta,
    fechaLarga,
    numero,
    queryString,
  };
})(window);
