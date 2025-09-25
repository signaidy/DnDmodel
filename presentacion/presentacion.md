---
marp: true
theme: default
paginate: true
math: katex
---

# Simulador de Combate DnD – Modelo, Distribuciones y Resultados

**Autor:**  `Carlos Solares`  
**Profesor:** `Juan Andrés García Porres`  
**Repositorio / Código:** `https://github.com/signaidy/DnDmodel.git`

---

# Modelo y resultados: Simulador de Combate DnD

**Objetivo**

- Explicar cómo modelamos cada parte del combate.
- Precisar qué **distribución** usa cada componente.
- Responder preguntas clave sobre probabilidad de ganar bajo diferentes condiciones.
- Mostrar gráficas comparativas por monstruo y entre monstruos.

---

# Índice

1. Flujo del combate
2. Componentes y distribuciones
3. Métricas y estimación
4. Resultados (cómo leerlos)
5. Escenarios extra (Healer / Party completa)
6. Supuestos y limitaciones

---

# Flujo del combate

- **Estado inicial**: HP de combatientes, AC, modificadores.
- **Iniciativa**: orden aleatorio por ronda.
- **Turnos**:
  - Tiradas de ataque (hit / miss / crit).
  - Daño (mezcla con inflación en 0; críticos duplican dados).
  - Rasgos (regeneración, aliento, contraataque, invocación).
  - Habilidades de la party (Second Wind, Superioridad, Healer, Rogue, Wizard).
- **Fin**: cuando HP del monstruo ≤ 0 o la party es derrotada.
- **Repetir** muchas veces (Monte Carlo) para estimar probabilidades.

---

# Notación rápida

- $\mathrm{Unif}\{a,\dots,b\}$: uniforme discreta.
- $\mathrm{Bernoulli}(p)$: variable 0/1 con prob. $p$.
- $\mathrm{Geom}(p)$: nº de ensayos hasta el primer éxito (soporte $1,2,\dots$).
- $\mathbf{1}\{\cdot\}$: indicador.

---

# Dados base

**1dN**  
$X \sim \mathrm{Unif}\{1,\dots,N\}$  
$\mathbb{E}[X] = \tfrac{N+1}{2},\quad \mathrm{Var}(X) = \tfrac{N^2-1}{12}$

**Suma de $k$ dados 1dN**  
$\sum_{i=1}^{k} X_i$ (convolución de uniformes; forma poligonal)  
$\mathbb{E} = k\,\tfrac{N+1}{2},\quad \mathrm{Var} = k\,\tfrac{N^2-1}{12}$

---

# Iniciativa

Cada actor obtiene 2 llaves $U_1,U_2 \sim \mathrm{Unif}\{1,\dots,20\}$ i.i.d.; se ordena en forma lexicográfica descendente.

- Simetría: si hay $m$ actores, $P(\text{ser primero}) = 1/m$.
- Por equipos:

$$
P(\text{party first}) = \frac{M}{M+1}
$$

donde $M$ es nº de miembros de la party activos frente a 1 monstruo.  
Ej.: 1v1 → $1/2$; (Guerrero+Healer) vs 1 → $2/3$; party de 4 vs 1 → $4/5$.

---

# Tirada de ataque (d20) — sin ventaja

$R \sim \mathrm{Unif}\{1,\dots,20\}$

- Crítico natural: $P(\text{crit}) = 1/20$.
- Pifia natural: $P(\text{nat1}) = 1/20$.
- Éxito (ignorando nat1 y nat20):

$$
P(\text{hit}) = P(R=20) + P\big(R\in\{2,\dots,19\},\, R+\text{ATK\_MOD} \ge \text{AC}\big).
$$

---

# Tirada de ataque (d20) — con ventaja

$R=\max(R_1,R_2)$, con $R_i \sim \mathrm{Unif}\{1,\dots,20\}$ i.i.d.

- $P(R \le k) = \left(\frac{k}{20}\right)^2$,  
  $P(R=k) = \frac{2k-1}{400}$.
- Crítico: 

$$
P(\text{crit}) = 1 - \left(\frac{19}{20}\right)^2 = 0.0975.
$$

- Pifia natural: $P(\text{nat1}) = (1/20)^2 = 1/400$.

*(Desventaja sería $R=\min(R_1,R_2)$, análogo, pero no se implementó)*

---

# Dado de superioridad (Battlemaster)

$S \sim \mathrm{Unif}\{1,\dots,10\}$.  
Se usa sólo en “near-miss”: si faltan $n \in \{1,\dots,10\}$ puntos para impactar:

$$
\Delta P(\text{hit}) = \sum_{n=1}^{10} P(\text{necesito }n)\cdot P(S\ge n), 
\qquad
P(S \ge n) = \frac{11-n}{10}.
$$

---

# Daño de arma y mezcla (cero-inflado)

Sea $W$ el dado de arma (d4..d20).

$$
D = \begin{cases}
0 & \text{con prob. } 1-p_{\text{hit}}\\[4pt]
1dW+\text{DMG\_MOD} & \text{con prob. } p_{\text{hit}}-p_{\text{crit}}\\[4pt]
2dW+\text{DMG\_MOD} & \text{con prob. } p_{\text{crit}}
\end{cases}
$$

Algunos monstruos añaden dados extra en crítico.

---

# Healer (curación por hechizo)

- **Cure Wounds (nivel $L$)**:  
  $k=1+\max(0,L-1)$, $H\sim \sum_{i=1}^{k} 1d8 + \text{mod}$.
- **Healing Word (nivel $L$)**:  
  $k=1+\max(0,L-1)$, $H\sim \sum_{i=1}^{k} 1d4 + \text{mod}$.
- **Mass Healing Word (nivel $L\ge 3$)**:  
  $k=1+\max(0,L-3)$, $H\sim \sum 1d4 + \text{mod}$ por objetivo.
- **Second Wind (Guerrero)**:  
  $H\sim 1d10 + \text{nivel} \in \{11,\dots,20\}$.

La **elección** de hechizo y objetivo sigue una **política determinista** (según HP y slots).

---

# Rogue (Pícaro)

- To-hit: como antes (con posible ventaja por Steady Aim).
- Daño base: $1d8+\text{DMG\_MOD}$.
- Sneak Attack: $S$ dados d6 (aquí $S=5$); en crítico se **duplican todos** los dados:

$$
D_{\text{crit}} = 2d8 + 2S\cdot d6 + \text{DMG\_MOD}.
$$

- Uncanny Dodge: primer golpe **no crítico** recibido en la ronda se **divide a la mitad** (transformación determinista sobre la muestra).

---

# Wizard (Mago)

- **Magic Missile (nivel $L$)**: nº dardos $=L+2$.  
  Cada dardo $X \sim (1d4+1)$. Total $T=\sum X_i$.  
  Si hay resistencia automática $q$: $T'=\lfloor (1-q)T \rfloor$.
- **Chromatic Orb (nivel $L$)**:  
  $T \sim \sum_{i=1}^{L+2} 1d8$ (doblar nº de dados en crítico).
- **Fire Bolt** (cantrip a nivel 10 en este modelo):  
  normal $= 2\times 1d10$, crítico $= 4\times 1d10$.
- **Shield**: anula golpes dentro del rango $[\text{AC},\text{AC}+5)$ si hay slot (gating inducido por la tirada enemiga).

---

# Rasgos de Monstruo

- **Multiataque**: repeticiones i.i.d. del esquema hit/daño.
- **Aliento / AoE**:

$$
B \sim \sum_{i=1}^{N} 1dD, \quad
\text{daño a cada objetivo} =
\begin{cases}
B & \text{si falla la salvación}\\[4pt]
\lfloor B/2 \rfloor & \text{si la supera}
\end{cases}
$$

Si hay **cargas** disponibles, se puede aplicar $\times 2$ si eso mata (decisión determinista).

---

# Rasgos de Monstruo

- **Recarga** (p. ej. “5–6”): por turno

$$
R\sim 1d6,\quad P(\text{listo}) = \frac{2}{6},\;
\text{tiempo de espera} \sim \mathrm{Geom}\!\left(\tfrac{2}{6}\right).
$$

- **Regeneración**: +HP determinista por turno.
- **Counter on miss**: ataque estándar cuando el rival falla.
- **Invocar lobo**: se activa al cruzar umbral de HP; luego $T$ turnos de daño $1dD+\text{MOD}$.

---

# Métricas que estimamos (por combinación de dado y composición)

Para cada simulación guardamos flags y medidas; a partir de $n$ repeticiones:

- **Baseline**: $\hat p_0 = P(\text{win})$.
- **Condicionadas**:

$$
\hat p_{\text{PF}} = P(\text{win}\mid \text{party first}),
\qquad
\hat p_{\text{FC}} = P(\text{win}\mid \text{primer ataque crit}).
$$

---

# Métricas que estimamos (por combinación de dado y composición)

- **Impactos marginales (deltas)**:

$$
\Delta_{\text{miss1}} = P(\text{win}\mid \text{fallé primer ataque}) - \hat p_0,
\qquad
\Delta_{\text{recibí crit1}} = P(\text{win}\mid \text{recibí crit en turno 1}) - \hat p_0.
$$

- **Rachas de críticos** (longitudes consecutivas $>0$): mínimo, máximo, promedio.

---

# Estimación Monte Carlo y errores

Sea $\hat p = \tfrac{1}{n}\sum_{i=1}^n \mathbf{1}\{\text{evento}_i\}$.  
Para $n$ grande, por CLT:

$$
\hat p \approx \mathcal{N}\!\Big(p,\, \tfrac{p(1-p)}{n}\Big),
\qquad
\text{IC 95\%} \approx \hat p \pm 1.96\sqrt{\tfrac{\hat p(1-\hat p)}{n}}.
$$

Diferencias de proporciones $\hat p_a - \hat p_b$: aproximación normal con varianza suma (si independientes) o teniendo en cuenta covarianza (si comparten muestra).

---

# Cómo leer las gráficas (por monstruo)

- **Eje X**: dado de daño del Guerrero (d4, d6, …).
- **Barras por X**: **Solo**, **Healer**, **Party completa** (colores distintos).
- **Eje Y**: valor de la métrica (probabilidad o conteo esperado).
- **Título**: “{métrica} – {monstruo}”.

> Inserta aquí, por monstruo, la colección de gráficas (una por métrica):
>
> `![baseline_P(win) – CLOAKER](graphs/CLOAKER/plot_baseline_P_win__CLOAKER.png)`  
> `![P(win | party first) – CLOAKER](graphs/CLOAKER/plot_P_win___party_first__CLOAKER.png)`

---

# Cómo leer las gráficas (entre monstruos)

- **Eje X**: monstruo.
- **Barras por X**: una barra por **dado** (colores fijos por dado).
- **Series**: una figura por **métrica** y **composición** (Solo / Healer / Party).
- **Leyenda**: color ↔ dado (d4, d6, …).

> Inserta aquí, por métrica y composición, las “final_*.png”:
>
> `![baseline_P(win) – All – Solo](graphs/_ALL_MONSTERS/final_baseline_P_win__solo_all_monsters.png)`

---

# Preguntas que respondemos (por monstruo y global)

- $P(\text{win} \mid \text{party first})$.
- $P(\text{win} \mid \text{primer ataque crítico})$.
- $\Delta_{\text{miss1}} = P(\text{win}\mid \text{fallo primer ataque}) - P(\text{win})$.
- $\Delta_{\text{recibí crit1}} = P(\text{win}\mid \text{recibir crit en turno 1}) - P(\text{win})$.
- Rachas de críticos: **mínimo**, **máximo**, **promedio (>0)**.

*(Todos estos valores aparecen en los CSV y en las gráficas por métrica.)*

---

# Composición con Healer

**Escenario**: Guerrero L10 + Healer L10 vs 1 monstruo  
**Orden**: iniciativa aleatoria por ronda entre *warrior, healer, monster*.  
$P(\text{party first}) = \tfrac{2}{3}$ por simetría.

---

## Política de decisión del Healer (por turno)

Determinística, basada en HP y slots disponibles $\{L=1,\dots,5\}$.

1) **Ambos heridos** ($w\_hp < \text{max}_w$ **y** $h\_hp < \text{max}_h$)  
   → si existe slot $L\ge 3$: **Mass Healing Word** al **máximo $L$** disponible.

$$
H \sim \sum_{i=1}^{k} 1d4 + \text{mod},\quad k = 1 + \max(0, L-3),
$$

se aplica a **ambos** (misma tirada por objetivo en el código).

---

## Política de decisión del Healer (por turno)

2) **Alguien bajo de vida** ($w\_hp < 0.5\cdot \text{max}_w$ **o** $h\_hp < 0.5\cdot \text{max}_h$)  
   → si existe slot: **Cure Wounds** al **máximo $L$** disponible sobre el **más dañado**  
   (en 2v1: el de **menor HP absoluto**).

$$
H \sim \sum_{i=1}^{k} 1d8 + \text{mod},\quad k = 1 + \max(0, L-1).
$$

---

## Política de decisión del Healer (por turno)

3) **Hay heridos pero no “bajos”**  
   → **Healing Word** priorizando **slots bajos** (si hay $L\le 2$, usar el mayor de ellos; si no, usar el mayor $L$ disponible).  
   Objetivo: el de **menor HP absoluto**.

$$
H \sim \sum_{i=1}^{k} 1d4 + \text{mod},\quad k = 1 + \max(0, L-1).
$$

---

## Política de decisión del Healer (por turno)

4) **Ambos a tope** (sin heridos)  
   → **Ataque de arma** del Healer:
   - Tirada: $R \sim \mathrm{Unif}\{1,\dots,20\}$.  
     $P(\text{crit})=1/20,\ P(\text{nat1})=1/20$.
   - Impacta si $R=20$ o $R+\text{ATK\_MOD} \ge \text{AC}_{\text{efectivo}}$.
   - Daño:

$$
D=\begin{cases}
0 & (\text{fallo})\\[4pt]
1d6 + \text{DMG\_MOD} & (\text{hit sin crit})\\[4pt]
2d6 + \text{DMG\_MOD} & (\text{crítico})
\end{cases}
$$

---

## Política de decisión del Healer (por turno)

> **Consumo de slots**: cada conjuro gasta exactamente 1 slot del nivel elegido (se toma el **más alto** que cumpla la regla en 1) y 2), y el **más bajo posible** en 3) si hay $L\le 2$).  
> **Selección de objetivo** en 2) y 3): en 2v1, si $\texttt{w\_hp} \le \texttt{h\_hp}$ se cura al Guerrero; en caso contrario, al Healer.

---

## Distribuciones usadas en esta composición

- **To-hit (Healer)**: $R \sim \mathrm{Unif}\{1,\dots,20\}$; evento de impacto:

$$
P(\text{hit}) = P(R=20) + P\big(R\in\{2,\dots,19\},\, R+\text{ATK\_MOD}\ge \text{AC}_{\text{efectivo}}\big).
$$

- **Curaciones**:
  - *Cure Wounds*: suma de uniformes discretas $1d8$ ($k = 1+\max(0,L-1)$) $+$ $\text{mod}$.
  - *Healing Word*: suma de uniformes discretas $1d4$ ($k = 1+\max(0,L-1)$) $+$ $\text{mod}$.
  - *Mass Healing Word*: suma de uniformes $1d4$ ($k = 1+\max(0,L-3)$) $+$ $\text{mod}$ a cada objetivo.

---

## Distribuciones usadas en esta composición

- **Decisión de hechizo/ataque**: **no aleatoria**; es una política **determinística** (árbol de reglas de arriba).
- **Monstruo**: mantiene sus distribuciones (multiataque, aliento $=\sum 1dD$ con salvación Bernoulli para mitad, recarga geométrica, etc.) idénticas al resto de escenarios.

---

## Notas de implementación (resumen del código)

```text
if ambos_heridos and slot(L>=3):
    usar Mass Healing Word al L más alto
elif alguien_muy_bajo and slot(cualquiera):
    usar Cure Wounds al L más alto sobre quien tenga menor HP
elif alguien_herido and slot:
    usar Healing Word (prefiere L<=2; si no hay, el mayor L)
else:
    atacar con arma (1d20 para impactar; daño 1d6 [+mod], crítico duplica dados)
```

---

# Party completa (extra)

* Se añaden:

  * **Rogue** con Steady Aim, Sneak Attack, Uncanny Dodge.
  * **Wizard** con slots, Magic Missile / Chromatic Orb / Fire Bolt, y **Shield**.
* Distribuciones: ver slides anteriores (daño por dados, Bernoulli de hit/crit, mezcla por crítico, Geom. para recarga de alientos, gating para Shield).
* El monstruo **elige objetivo** con heurística determinista (HP más bajo, prioridades).

---

# Supuestos y limitaciones

* AC, HP y modificadores fijos (no escalamos con condiciones fuera del modelo).
* Ventaja/desventaja sólo donde lo indicamos (no se acumulan múltiples fuentes).
* Decisiones “inteligentes” codificadas: Action Surge, uso de superioridad, objetivos, etc.
  → No hay “blunders” ni TTP complejos; es una **política determinista**.
* Independencias aproximadas: p. ej., rachas de críticos se miden en un proceso con nº de ataques aleatorio y estados (ventaja) que cambian.

---

# Reproducibilidad

* **CSV**: `csv/<MONSTRUO>/dnd_*.csv` contienen métricas por dado.
* **Gráficas por monstruo**: `graphs/<MONSTRUO>/plot_*.png`.
* **Comparativas globales**: `graphs/_ALL_MONSTERS/final_*.png`.
* **Semilla RNG** configurable: `--seed`.
* **Intensidad Monte Carlo**: `--sims` (sug.: ≥ 10k).

---

# Fin