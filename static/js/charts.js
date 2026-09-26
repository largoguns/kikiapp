/* Definición de los gráficos del dashboard.

   Cada constructor devuelve { config, tabla }: la configuración de Chart.js y
   su gemela en tabla, para que ningún valor quede accesible sólo por color o
   sólo por tooltip.

   La Marea no se pinta en ninguna serie: es un bloque de siete días o más al
   mes, así que aplastaría la escala de los encuentros sin aportar nada que no
   cuente ya el calendario y la tarjeta de ciclo. */
(function (global) {
  'use strict';

  const C = global.Kiki.COLOR;

  // --- Especificación de marcas -------------------------------------------
  const BARRA = {
    maxBarThickness: 24,
    borderRadius: { topLeft: 4, topRight: 4, bottomLeft: 0, bottomRight: 0 },
    borderSkipped: 'bottom',
    // El hueco entre barras contiguas lo hace la superficie, no un borde.
    categoryPercentage: 0.72,
    barPercentage: 0.88,
  };

  const BARRA_HORIZONTAL = Object.assign({}, BARRA, {
    borderRadius: { topLeft: 0, topRight: 4, bottomLeft: 0, bottomRight: 4 },
    borderSkipped: 'left',
  });

  function aplicarTema(Chart) {
    Chart.defaults.font.family =
      'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    Chart.defaults.font.size = 11;
    Chart.defaults.color = C.ink3;
    Chart.defaults.animation.duration = 260;
    Chart.defaults.maintainAspectRatio = false;
  }

  function leyenda() {
    return {
      display: true,
      position: 'top',
      align: 'end',
      labels: {
        usePointStyle: true,
        pointStyle: 'circle',
        boxWidth: 8,
        boxHeight: 8,
        padding: 16,
        // El texto va en tinta; la identidad la lleva el punto de color.
        color: C.ink2,
        font: { size: 11, weight: '600' },
      },
    };
  }

  function tooltip(sufijo) {
    return {
      backgroundColor: C.surface2,
      borderColor: C.axis,
      borderWidth: 1,
      titleColor: C.ink,
      bodyColor: C.ink2,
      padding: 10,
      cornerRadius: 8,
      usePointStyle: true,
      boxPadding: 4,
      callbacks: sufijo
        ? {
            label: (item) =>
              ` ${item.dataset.label}: ${item.formattedValue}${sufijo}`,
          }
        : undefined,
    };
  }

  function ejeValor(titulo) {
    return {
      beginAtZero: true,
      border: { color: C.axis },
      grid: { color: C.grid, drawTicks: false, lineWidth: 1 },
      ticks: {
        color: C.ink3,
        precision: 0,
        padding: 8,
        font: { size: 10 },
      },
      title: titulo
        ? { display: true, text: titulo, color: C.ink3, font: { size: 10 } }
        : undefined,
    };
  }

  function ejeCategoria() {
    return {
      border: { color: C.axis },
      grid: { display: false },
      ticks: { color: C.ink3, padding: 6, font: { size: 10 } },
    };
  }

  function opcionesBase(opciones) {
    return Object.assign(
      {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        layout: { padding: { top: 4 } },
        plugins: { legend: leyenda(), tooltip: tooltip() },
      },
      opciones || {}
    );
  }

  function serie(label, color, datos, extra) {
    return Object.assign(
      { label, data: datos, backgroundColor: color, hoverBackgroundColor: color },
      BARRA,
      extra || {}
    );
  }

  function tabla(columnas, filas) {
    return { columnas, filas };
  }

  // --- Gráficos ------------------------------------------------------------

  /** Totales por mes: Kiki vs No Kiki vs Marea. */
  function mensual(meses) {
    const etiquetas = meses.map((mes) => mes.etiqueta);
    return {
      config: {
        type: 'bar',
        data: {
          labels: etiquetas,
          datasets: [
            serie('Kiki', C.kiki, meses.map((mes) => mes.kiki)),
            serie('No Kiki', C.nokiki, meses.map((mes) => mes.no_kiki)),
            serie('Gayola', C.gayola, meses.map((mes) => mes.gayola)),
          ],
        },
        options: opcionesBase({
          scales: { x: ejeCategoria(), y: ejeValor('registros') },
        }),
      },
      tabla: tabla(
        ['Mes', 'Kiki', 'No Kiki', 'Gayola', 'Calidad media', 'Tiempo medio'],
        meses.map((mes) => [
          mes.etiqueta,
          mes.kiki,
          mes.no_kiki,
          mes.gayola,
          mes.calidad_media ?? '—',
          mes.tiempo_medio ?? '—',
        ])
      ),
    };
  }

  /** Histórico por año. */
  function anual(anios) {
    return {
      config: {
        type: 'bar',
        data: {
          labels: anios.map((a) => String(a.anio)),
          datasets: [
            serie('Kiki', C.kiki, anios.map((a) => a.kiki)),
            serie('No Kiki', C.nokiki, anios.map((a) => a.no_kiki)),
            serie('Gayola', C.gayola, anios.map((a) => a.gayola)),
          ],
        },
        options: opcionesBase({
          scales: { x: ejeCategoria(), y: ejeValor('registros') },
        }),
      },
      tabla: tabla(
        ['Año', 'Kiki', 'No Kiki', 'Gayola', 'Calidad media', 'Tiempo medio'],
        anios.map((a) => [
          a.anio, a.kiki, a.no_kiki, a.gayola,
          a.calidad_media ?? '—', a.tiempo_medio ?? '—',
        ])
      ),
    };
  }

  /** Cuántos Kikis hay en cada nivel 0-4 de calidad y de tiempo. */
  function distribucion(calidad, tiempo) {
    const etiquetas = calidad.map((punto) => String(punto.valor));
    return {
      config: {
        type: 'bar',
        data: {
          labels: etiquetas,
          datasets: [
            serie('Calidad', C.kiki, calidad.map((p) => p.total)),
            // Segundo contexto secuencial → siguiente tono categórico.
            serie('Tiempo', C.marea, tiempo.map((p) => p.total)),
          ],
        },
        options: opcionesBase({
          scales: {
            x: Object.assign(ejeCategoria(), {
              title: { display: true, text: 'valoración (0–4)', color: C.ink3,
                       font: { size: 10 } },
            }),
            y: ejeValor('kikis'),
          },
        }),
      },
      tabla: tabla(
        ['Valoración', 'Kikis por calidad', 'Kikis por tiempo'],
        calidad.map((punto, indice) => [
          punto.valor, punto.total, tiempo[indice] ? tiempo[indice].total : 0,
        ])
      ),
    };
  }

  /** Reparto por una dimensión (motivación o pretexto), en barras horizontales. */
  function reparto(items, limite) {
    const ordenados = items.slice(0, limite || items.length);
    const resto = items.slice(ordenados.length);
    if (resto.length) {
      ordenados.push({
        clave: 'Otros',
        kiki: resto.reduce((suma, item) => suma + item.kiki, 0),
        no_kiki: resto.reduce((suma, item) => suma + item.no_kiki, 0),
        total: resto.reduce((suma, item) => suma + item.total, 0),
        calidad_media: null,
      });
    }

    return {
      config: {
        type: 'bar',
        data: {
          labels: ordenados.map((item) => item.clave),
          datasets: [
            Object.assign(
              { label: 'Kiki', data: ordenados.map((i) => i.kiki),
                backgroundColor: C.kiki },
              BARRA_HORIZONTAL
            ),
            Object.assign(
              { label: 'No Kiki', data: ordenados.map((i) => i.no_kiki),
                backgroundColor: C.nokiki },
              BARRA_HORIZONTAL
            ),
          ],
        },
        options: opcionesBase({
          indexAxis: 'y',
          scales: {
            x: ejeValor('registros'),
            y: Object.assign(ejeCategoria(), { ticks: { color: C.ink2, font: { size: 11 } } }),
          },
        }),
      },
      tabla: tabla(
        ['Categoría', 'Kiki', 'No Kiki', 'Total', 'Calidad media'],
        ordenados.map((item) => [
          item.clave, item.kiki, item.no_kiki, item.total,
          item.calidad_media ?? '—',
        ])
      ),
    };
  }

  /** Actividad por día de la semana. */
  function semana(dias) {
    return {
      config: {
        type: 'bar',
        data: {
          labels: dias.map((dia) => dia.dia),
          datasets: [
            serie('Kiki', C.kiki, dias.map((d) => d.kiki)),
            serie('No Kiki', C.nokiki, dias.map((d) => d.no_kiki)),
            serie('Gayola', C.gayola, dias.map((d) => d.gayola)),
          ],
        },
        options: opcionesBase({
          scales: { x: ejeCategoria(), y: ejeValor('registros') },
        }),
      },
      tabla: tabla(
        ['Día', 'Kiki', 'No Kiki', 'Gayola'],
        dias.map((d) => [d.dia, d.kiki, d.no_kiki, d.gayola])
      ),
    };
  }

  global.KikiCharts = {
    aplicarTema,
    mensual,
    anual,
    distribucion,
    reparto,
    semana,
  };
})(window);
