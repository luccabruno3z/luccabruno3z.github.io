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

## Pendiente / diferido (no incluido en este deploy)
Lo dejé fuera a propósito para no romper cosas que no puedo probar en vivo:

- **Fase 2 — `-compare` a V2**: sigue funcionando con embed + chart. Migrar a
  `comparison_card` es interacción-pesado (3 ramas + botón invertir); lo dejo
  para cuando podamos probar en vivo. _¿Avanzar? [ ]_
- **Fase 3 — Localización es-419**: evaluado, **valor marginal** (los comandos
  ya están en español). Se puede hacer si querés nombres slash localizados. _[ ]_
- **Fase 3 — Ephemeral por defecto (amplio)**: aplicado ya a las acciones de la
  player card. Hacerlo global es delicado (los comandos por prefijo no soportan
  efímero). _Definir alcance [ ]_
- **Fase 3 — Modales con Select**: menor; útil si rehacemos filtros. _[ ]_

## Bugs / feedback general
> (escribí acá lo que notes)
-
-
