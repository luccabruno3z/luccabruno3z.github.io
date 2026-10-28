# Runbook

Qué hacer cuando algo falla o hay que operar el sistema. Para entender las piezas,
ver [ARQUITECTURA.md](ARQUITECTURA.md).

## Accesos necesarios

| Pieza | Dónde | Quién |
|---|---|---|
| Scraper | GitHub Actions del repo, workflow *Actualización de estadísticas PR* | Admin del repo |
| Web | GitHub Pages (rama `main`) | Admin del repo |
| Bot | Railway: proyecto del bot, servicio con volumen en `/data` | Dueño del proyecto en Railway |
| Discord | Developer Portal de la aplicación (token, emojis) | Dueño del bot |

Secretos del repo: `GH_PAT` (push del scraper) y `DISCORD_WEBHOOK` (aviso cuando
falla). Variable de Railway: `DISCORD_TOKEN`.

---

## Scraper

**Frecuencia:** cron en `.github/workflows/daily_update.yml`. Hoy corre cada 10 minutos
para vaciar el backlog de demos; el ritmo normal es cada hora (`0 * * * *`).
`concurrency` evita que dos corridas se pisen.

### Correrlo a mano
GitHub → Actions → *Actualización de estadísticas PR* → **Run workflow**. Localmente:

```bash
pip install -r requirements-scraper.txt
```

```bash
python -m scraper
```

### Falló una corrida
Llega un aviso al webhook de Discord con el link al run.
1. Abrí el run y fijate qué paso falló.
2. **"Verificar conectividad con PRStats"** no corta el workflow. Si después falla
   *Ejecutar scraper*, lo más común es que PRStats esté caído o bloqueando: se
   reintenta solo en la próxima corrida.
3. **Timeout de *Ejecutar scraper*** (50 min): hay demasiadas demos pendientes. Bajá
   `MAX_DEMOS_PER_RUN` o `DEMO_TIME_BUDGET` en `scraper/config.py`.
4. **Falla *Validar output JSON*:** `all_players_clusters.json` quedó corrupto. Como
   ese paso corta el workflow antes del commit, el archivo malo no llega a publicarse.
   Corré el scraper localmente para ver el error.
5. **Falla el push:** otra corrida o un commit manual se adelantó. El workflow hace
   `pull --rebase` antes del push, y la próxima corrida lo vuelve a intentar.

### Un servidor de demos no responde
Los hosts inestables se postergan solos y se reintentan con backoff. Para sacar uno de
forma permanente, quitalo de las fuentes en `scraper/config.py`.

---

## Bot en Railway

### Ver estado y logs
En Railway, abrí el servicio y entrá en **Deployments** → el último → **Logs**. Un
arranque sano muestra que se cargaron los 12 cogs y la cantidad de Application Emojis.

### Deploy
Cada push a `main` dispara un build con nixpacks (`nixpacks.toml`, que corre
`python -m bot`). `.dockerignore` deja fuera de la imagen `graphs/`, `web/`,
`scraper/` y el resto de lo que el bot no usa.

> **Falla con `context deadline exceeded` al exportar la imagen.** Casi siempre es
> que algo grande entró en la imagen. Revisá que `.dockerignore` siga excluyendo
> `graphs/**` y cualquier carpeta pesada nueva. Con el `.dockerignore` correcto, la
> copia tarda menos de un segundo y la exportación unos 20 s.

### Dependencias
Railway instala `requirements.txt`, que tiene **solo lo que usa el bot y con versión
fija**. Así un redeploy no trae versiones nuevas por sorpresa. Para actualizar, por
ejemplo, discord.py:
1. Cambiá la versión en `requirements.txt`.
2. Probalo local (`pip install -r requirements.txt` y `python -m bot`).
3. Pusheá y mirá el log de arranque: muestra la versión de Python y de discord.py, y
   avisa si algún cog no cargó (`Cogs sin cargar: …`). El bot arranca igual sin ese cog.

### Configuración recomendada del servicio
- **App sleeping desactivado.** Si Railway duerme el servicio, un bot de Discord no
  se despierta solo, porque nadie le hace pedidos HTTP.
- **Restart policy "Always".** Si el proceso se cae, Railway lo vuelve a levantar sin
  límite de reintentos.

### Rollback
Railway → Deployments → elegí el último deploy sano → **Redeploy**. Después revertí
el commit en `main`; si no, el próximo push vuelve a desplegar la versión rota.

### Los vínculos o la configuración se borraron después de un deploy
El estado vive en `DATA_DIR`. Verificá que:
1. el servicio tenga un **volumen montado en `/data`**;
2. el log de arranque diga `Datos persistentes en: /data` y no una ruta dentro de
   `bot/data/`, que es efímera.

`RAILWAY_VOLUME_MOUNT_PATH` lo define Railway solo cuando hay volumen. Si querés otra
ruta, usá `BOT_DATA_DIR`.

### Las barras o los logos aparecen como `:tb_…:` o rotos
Faltan los Application Emojis. Corré `-setup_emojis` (solo el dueño del bot). Sube lo
que falte y saltea lo que ya existe.

### Los botones viejos no responden
Los componentes del perfil y del menú son `DynamicItem` y siguen andando después de
un reinicio. Si uno nuevo deja de responder, seguramente no se registró en
`bot/main.py`.

### El leaderboard semanal no se publicó
Se publica los lunes a las 10:00 UTC en los canales configurados con
`-set_leaderboard_channel` (se guardan en `automation.json`). Revisá que el canal
siga existiendo y que el bot tenga permiso para escribir ahí.

---

## Web

### No se ve un cambio
1. Fijate en Actions que el deploy de Pages (*pages build and deployment*) haya
   terminado.
2. Recarga forzada (Ctrl+F5). Ver [WEB.md](WEB.md#caché-y-service-worker).

### La página carga pero sin datos
Abrí la consola. Si las peticiones a `graphs/*.json` dan 404 o el JSON es inválido, el
problema está en el último commit del scraper: revertilo o volvé a correr el workflow.

---

## Escalamiento
Proyecto mantenido por W4RR10R: [Discord de Legión de Hierro](https://discord.gg/S9ugnuRVsD)
o luccabruno96@gmail.com.
