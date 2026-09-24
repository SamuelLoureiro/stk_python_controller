# PROMPT PARA AGENTE: Migração do Steering de PWM/Teclado para Joystick Analógico

> **Instrução para o agente**: Lê este ficheiro por completo antes de começar.
> Segue os passos na ordem indicada. Testa a sintaxe de cada ficheiro alterado.
> NÃO altere nenhum ficheiro que não esteja listado explicitamente.

---

## 0. Contexto e Objetivo

O projeto controla o SuperTuxKart usando vários módulos. Atualmente a **direção**
funciona assim:

```
Celular (OSC pitch) → steer_module.py → calcula intensidade 0.0~1.0
                                       → PWM digital (pulsa P_LEFT/R_LEFT rapidamente)
                                       → STK_input_server_v2.py → pynput → teclado → STK
```

O problema é que as teclas são **binárias** (0% ou 100%). O PWM simula
proporcionalidade mas nunca é verdadeiramente suave.

Na pasta `experimento/` existe um servidor alternativo que cria um **gamepad
virtual Xbox 360** via `evdev`/`uinput` com um eixo analógico real (`ABS_X`).
A direção é enviada como `STEER:0.5000` (float de -1.0 a 1.0) e o STK
reconhece nativamente como joystick.

**O objetivo é migrar o projeto principal para usar essa abordagem analógica
para a direção, sem quebrar nenhum outro módulo.**

---

## 1. O que NÃO deve ser alterado

Estes módulos/ficheiros **NÃO devem ser tocados** de forma alguma:

| Ficheiro | Motivo |
|---|---|
| `face_module.py` | Funciona perfeitamente (sobrancelhas→lookback, nod→rescue) |
| `voice_module.py` | Funciona perfeitamente (turbo→NITRO, fire→FIRE) |
| `config.py` | Nenhuma mudança necessária |
| `drift.ino` | Hardware Arduino independente |
| `input_controller.py` | Legado, não usado |
| `main.py` | Legado, não usado |
| `steer.py` | Original standalone, manter intacto |

---

## 2. Ficheiros a alterar (apenas 3)

| Ficheiro | Alteração |
|---|---|
| `STK_input_server_v2.py` | Substituir pelo servidor híbrido (gamepad virtual + teclado) |
| `steer_module.py` | Simplificar: eliminar PWM, enviar `STEER:float` direto |
| `run_all.py` | Pequeno ajuste no banner (opcional) |
| `requirements.txt` | Adicionar `evdev` |

---

## 3. Referência: Servidor do Experimento

O ficheiro `experimento/STK_input_server_v2.py` é o modelo a seguir. Ele faz
duas coisas:

### 3.1 Gamepad Virtual (evdev/uinput) — APENAS para direção

```python
from evdev import UInput, AbsInfo, ecodes

capabilities = {
    ecodes.EV_ABS: [
        (ecodes.ABS_X, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
        (ecodes.ABS_Y, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
        (ecodes.ABS_Z, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
        (ecodes.ABS_RZ, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
        (ecodes.ABS_HAT0X, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        (ecodes.ABS_HAT0Y, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
    ],
    ecodes.EV_KEY: [
        ecodes.BTN_A, ecodes.BTN_B, ecodes.BTN_X, ecodes.BTN_Y,
        ecodes.BTN_TL, ecodes.BTN_TR, ecodes.BTN_SELECT, ecodes.BTN_START,
    ],
}

gamepad = UInput(capabilities, name="Xbox 360 Controller", vendor=0x045e, product=0x028e)
```

### 3.2 Função set_steer — Converte float para eixo analógico

```python
def set_steer(float_val):
    """Aplica o valor analógico contínuo (-1.0 a 1.0) no eixo ABS_X do volante."""
    if gamepad:
        clamped = max(-1.0, min(1.0, float_val))
        axis_val = int(clamped * 32767)
        gamepad.write(ecodes.EV_ABS, ecodes.ABS_X, axis_val)
        gamepad.syn()
```

### 3.3 Protocolo no loop principal

```python
# Comando de direção analógica (novo)
if data.startswith("STEER:"):
    val = float(data.split(":")[1])
    set_steer(val)
    continue

# Todos os demais comandos continuam por teclado (pynput)
if data in commands:
    b = bindings[commands.index(data)]
    b[2](b[1])
```

### 3.4 Cleanup no encerramento

```python
finally:
    if gamepad:
        set_steer(0.0)
        gamepad.close()
    sock.close()
```

---

## 4. Passo a Passo de Implementação

### PASSO 1: Substituir `STK_input_server_v2.py`

Copiar o conteúdo do ficheiro `experimento/STK_input_server_v2.py` para
substituir o `STK_input_server_v2.py` da raiz do projeto.

**Verificação**: O ficheiro da pasta `experimento/` já contém:
- Todos os bindings de teclado do servidor original (P_LEFT, R_LEFT, FIRE,
  NITRO, P_LOOKBACK, R_LOOKBACK, RESCUE, P_SKIDDING, R_SKIDDING, P_ACCELERATE,
  R_ACCELERATE, P_BRAKE, R_BRAKE, etc.)
- O gamepad virtual Xbox 360
- O parsing de `STEER:float`
- Tratamento de erros e cleanup

**Ação**: Copiar `experimento/STK_input_server_v2.py` → `./STK_input_server_v2.py`
(sobrescrever o original).

---

### PASSO 2: Simplificar `steer_module.py`

Esta é a mudança principal. O `steer_module.py` atual tem ~380 linhas com toda
a lógica de PWM. Precisa ser simplificado drasticamente:

**O que ELIMINAR:**
- Toda a `steering_thread()` (thread de PWM de ~70 linhas)
- As constantes de PWM: `PWM_PERIOD`, `MIN_PRESS_MS`, `FULL_LOCK_THRESHOLD`, `MIN_DUTY_THRESHOLD`
- As variáveis de estado: `current_steer_dir`, `current_steer_intensity`
- O COMMANDS dict para LEFT/RIGHT (não precisa mais de P_LEFT/R_LEFT)

**O que MANTER:**
- O callback `on_pitch()` com o filtro adaptativo zero-lag e curva exponencial
- O callback `on_pad_x()` para aceleração/freio (continua por teclado: P_ACCELERATE, etc.)
- A calibração automática e recalibração com 2 dedos
- A `release_watchdog()` para o acelerador/freio
- A `keyboard_listener_thread()` para recalibrar via Enter
- A função `start_steer(send_fn)` e `stop()`
- O servidor OSC na porta 8000
- Constantes: `DEAD_ZONE`, `MAX_STEER_ANGLE`, `EXPO_GAMMA`, `STEER_SIGN`,
  `TOUCH_TIMEOUT`, `RECAL_COOLDOWN`

**O que MUDAR no `on_pitch()`:**
Em vez de calcular `current_steer_dir` e `current_steer_intensity` (que eram
consumidos pela thread de PWM), o callback deve calcular o **valor analógico
final** (-1.0 a 1.0) e enviá-lo **imediatamente** via `send_fn("STEER:X.XXXX")`.

A lógica de cálculo já existe e é excelente — apenas o resultado muda:

```python
def on_pitch(*values):
    global pitch_origin, smoothed_pitch

    if not values:
        return
    value = float(values[0])

    # Calibração automática no primeiro valor (MANTER como está)
    if pitch_origin is None:
        pitch_origin = value
        smoothed_pitch = value
        print(...)
        return

    # Filtro adaptativo zero-lag (MANTER como está)
    diff = abs(value - smoothed_pitch)
    adaptive_alpha = min(0.85, max(0.35, 0.35 + (diff / 12.0) * 0.50))
    smoothed_pitch = adaptive_alpha * value + (1.0 - adaptive_alpha) * smoothed_pitch

    # Delta em relação ao centro (MANTER como está)
    delta = normalize_angle(smoothed_pitch - pitch_origin) * STEER_SIGN
    adelta = abs(delta)

    # Calcular valor analógico contínuo (-1.0 a 1.0)
    if adelta <= DEAD_ZONE:
        steer_value = 0.0
    else:
        norm = min(1.0, (adelta - DEAD_ZONE) / (MAX_STEER_ANGLE - DEAD_ZONE))
        intensity = norm ** EXPO_GAMMA
        # Sinal: delta > 0 = direita (+), delta < 0 = esquerda (-)
        steer_value = intensity if delta > 0 else -intensity

    # ENVIAR DIRETAMENTE como STEER:float (em vez de alimentar thread PWM)
    _module_send_command(f"STEER:{steer_value:.4f}")

    if DEBUG_STEER:
        bar_len = int(abs(steer_value) * 20)
        side = "R" if steer_value > 0 else "L" if steer_value < 0 else "C"
        bar = "[" + "=" * bar_len + " " * (20 - bar_len) + "]"
        print(f"delta={delta:+5.1f}° | {side} | steer={steer_value:+.4f} {bar}")
```

**Nota sobre a recalibração (`trigger_recalibrate`):**
Ao recalibrar, enviar `STEER:0.0000` para centralizar o volante imediatamente:

```python
def trigger_recalibrate(reason=""):
    global pitch_origin, smoothed_pitch, last_recal_time
    global current_vertical

    now = time.time()
    if now - last_recal_time < RECAL_COOLDOWN:
        return

    with lock:
        last_recal_time = now
        if smoothed_pitch is not None:
            pitch_origin = smoothed_pitch

        # Libera acelerador/freio se ativo
        if current_vertical is not None:
            _module_send_command(COMMANDS[current_vertical][1])
            current_vertical = None

    # Centraliza o volante analógico imediatamente
    _module_send_command("STEER:0.0000")

    print(...)
```

**Nota sobre a função `stop()`:**
Em vez de enviar `R_LEFT` e `R_RIGHT`, enviar `STEER:0.0000`:

```python
def stop():
    global current_vertical
    with lock:
        if current_vertical is not None:
            _module_send_command(COMMANDS[current_vertical][1])
            current_vertical = None
    _module_send_command("STEER:0.0000")
    time.sleep(0.05)
    osc.stop()
```

**COMMANDS dict simplificado** (só precisa de aceleração/freio agora):

```python
COMMANDS = {
    "ACCELERATE": ("P_ACCELERATE", "R_ACCELERATE"),
    "BRAKE":      ("P_BRAKE",      "R_BRAKE"),
}
```

---

### PASSO 3: Atualizar `run_all.py`

No cleanup final do `run_all.py`, substituir as releases de direção:

```python
# ANTES:
for cmd in ["R_LEFT", "R_RIGHT", "R_ACCELERATE", "R_BRAKE", "R_LOOKBACK", "R_SKIDDING"]:
    send_command(cmd)

# DEPOIS:
send_command("STEER:0.0000")  # Centralizar volante analógico
for cmd in ["R_ACCELERATE", "R_BRAKE", "R_LOOKBACK", "R_SKIDDING"]:
    send_command(cmd)
```

Atualizar o banner (opcional):
```python
print("  * 📱 Celular (OSC :8000) -> Volante Analógico (STEER) e Aceleração/Freio")
```

---

### PASSO 4: Atualizar `requirements.txt`

Adicionar `evdev` (necessário para o gamepad virtual no servidor):

```
opencv-python
mediapipe
pynput
vosk
sounddevice
numpy
oscpy
evdev
```

---

## 5. Compatibilidade: Por que os outros módulos NÃO são afetados

| Módulo | Comandos que envia | Canal no servidor | Mudou? |
|---|---|---|---|
| **steer_module** | `STEER:X.XXXX` (novo) | Gamepad ABS_X | ✅ SIM |
| **steer_module** | `P_ACCELERATE` / `R_ACCELERATE` | Teclado (pynput) | ❌ NÃO |
| **steer_module** | `P_BRAKE` / `R_BRAKE` | Teclado (pynput) | ❌ NÃO |
| **voice_module** | `NITRO`, `FIRE` | Teclado (pynput) | ❌ NÃO |
| **face_module** | `P_LOOKBACK`, `R_LOOKBACK`, `RESCUE` | Teclado (pynput) | ❌ NÃO |
| **drift.ino** | `P_SKIDDING`, `R_SKIDDING` | Teclado (pynput) | ❌ NÃO |

O servidor do `experimento/` já contém **todos** esses bindings de teclado,
portanto todos os módulos existentes continuam a funcionar sem qualquer mudança.

---

## 6. Configuração do SuperTuxKart

> **IMPORTANTE**: Depois de aplicar estas mudanças, o STK precisa de ser
> reconfigurado para usar o controle virtual para a direção.

1. Abrir SuperTuxKart → **Options** → **Controls**
2. O jogo deve detectar o "Xbox 360 Controller" automaticamente
3. Configurar:
   - **Steer Left / Steer Right**: Eixo analógico do "Xbox 360 Controller"
   - **Accelerate, Brake, Fire, Nitro, Look Back, Rescue, Skid**: Manter nas **teclas do teclado** (↑, ↓, Espaço, N, B, Backspace, V)

---

## 7. Permissões do Linux (pré-requisito)

O `evdev`/`uinput` precisa de permissão para criar dispositivos virtuais:

```bash
sudo chmod 666 /dev/uinput
```

Para tornar permanente (sobrevive a reinícios):

```bash
echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

## 8. Ordem de Execução (após as mudanças)

```bash
# 0. Permissão uinput (apenas na primeira vez)
sudo chmod 666 /dev/uinput

# 1. Arduino com drift.ino (ligar a placa)

# 2. Terminal 1 — Servidor (cria o gamepad virtual + escuta UDP)
python STK_input_server_v2.py -d

# 3. Abrir SuperTuxKart, configurar o controle (primeira vez), entrar numa corrida

# 4. Terminal 2 — Controller unificado
python run_all.py
```

---

## 9. Checklist de Verificação

- [ ] `STK_input_server_v2.py` substituído pelo do `experimento/`
- [ ] `steer_module.py` simplificado: sem PWM, envia `STEER:X.XXXX`
- [ ] `run_all.py` atualizado: cleanup envia `STEER:0.0000`
- [ ] `requirements.txt` contém `evdev`
- [ ] Todos os ficheiros compilam sem erros: `python3 -m py_compile STK_input_server_v2.py steer_module.py run_all.py`
- [ ] Servidor inicia e mostra "Xbox 360 Controller" sem erros
- [ ] `voice_module` continua enviando `FIRE` e `NITRO` corretamente
- [ ] `face_module` continua enviando `P_LOOKBACK`, `R_LOOKBACK`, `RESCUE`
- [ ] `drift.ino` continua enviando `P_SKIDDING`, `R_SKIDDING`
- [ ] Direção no STK é suave e analógica (sem solavancos de PWM)
- [ ] Recalibração com 2 dedos centraliza o volante (`STEER:0.0000`)
- [ ] `Ctrl+C` encerra tudo sem teclas presas e com gamepad fechado

---

## 10. Mapa Final de Comandos UDP

| Módulo | Quando | Comando UDP | Canal no servidor |
|---|---|---|---|
| **Steer** | Inclina celular | `STEER:X.XXXX` (-1.0 a 1.0) | Gamepad ABS_X |
| **Steer** | Toque direita tela | `P_ACCELERATE` | Teclado ↑ |
| **Steer** | Levanta dedo (acel) | `R_ACCELERATE` | Teclado ↑ |
| **Steer** | Toque esquerda tela | `P_BRAKE` | Teclado ↓ |
| **Steer** | Levanta dedo (freio) | `R_BRAKE` | Teclado ↓ |
| **Voice** | Grita "turbo" | `NITRO` | Teclado N |
| **Voice** | Grita "fire" | `FIRE` | Teclado Espaço |
| **Face** | Levanta sobrancelhas | `P_LOOKBACK` | Teclado B |
| **Face** | Relaxa sobrancelhas | `R_LOOKBACK` | Teclado B |
| **Face** | Acena cabeça (nod) | `RESCUE` | Teclado Backspace |
| **Drift** | Sensor tocado | `P_SKIDDING` | Teclado V |
| **Drift** | Sensor solto | `R_SKIDDING` ×3 | Teclado V |
