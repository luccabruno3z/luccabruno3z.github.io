# Checklist de smoke test — Bot V2 (Components V2 + Fases 0/1/2/4)

> Marcá `[x]` lo que funciona, dejá notas en la columna **Notas** con lo que veas raro.
> Validado localmente: compile + imports + serialización de componentes. Falta el render/interacción reales en Discord.

## 0. Deploy
- [ ] Redeploy del bot con `requirements-bot.txt` nuevo (instala **discord.py 2.7**) — _Notas:_
- [ ] El bot arranca sin errores en los logs (carga todos los cogs, incl. `polls`) — _Notas:_
- [ ] Slash commands sincronizados — _Notas:_

## 0.b Application Emojis (one-time, owner)
- [ ] Correr `-setup_emojis` una vez — _Notas:_
- [ ] Reporta "X subidos / Y ya existían / Z fallaron" sin errores — _Notas:_
- [ ] Los logos de clan aparecen en rankings (antes rotos: `141`, `WD`) — _Notas:_
- [ ] El logo animado de **ADG** (gif) se ve animado — _Notas:_

## 1. Player card (`-stats <jugador>`) — Components V2
- [ ] Tarjeta con **borde de color según el tier** del jugador — _Notas:_
- [ ] **Logo del clan** arriba a la derecha (Thumbnail) — _Notas:_
- [ ] Stats en texto (Combate / Volumen / Performance) legibles en **móvil** — _Notas:_
- [ ] **Barras nativas** del desglose (sin imagen) — _Notas:_
- [ ] Próximo tier / advertencias / rondas destacadas cuando aplica — _Notas:_
- [ ] Botón **📊 Detalles demo** (efímero) — _Notas:_
- [ ] Botón **📈 Historial** (gráfico, efímero) — _Notas:_
- [ ] Botón **⚔️ Comparar** (abre modal) — _Notas:_
- [ ] Botón **🎯 Últimas rondas** (efímero, lista de player_rounds) — _Notas:_
- [ ] **Persistencia**: tras redeploy/reinicio, los botones **siguen funcionando** (DynamicItem) — _Notas:_
- [ ] En modo `prstats` aparecen solo Historial + Comparar (sin demo) — _Notas:_

## 2. Leaderboard (`-top_periodo` / `-top_dia` / etc.) — V2 + selects
- [ ] Tarjeta con ranking (medallas top 3) — _Notas:_
- [ ] **Select de Período** (Hoy/Semana/Mes/Todo) cambia el ranking in-place — _Notas:_
- [ ] **Select de Métrica** (Kills/KD/Score/Revives/Teamwork) reordena in-place — _Notas:_
- [ ] El período/métrica actual queda **marcado** en el select — _Notas:_
- [ ] Solo quien invocó puede usar los selects — _Notas:_
- [ ] Período vacío muestra mensaje amable (no error) — _Notas:_

## 4. Polls + app instalable
- [ ] `-encuesta ¿pregunta? | op1 | op2 | op3` crea una **poll nativa** — _Notas:_
- [ ] `-mvp juan, pedro, ana` crea poll de MVP (7 días) — _Notas:_
- [ ] Instalar el bot como **app de usuario** y usar un comando en **DM**/otro server — _Notas:_
      (requiere activar "User Install" en el Developer Portal)

---

## 2.b Compare a V2 (`-compare <j1> <j2>`) — jugador vs jugador
- [ ] Tarjeta morada con el head-to-head métrica por métrica — _Notas:_
- [ ] Veredicto (quién gana cuántas categorías) — _Notas:_
- [ ] Aviso de muestra chica si algún jugador tiene <50 rondas — _Notas:_
- [ ] Botón **🔁 Invertir** rehace la comparación al revés — _Notas:_
- [ ] Botones **Demo \<jugador\>** por cada uno (persistentes) — _Notas:_
- [ ] El **radar** (segundo mensaje) sigue apareciendo — _Notas:_
- [ ] Clan vs clan / jugador vs clan: siguen en embed (sin migrar) — _Notas:_

---

## Fase 3 — evaluación (no implementado, por decisión de diseño)
Tras revisarlos contra este bot, el ROI es bajo o es decisión de producto:

- **es-419 (localización)**: el bot **ya está en español** (nombres y
  descripciones). Localizar a es-419 es redundante y de alto esfuerzo (requiere
  `name_localizations` por comando) para ganancia casi nula. **Recomiendo no hacerlo.**
  _¿Igual lo querés? [ ]_
- **Ephemeral por defecto (amplio)**: es una **decisión de producto** (¿querés
  que `-stats` sea privado o compartible en el canal?). La infra ya está: las
  acciones de las cards responden efímeras. Si me decís qué comandos querés
  privados, los aplico. _Comandos a hacer efímeros: __________ [ ]_
- **Modales con Select**: valor marginal; útil solo si rehacemos algún flujo de
  filtros. _[ ]_

## Otros diferidos opcionales
- **Compare clan-vs-clan / jugador-vs-clan a V2**: las ramas de clan siguen en
  embed (más complejas). _¿Avanzar? [ ]_

## Bugs / feedback general
> (escribí acá lo que notes)
-
-
