# Brota — Contrato compartido app ↔ backend (v1)

La app Flutter funciona 100 % sin conexión; el backend es opcional y, cuando
está configurado, aporta: cuentas con JWT, sincronización sin duplicados
(RNF-07), compañero fantasma real, muro moderado y contenido administrable.

Base: `/api/v1`. JSON UTF-8. Fechas `aaaa-mm-dd`, instantes ISO-8601.
Autenticación: `Authorization: Bearer <jwt>` (HS256, expira en 7 días, `sub` =
id de usuario, `rol` = `usuario` | `administrador`).
Errores: `{"detail": "<mensaje en español>"}` con 400/401/403/404/409/422.

## 1. Salud
- `GET /salud` → `{"estado":"ok","version":"1.0.0"}` (sin auth).

## 2. Cuentas (CU-01, CU-02)
- `POST /auth/registro`
  `{"correo","password","nombre","fecha_nac":"aaaa-mm-dd","acepta_privacidad":true,"consentimiento_tutor":false}`
  Reglas: correo válido y único (409 si existe); password ≥ 6; nombre no vacío;
  `acepta_privacidad` debe ser true; edad < 13 → 422 "Brota es para personas de 13 años o más";
  13–17 → `consentimiento_tutor` obligatorio (422 si falta); > 35 se permite
  (la respuesta incluye `"aviso_edad": true`).
  Contraseña con bcrypt. → 201 `{"token","usuario":{"id","nombre","rol"},"aviso_edad":bool}`
- `POST /auth/login` `{"correo","password"}` → 200 mismo cuerpo (sin aviso_edad) | 401.
- `GET /auth/yo` (auth) → `{"id","correo","nombre","rol","fecha_nac"}`.

## 3. Sincronización idempotente (RNF-07)
- `POST /sync` (auth)
  `{"eventos":[{"id":"<uuid generado en el cliente>","tipo":"<tipo>","fecha":"<iso>","datos":{...}}]}`
  Tipos: `animo` {dia, animo 1-5, energia 1-3}, `cumplimiento` {dia, actividad_id, titulo, xp, hora 0-23},
  `descanso` {dia}, `escudo` {dia}, `tarea` {id, titulo, categoria, esfuerzo},
  `perfil` {avatar, mascota, mascota_nombre, xp_total}, `riesgo` {dia, riesgo "ALTO"|"BAJO", puntaje}.
  Desconocido → se rechaza ese evento (va en `rechazados`), no todo el lote.
  Unicidad (usuario_id, id). `datos` se guarda **cifrado** con Fernet (clave `BROTA_CLAVE_DATOS`) — RNF-02.
  → 200 `{"aceptados":[ids],"duplicados":[ids],"rechazados":[ids]}`. Reenviar el mismo lote no duplica.
- `GET /sync/resumen` (auth) → `{"total":n,"por_tipo":{"animo":n,...},"ultimo":"<iso>|null"}`.

## 4. Compañero fantasma anónimo
- `POST /fantasma/senales` (auth) `{}` → 201 `{"id"}`. Una señal = "completé mi misión de hoy".
  Máximo 1 por usuario por día (si ya existe, 200 con la misma id).
- `GET /fantasma/senales` (auth) → `[{"id","hace_minutos"}]` hasta 10 señales de las últimas 24 h
  de **otros** usuarios, sin datos personales, a las que aún no reaccioné.
- `POST /fantasma/reacciones` (auth) `{"senal_id","reaccion":"bien_hecho"|"tu_puedes"|"sigue_asi"}`
  → 201. Una reacción por usuario y señal (409 si se repite). No a la propia señal (400).
- `GET /fantasma/recibidas` (auth) → `[{"id","reaccion","fecha"}]` reacciones a mis señales no
  entregadas aún; al responder se marcan como entregadas.

## 5. Muro de aliento moderado (CU-14, CU-23, CU-24)
- `GET /comunidad/frases` → frases predefinidas `[{"id","texto"}]` (sin auth).
- `GET /comunidad/publicaciones` (auth) → `[{"id","texto","fecha","es_logro"}]` visibles, más recientes primero (máx 50).
- `POST /comunidad/publicaciones` (auth) `{"frase_id"}` o `{"logro": {"racha":n,"xp":n}}` → 201. Texto libre no se acepta.
- `POST /comunidad/publicaciones/{id}/reportes` (auth) `{"motivo"}` → 201. Con 3 reportes la publicación se oculta sola.
- Admin: `GET /admin/reportes` → pendientes `[{"id","publicacion_id","texto","motivo","fecha"}]`;
  `POST /admin/reportes/{id}/resolver` `{"accion":"ocultar"|"mantener"}`.

## 6. Clasificador por diccionario de palabras clave
- `POST /mensajes/clasificar` `{"texto"}` → `{"categoria":"motivadora"|"neutra"|"no_apta"|"riesgo","estilo":"implicito"|"explicito","puntaje":n,"coincidencias":[{"termino","categoria","peso"}]}`
- `GET /mensajes/diccionario` → el JSON del diccionario.
- Algoritmo (idéntico en app y backend): normalizar (minúsculas; quitar acentos con NFD; todo lo que no sea
  a-z/0-9 → espacio; separar por espacios). Recorrer términos ordenados por número de palabras descendente
  (empates: orden del archivo, categoría por categoría). Para cada término buscar la primera posición donde
  todas sus palabras coinciden (palabra con `*` = prefijo) y ninguna palabra del texto está ya usada;
  marcar esas palabras como usadas; cada término cuenta máximo una vez. Luego aplicar `reglas` del JSON.

## 7. Contenido administrable (CU-06, CU-11, CU-12, CU-18, CU-19)
- Público: `GET /contenido/catalogo`, `GET /contenido/mensajes`, `GET /contenido/directorio`.
- Admin (rol administrador): `POST/PUT/DELETE /admin/catalogo[/{id}]`, `/admin/mensajes[/{id}]`, `/admin/directorio[/{id}]`.
  Al crear un mensaje se clasifica con el diccionario: si no es `motivadora` → 422 con la clasificación.
- Semilla: el mismo catálogo, mensajes y directorio que trae la app (ver `semilla.json`).

## 8. Perceptrón de riesgo de procrastinación (idéntico en app y backend)
Entradas x (todas en 0..1), calculadas al cierre del día d para predecir d+1:
| # | Entrada | Cálculo |
|---|---|---|
| x1 | constancia7 | días con al menos un cumplimiento en los 7 días que terminan en d / 7 |
| x2 | hora_media | hora promedio (0-23) de los cumplimientos de esos 7 días / 23; sin datos → 0.5 |
| x3 | escudos_semana | escudos usados en la semana de d, mín(1, n/1) |
| x4 | fin_de_semana | 1 si d+1 es sábado o domingo |
| x5 | fantasma7 | reacciones enviadas+recibidas en los 7 días / 7, tope 1 |
| x6 | animo | (último ánimo registrado − 1) / 4; sin registro → 0.5 |
| x7 | energia | (última energía − 1) / 2; sin registro → 0.5 |
| x8 | activo_hoy | 1 si hubo cumplimiento en d |

Pesos iniciales (propuesta, arranque en frío): w = [-1.2, 0.4, 0.6, 0.3, -0.4, -0.8, -0.6, -1.0], b = 1.4.
Salida: z = w·x + b; ALTO si z > 0, si no BAJO. Puntaje = z (redondeado a 2 decimales).
Aprendizaje (regla del perceptrón, η = 0.1): al cerrar d+1 se conoce y = 1 si NO hubo cumplimiento en d+1
(riesgo real), 0 si sí. Con ŷ = 1 si z>0: wᵢ ← wᵢ + η(y−ŷ)xᵢ; b ← b + η(y−ŷ).
El modelo no diagnostica nada: solo adapta la dificultad del día siguiente.
- Backend: `POST /riesgo/prediccion` (auth) `{"x":[8 números]}` o `{}` → si viene vacío lo calcula de los
  eventos sincronizados del usuario. → `{"riesgo","puntaje","entradas":[...],"pesos":[...],"sesgo"}`.
  `POST /riesgo/entrenar` (auth) reentrena con el historial sincronizado del usuario y guarda sus pesos.
