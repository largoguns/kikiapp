/* Componente Alpine de la PWA móvil: entrada rápida con cola offline. */
function movil() {
  const K = window.Kiki;
  const CLAVE_COLA = 'kiki.pendientes';

  const FORM_VACIO = () => ({
    fecha: K.hoyISO(),
    tipo: 'Kiki',
    pretexto: '',
    motivacion: '',
    calidad: 3,
    tiempo: 2,
    observaciones: '',
  });

  function leerCola() {
    try {
      return JSON.parse(window.localStorage.getItem(CLAVE_COLA) || '[]');
    } catch (error) {
      return [];
    }
  }

  function escribirCola(cola) {
    window.localStorage.setItem(CLAVE_COLA, JSON.stringify(cola));
  }

  return {
    Kiki: K,
    pestana: 'registrar',
    form: FORM_VACIO(),
    opciones: { tipos: K.TIPOS, motivaciones: ['Propia', 'Ajena', 'Ambos'], pretextos: [] },
    kpi: {},
    historial: [],
    pendientes: [],
    conexion: window.navigator.onLine,
    guardando: false,
    error: '',
    aviso: '',

    get ayer() {
      const fecha = new Date();
      fecha.setDate(fecha.getDate() - 1);
      const desplazado = new Date(fecha.getTime() - fecha.getTimezoneOffset() * 60000);
      return desplazado.toISOString().slice(0, 10);
    },

    async init() {
      this.pendientes = leerCola();
      window.addEventListener('online', () => {
        this.conexion = true;
        this.vaciarCola();
      });
      window.addEventListener('offline', () => { this.conexion = false; });

      await this.cargarOpciones();
      await this.cargarKpi();
      if (this.pendientes.length && this.conexion) await this.vaciarCola();
    },

    async cargarOpciones() {
      try {
        this.opciones = await K.api.get('/api/options');
      } catch (error) {
        /* Sin red se conservan las opciones por defecto. */
      }
    },

    async cargarKpi() {
      try {
        const resumen = await K.api.get('/api/stats/summary');
        this.kpi = resumen.global;
      } catch (error) {
        /* El KPI es informativo: si no hay red, se deja como esté. */
      }
    },

    async cargarHistorial() {
      try {
        const pagina = await K.api.get('/api/events?limit=50&sort=fecha&order=desc');
        this.historial = pagina.items;
      } catch (error) {
        this.notificar('Sin conexión: historial no disponible');
      }
    },

    cuerpo() {
      const esKiki = this.form.tipo === 'Kiki';
      return {
        fecha: this.form.fecha,
        tipo: this.form.tipo,
        pretexto: this.form.tipo === 'Marea' ? null : this.form.pretexto || null,
        motivacion: this.form.tipo === 'Marea' ? null : this.form.motivacion || null,
        calidad: esKiki ? this.form.calidad : 0,
        tiempo: esKiki ? this.form.tiempo : 0,
        observaciones: this.form.observaciones || null,
      };
    },

    async guardar() {
      this.guardando = true;
      this.error = '';
      const cuerpo = this.cuerpo();
      try {
        await K.api.post('/api/events', cuerpo);
        this.notificar('Guardado ✓');
        this.reiniciar();
        await this.cargarKpi();
        if (this.pestana === 'historial') await this.cargarHistorial();
      } catch (error) {
        if (error instanceof TypeError) {
          // Fallo de red: se encola y se reintenta al volver la conexión.
          this.pendientes = [...this.pendientes, cuerpo];
          escribirCola(this.pendientes);
          this.notificar('Sin conexión: guardado para enviar luego');
          this.reiniciar();
        } else {
          this.error = error.message;
        }
      } finally {
        this.guardando = false;
      }
    },

    async vaciarCola() {
      const cola = leerCola();
      if (!cola.length) return;
      const fallidos = [];
      for (const cuerpo of cola) {
        try {
          await K.api.post('/api/events', cuerpo);
        } catch (error) {
          if (error instanceof TypeError) fallidos.push(cuerpo);
          // Un rechazo de validación se descarta: reintentarlo fallaría igual.
        }
      }
      this.pendientes = fallidos;
      escribirCola(fallidos);
      const enviados = cola.length - fallidos.length;
      if (enviados > 0) {
        this.notificar(`${enviados} registro${enviados === 1 ? '' : 's'} sincronizado${enviados === 1 ? '' : 's'}`);
        await this.cargarKpi();
      }
    },

    async borrar(registro) {
      if (!window.confirm('¿Borrar este registro?')) return;
      try {
        await K.api.del(`/api/events/${registro.id}`);
        this.historial = this.historial.filter((item) => item.id !== registro.id);
        await this.cargarKpi();
        this.notificar('Eliminado');
      } catch (error) {
        this.notificar(error.message);
      }
    },

    reiniciar() {
      const fecha = this.form.fecha;
      this.form = Object.assign(FORM_VACIO(), { fecha });
      this.error = '';
    },

    notificar(texto) {
      this.aviso = texto;
      window.clearTimeout(this._temporizador);
      this._temporizador = window.setTimeout(() => { this.aviso = ''; }, 2600);
    },
  };
}
