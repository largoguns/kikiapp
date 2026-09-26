/* Componente Alpine del dashboard de escritorio. */
function dashboard() {
  const K = window.Kiki;

  const RESUMEN_VACIO = {
    global: {},
    totales: { kiki: 0, no_kiki: 0, gayola: 0, marea: 0, total: 0, ratio_kiki: null },
    promedios: { calidad: null, tiempo: null },
    periodo: { desde: null, hasta: null },
    distribucion_calidad: [],
    distribucion_tiempo: [],
    por_dia_semana: [],
    mayor_sequia: {},
    ciclo: {},
  };

  /* Las instancias de Chart.js se guardan fuera del estado reactivo: su grafo
     de objetos es circular y envolverlo en proxies de Alpine desborda la pila. */
  const instancias = new Map();

  const FORM_VACIO = () => ({
    fecha: K.hoyISO(),
    hasta: '',
    rango: false,
    tipo: 'Kiki',
    pretexto: '',
    motivacion: '',
    calidad: 3,
    tiempo: 2,
    observaciones: '',
  });

  return {
    Kiki: K,
    cargando: false,

    filtros: {
      year: String(new Date().getFullYear()),
      tipo: '',
      motivacion: '',
      pretexto: '',
      min_calidad: '',
      min_tiempo: '',
      q: '',
    },
    opciones: { tipos: K.TIPOS, motivaciones: [], pretextos: [], years: [] },

    resumen: RESUMEN_VACIO,
    meses: [],
    anios: [],
    reparto: { motivacion: [], pretexto: [] },

    dias: {},
    modoCalendario: 'mes',
    anioCalendario: new Date().getFullYear(),
    mesCalendario: new Date().getMonth() + 1,

    registros: [],
    totalRegistros: 0,
    limite: 50,
    orden: { campo: 'fecha', dir: 'desc' },
    columnasTabla: [
      { campo: 'fecha', titulo: 'Fecha' },
      { campo: 'tipo', titulo: 'Tipo' },
      { campo: 'pretexto', titulo: 'Pretexto' },
      { campo: 'motivacion', titulo: 'Motivación' },
      { campo: 'calidad', titulo: 'Calidad' },
      { campo: 'tiempo', titulo: 'Tiempo' },
      { campo: 'observaciones', titulo: 'Observaciones' },
    ],

    tablas: {},
    vistaTabla: {},

    ultimaImportacion: null,
    importacion: {
      abierto: false,
      archivo: null,
      modo: 'combinar',
      informe: null,
      error: '',
      enviando: false,
    },
    modal: { abierto: false, id: null, form: FORM_VACIO(), error: '', guardando: false, delDia: [] },
    aviso: { texto: '', tipo: 'info' },

    // --- arranque ---------------------------------------------------------
    async init() {
      window.KikiCharts.aplicarTema(window.Chart);
      await this.cargarOpciones();
      await this.recargar();
      await this.cargarImportacion();
      window.addEventListener('resize', () => this.redibujar());
    },

    parametros(extra) {
      const filtros = this.filtros;
      return K.queryString(
        Object.assign(
          {
            year: filtros.year,
            tipo: filtros.tipo,
            motivacion: filtros.motivacion,
            pretexto: filtros.pretexto,
            min_calidad: filtros.min_calidad,
            min_tiempo: filtros.min_tiempo,
            q: filtros.q,
          },
          extra || {}
        )
      );
    },

    async cargarOpciones() {
      try {
        const datos = await K.api.get('/api/options');
        this.opciones = datos;
        if (this.filtros.year && !datos.years.includes(Number(this.filtros.year))) {
          this.filtros.year = datos.years.length ? String(datos.years[0]) : '';
        }
        if (datos.years.length && !datos.years.includes(this.anioCalendario)) {
          this.anioCalendario = datos.years[0];
        }
      } catch (error) {
        this.notificar(error.message, 'error');
      }
    },

    async recargar() {
      this.cargando = true;
      this.limite = 50;
      if (this.filtros.year) this.anioCalendario = Number(this.filtros.year);
      try {
        await Promise.all([
          this.cargarResumen(),
          this.cargarSeries(),
          this.cargarCalendario(),
          this.cargarRegistros(),
        ]);
        this.redibujar();
      } catch (error) {
        this.notificar(error.message, 'error');
      } finally {
        this.cargando = false;
      }
    },

    async cargarResumen() {
      this.resumen = await K.api.get(`/api/stats/summary${this.parametros()}`);
    },

    async cargarSeries() {
      const [mensual, anual, reparto] = await Promise.all([
        K.api.get(`/api/stats/monthly${this.parametros({ year: this.anioCalendario })}`),
        K.api.get(`/api/stats/yearly${this.parametros({ year: '' })}`),
        K.api.get(`/api/stats/breakdown${this.parametros()}`),
      ]);
      this.meses = mensual.meses;
      this.anios = anual.anios;
      this.reparto = reparto;
    },

    async cargarCalendario() {
      const parametros = this.parametros({
        year: this.anioCalendario,
        month: this.modoCalendario === 'mes' ? this.mesCalendario : '',
      });
      const datos = await K.api.get(`/api/stats/calendar${parametros}`);
      this.dias = datos.dias;
    },

    async cargarRegistros() {
      const parametros = this.parametros({
        sort: this.orden.campo,
        order: this.orden.dir,
        limit: this.limite,
        offset: 0,
      });
      const pagina = await K.api.get(`/api/events${parametros}`);
      this.registros = pagina.items;
      this.totalRegistros = pagina.total;
    },

    async cargarMas() {
      this.limite += 100;
      await this.cargarRegistros();
    },

    ordenarPor(campo) {
      if (this.orden.campo === campo) {
        this.orden.dir = this.orden.dir === 'asc' ? 'desc' : 'asc';
      } else {
        this.orden = { campo, dir: 'desc' };
      }
      this.cargarRegistros();
    },

    limpiarFiltros() {
      this.filtros = {
        year: '', tipo: '', motivacion: '', pretexto: '',
        min_calidad: '', min_tiempo: '', q: '',
      };
      this.recargar();
    },

    // --- gráficos ---------------------------------------------------------
    get tarjetasGrafico() {
      const ambito = this.etiquetaAmbito;
      return [
        { id: 'mensual', titulo: `Evolución mensual · ${this.anioCalendario}`,
          subtitulo: 'Registros por mes y tipo' },
        { id: 'anual', titulo: 'Histórico por año',
          subtitulo: 'Todos los años (el filtro de año no aplica aquí)' },
        { id: 'distribucion', titulo: 'Distribución de valoraciones',
          subtitulo: `Cuántos Kikis en cada nivel 0–4 · ${ambito}` },
        { id: 'motivacion', titulo: 'Por motivación',
          subtitulo: `De quién surgió la iniciativa · ${ambito}` },
        { id: 'pretexto', titulo: 'Por pretexto',
          subtitulo: `Seis principales, el resto agrupado · ${ambito}` },
        { id: 'semana', titulo: 'Por día de la semana',
          subtitulo: `Reparto semanal · ${ambito}` },
      ];
    },

    especificaciones() {
      const G = window.KikiCharts;
      return {
        mensual: G.mensual(this.meses),
        anual: G.anual(this.anios),
        distribucion: G.distribucion(
          this.resumen.distribucion_calidad,
          this.resumen.distribucion_tiempo
        ),
        motivacion: G.reparto(this.reparto.motivacion),
        pretexto: G.reparto(this.reparto.pretexto, 6),
        semana: G.semana(this.resumen.por_dia_semana),
      };
    },

    redibujar() {
      const especificaciones = this.especificaciones();
      Object.entries(especificaciones).forEach(([id, spec]) => {
        this.tablas[id] = spec.tabla;
        const lienzo = document.getElementById(`chart-${id}`);
        if (!lienzo) return;
        const existente = instancias.get(id);
        if (existente) {
          // Actualizar en lugar de recrear: sin parpadeo de esqueleto.
          existente.data = spec.config.data;
          existente.options = spec.config.options;
          existente.update();
        } else {
          instancias.set(id, new window.Chart(lienzo, spec.config));
        }
      });
    },

    // --- calendario -------------------------------------------------------
    get tituloCalendario() {
      return this.modoCalendario === 'mes'
        ? `${K.MESES_LARGOS[this.mesCalendario - 1]} ${this.anioCalendario}`
        : String(this.anioCalendario);
    },

    get etiquetaAmbito() {
      return this.filtros.year ? `Año ${this.filtros.year}` : 'Histórico';
    },

    moverCalendario(paso) {
      if (this.modoCalendario === 'anio') {
        this.anioCalendario += paso;
      } else {
        let mes = this.mesCalendario + paso;
        if (mes < 1) { mes = 12; this.anioCalendario -= 1; }
        if (mes > 12) { mes = 1; this.anioCalendario += 1; }
        this.mesCalendario = mes;
      }
      this.cargarCalendario();
      this.cargarSeries().then(() => this.redibujar());
    },

    irAHoy() {
      const ahora = new Date();
      this.anioCalendario = ahora.getFullYear();
      this.mesCalendario = ahora.getMonth() + 1;
      this.cargarCalendario();
    },

    decorar(fecha) {
      const dia = this.dias[fecha];
      const vacio = {
        fondo: K.COLOR.surface2,
        fondoSolido: K.COLOR.surface2,
        tinta: K.COLOR.ink3,
        marcas: [],
        titulo: `${K.fechaCorta(fecha)} · sin actividad`,
      };
      if (!dia) return vacio;

      // Si el día tiene varios tipos, manda el primero de este orden.
      const tipos = dia.tipos;
      const dominante = ['Kiki', 'Gayola', 'No Kiki', 'Marea']
        .find((tipo) => tipos.includes(tipo));
      // Sólo el Kiki se valora, así que sólo él lleva rampa de intensidad.
      const fondo = dominante === 'Kiki'
        ? K.intensidadKiki(Math.max(dia.calidad_max, dia.tiempo_max))
        : K.COLOR_POR_TIPO[dominante];

      const detalle = dia.eventos
        .map((evento) =>
          evento.tipo === 'Kiki'
            ? `Kiki (calidad ${evento.calidad}, tiempo ${evento.tiempo})`
            : evento.tipo
        )
        .join(' · ');

      return {
        fondo,
        fondoSolido: K.mezclarSobre(fondo),
        tinta: K.tintaSobre(fondo),
        marcas: tipos.filter((tipo) => tipo !== dominante).map((tipo) => K.COLOR_POR_TIPO[tipo]),
        titulo: `${K.fechaCorta(fecha)} · ${detalle}`,
      };
    },

    celdasDeMes(anio, mes) {
      const primerDia = new Date(Date.UTC(anio, mes - 1, 1));
      const desplazamiento = (primerDia.getUTCDay() + 6) % 7; // semana empieza en lunes
      const diasDelMes = new Date(Date.UTC(anio, mes, 0)).getUTCDate();
      const total = Math.ceil((desplazamiento + diasDelMes) / 7) * 7;
      const hoy = K.hoyISO();

      const celdas = [];
      for (let indice = 0; indice < total; indice += 1) {
        const numero = indice - desplazamiento + 1;
        const fuera = numero < 1 || numero > diasDelMes;
        if (fuera) {
          celdas.push({
            clave: `${anio}-${mes}-x${indice}`, fuera: true, dia: '',
            fondo: 'transparent', fondoSolido: K.COLOR.surface, tinta: K.COLOR.ink3,
            marcas: [], titulo: '',
          });
          continue;
        }
        const fecha = `${anio}-${String(mes).padStart(2, '0')}-${String(numero).padStart(2, '0')}`;
        celdas.push(
          Object.assign(
            { clave: fecha, fecha, dia: numero, fuera: false, hoy: fecha === hoy },
            this.decorar(fecha)
          )
        );
      }
      return celdas;
    },

    get cuadriculaMes() {
      return this.celdasDeMes(this.anioCalendario, this.mesCalendario);
    },

    get cuadriculaAnio() {
      return Array.from({ length: 12 }, (_, indice) => {
        const mes = indice + 1;
        const prefijo = `${this.anioCalendario}-${String(mes).padStart(2, '0')}`;
        const delMes = Object.values(this.dias).filter((dia) => dia.fecha.startsWith(prefijo));
        const kikis = delMes.filter((dia) => dia.tipos.includes('Kiki')).length;
        return {
          numero: mes,
          nombre: K.MESES_LARGOS[indice],
          resumen: `${kikis} kiki${kikis === 1 ? '' : 's'}`,
          celdas: this.celdasDeMes(this.anioCalendario, mes),
        };
      });
    },

    // --- registros --------------------------------------------------------
    nuevoRegistro(fecha) {
      this.modal = {
        abierto: true,
        id: null,
        form: Object.assign(FORM_VACIO(), fecha ? { fecha } : {}),
        error: '',
        guardando: false,
        delDia: fecha ? (this.dias[fecha] ? this.dias[fecha].eventos : []) : [],
      };
    },

    abrirDia(fecha) {
      const dia = this.dias[fecha];
      if (dia && dia.eventos.length === 1) {
        this.editarRegistro(dia.eventos[0]);
      } else {
        this.nuevoRegistro(fecha);
      }
    },

    editarRegistro(registro) {
      this.modal = {
        abierto: true,
        id: registro.id,
        form: {
          fecha: registro.fecha,
          hasta: '',
          rango: false,
          tipo: registro.tipo,
          pretexto: registro.pretexto || '',
          motivacion: registro.motivacion || '',
          calidad: registro.calidad,
          tiempo: registro.tiempo,
          observaciones: registro.observaciones || '',
        },
        error: '',
        guardando: false,
        delDia: (this.dias[registro.fecha] ? this.dias[registro.fecha].eventos : [])
          .filter((evento) => evento.id !== registro.id),
      };
    },

    get usaRango() {
      const form = this.modal.form;
      return !this.modal.id && form.rango && form.tipo === 'Marea'
        && !!form.hasta && form.hasta > form.fecha;
    },

    cerrarModal() {
      this.modal.abierto = false;
    },

    async guardarRegistro() {
      this.modal.guardando = true;
      this.modal.error = '';
      const form = this.modal.form;
      const cuerpo = {
        fecha: form.fecha,
        tipo: form.tipo,
        calidad: form.calidad,
        tiempo: form.tiempo,
        pretexto: form.pretexto || null,
        motivacion: form.motivacion || null,
        observaciones: form.observaciones || null,
      };
      try {
        if (this.modal.id) {
          await K.api.put(`/api/events/${this.modal.id}`, cuerpo);
          this.notificar('Registro guardado');
        } else if (this.usaRango) {
          const r = await K.api.post('/api/events/rango',
            Object.assign({}, cuerpo, { hasta: form.hasta }));
          this.notificar(r.omitidos
            ? `${r.creados} días añadidos, ${r.omitidos} ya estaban`
            : `${r.creados} días añadidos`);
        } else {
          await K.api.post('/api/events', cuerpo);
          this.notificar('Registro guardado');
        }
        this.modal.abierto = false;
        await this.cargarOpciones();
        await this.recargar();
      } catch (error) {
        this.modal.error = error.message;
      } finally {
        this.modal.guardando = false;
      }
    },

    async borrarRegistro(registro) {
      if (!window.confirm(`¿Borrar el registro del ${K.fechaCorta(registro.fecha)}?`)) return;
      try {
        await K.api.del(`/api/events/${registro.id}`);
        this.notificar('Registro eliminado');
        await this.recargar();
      } catch (error) {
        this.notificar(error.message, 'error');
      }
    },

    // --- importación ------------------------------------------------------
    async cargarImportacion() {
      try {
        const estado = await K.api.get('/api/import');
        this.ultimaImportacion = estado.ultima_importacion;
      } catch (error) {
        this.ultimaImportacion = null;
      }
    },

    abrirImportacion() {
      this.importacion = {
        abierto: true, archivo: null, modo: 'combinar',
        informe: null, error: '', enviando: false,
      };
    },

    elegirArchivo(evento) {
      this.importacion.archivo = evento.target.files[0] || null;
      this.importacion.informe = null;
      this.importacion.error = '';
    },

    async enviarImportacion(simular) {
      if (!this.importacion.archivo) return;
      if (!simular && this.importacion.modo === 'reemplazar') {
        const aviso = 'Esto BORRA todos los registros actuales antes de importar. '
          + '¿Continuar?';
        if (!window.confirm(aviso)) return;
      }

      this.importacion.enviando = true;
      this.importacion.error = '';
      const cuerpo = new FormData();
      cuerpo.append('archivo', this.importacion.archivo);
      cuerpo.append('modo', this.importacion.modo);
      cuerpo.append('simular', simular ? 'true' : 'false');

      try {
        const respuesta = await fetch('/api/import', { method: 'POST', body: cuerpo });
        const datos = await respuesta.json();
        if (!respuesta.ok) throw new Error(datos.detail || `Error ${respuesta.status}`);
        this.importacion.informe = datos;
        if (!simular) {
          this.notificar(`${datos.insertadas} registros importados`);
          this.ultimaImportacion = null;
          await this.cargarImportacion();
          await this.cargarOpciones();
          await this.recargar();
        }
      } catch (error) {
        // Un TypeError aquí es un corte de red: la petición no llegó o se
        // perdió la respuesta, así que no se sabe si el servidor escribió.
        // En modo combinar reintentar es seguro, porque es idempotente.
        this.importacion.error = error instanceof TypeError
          ? 'No se pudo contactar con el servidor, o se perdió la respuesta. '
            + (this.importacion.modo === 'combinar'
              ? 'Vuelve a pulsar Importar: en modo combinar repetirlo no duplica nada.'
              : 'Comprueba el estado de los datos antes de reintentar en modo reemplazar.')
          : error.message;
      } finally {
        this.importacion.enviando = false;
      }
    },

    notificar(texto, tipo) {
      this.aviso = { texto, tipo: tipo || 'info' };
      window.clearTimeout(this._avisoTemporizador);
      this._avisoTemporizador = window.setTimeout(() => { this.aviso.texto = ''; }, 3500);
    },
  };
}
