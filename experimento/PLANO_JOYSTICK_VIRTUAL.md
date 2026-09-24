# Plano: Migração para Joystick Virtual via evdev/uinput

## Contexto

O sistema atual controla o SuperTuxKart usando a orientação do celular (via OSC) para direcionar o kart. A direção é traduzida em pressionamentos de teclas do teclado (`pynput`), e para simular proporcionalidade, o `steer.py` usa **PWM por software** — alternando rapidamente entre press/release. Isso funciona, mas gera micro-solavancos porque as teclas são binárias (on/off).

O SuperTuxKart tem **suporte nativo a joystick/gamepad**, incluindo eixos analógicos. A ideia é criar um **joystick virtual** no Linux via `evdev`/`uinput`, substituindo a simulação de teclado por um eixo analógico real — resultando em direção fluida e contínua, como um Wii Wheel no Mario Kart.

## Arquitetura Atual

```
Celular (MultiSense OSC)
    │
    ▼
steer.py (recebe OSC, aplica filtro + expo + PWM)
    │  envia comandos P_LEFT/R_LEFT/P_ACCELERATE etc. via UDP
    ▼
STK_input_server_v2.py (recebe UDP, simula teclado via pynput)
    │                        ▲
    │                        │  Arduino e outras interfaces também enviam UDP
    ▼
Teclado virtual (pynput) ──→ SuperTuxKart
```

**Problemas:**
- Teclas são binárias → PWM necessário para simular proporcionalidade
- PWM gera micro-zigzag frame a frame (ora full lock, ora nada)
- Complexidade alta: thread de PWM, interruptible_sleep, duty cycles, pulsos mínimos

## Arquitetura Proposta

```
Celular (MultiSense OSC)
    │
    ▼
steer.py (recebe OSC, aplica filtro + expo, calcula valor contínuo -1.0 a 1.0)
    │  envia "STEER:<valor>" e comandos de botão via UDP
    ▼
STK_input_server_v2.py (hub central, cria joystick virtual via evdev/uinput)
    │                        ▲
    │                        │  Arduino e outras interfaces também enviam UDP
    ▼
Joystick virtual (/dev/input/eventX) ──→ SuperTuxKart
```

**Ganhos:**
- Eixo analógico real → direção contínua e fluida
- Eliminação total do PWM e sua complexidade
- Menos latência (sem pynput, sem X11/Wayland no caminho)
- O STK_input_server continua como hub central para todas as interfaces

---

## Tarefas de Implementação

### Tarefa 1: Modificar `STK_input_server_v2.py` — Criar Joystick Virtual

**Objetivo:** Substituir o `pynput` (simulação de teclado) por um dispositivo joystick virtual via `evdev`/`uinput`.

**Dependência:** `pip install evdev`

**1.1 — Criar o dispositivo virtual na inicialização**

Usar `python-evdev` com `UInput` para criar um gamepad virtual com:

- **1 eixo analógico:** `ABS_X` (direção) — range de `-32767` a `+32767`, valor 0 = centro
- **Botões de jogo** para os comandos existentes. Sugestão de mapeamento:

| Comando atual | Mapeamento no joystick virtual |
|---|---|
| Direção (STEER) | `ABS_X` (eixo analógico, valor contínuo) |
| ACCELERATE | `BTN_A` (ou `BTN_SOUTH`) |
| BRAKE | `BTN_B` (ou `BTN_EAST`) |
| FIRE (item) | `BTN_X` (ou `BTN_NORTH`) |
| NITRO | `BTN_Y` (ou `BTN_WEST`) |
| SKIDDING | `BTN_TL` (trigger esquerdo) |
| LOOKBACK | `BTN_TR` (trigger direito) |
| RESCUE | `BTN_SELECT` |
| PAUSE | `BTN_START` |
| SELECT (menu) | `BTN_A` |
| CANCEL / BACK (menu) | `BTN_B` |
| UP / DOWN / LEFT / RIGHT (menu) | Hat/D-pad: `ABS_HAT0X` e `ABS_HAT0Y` ou usar o próprio eixo + botões |

> [!NOTE]
> O mapeamento de botões pode precisar de ajuste após testar no STK.
> O STK permite remapear controles no menu de configurações.

**Exemplo de referência para criação do dispositivo:**

```python
from evdev import UInput, AbsInfo, ecodes

capabilities = {
    ecodes.EV_ABS: [
        (ecodes.ABS_X, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
        # Hat/D-pad para navegação em menus
        (ecodes.ABS_HAT0X, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        (ecodes.ABS_HAT0Y, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
    ],
    ecodes.EV_KEY: [
        ecodes.BTN_A,      # Acelerar / Confirmar menu
        ecodes.BTN_B,      # Frear / Cancelar menu
        ecodes.BTN_X,      # Fire (item)
        ecodes.BTN_Y,      # Nitro
        ecodes.BTN_TL,     # Skidding
        ecodes.BTN_TR,     # Lookback
        ecodes.BTN_SELECT, # Rescue
        ecodes.BTN_START,  # Pause
    ],
}

gamepad = UInput(capabilities, name="STK-Celular-Controller", vendor=0x045e, product=0x028e)
```

> [!TIP]
> Usar vendor/product de um Xbox 360 controller (`0x045e`/`0x028e`) pode ajudar o STK a reconhecer automaticamente o dispositivo com mapeamentos padrão. Testar com e sem isso.

**1.2 — Novo protocolo de comandos UDP**

Atualizar a lista de bindings para suportar:

| Comando UDP recebido | Ação no joystick virtual |
|---|---|
| `STEER:<float>` | Escreve `int(valor * 32767)` no `ABS_X`. Valor entre `-1.0` (esquerda máx) e `1.0` (direita máx). |
| `P_ACCELERATE` | `BTN_A` press (value=1) |
| `R_ACCELERATE` | `BTN_A` release (value=0) |
| `P_BRAKE` | `BTN_B` press |
| `R_BRAKE` | `BTN_B` release |
| `FIRE` | `BTN_X` press + pequeno delay + release (tap) |
| `NITRO` | `BTN_Y` tap |
| `P_SKIDDING` / `R_SKIDDING` | `BTN_TL` press/release |
| `P_LOOKBACK` / `R_LOOKBACK` | `BTN_TR` press/release |
| `RESCUE` | `BTN_SELECT` tap |
| `PAUSE` | `BTN_START` tap |
| `UP` / `DOWN` | `ABS_HAT0Y` (-1 / +1), soltar após tap |
| `LEFT` / `RIGHT` | `ABS_HAT0X` (-1 / +1), soltar após tap |
| `SELECT` | `BTN_A` tap |
| `CANCEL` / `BACK` | `BTN_B` tap |

**1.3 — Parsing dos comandos**

```python
if data.startswith("STEER:"):
    value = float(data.split(":")[1])
    axis_val = max(-32767, min(32767, int(value * 32767)))
    gamepad.write(ecodes.EV_ABS, ecodes.ABS_X, axis_val)
    gamepad.syn()
elif data in commands:
    # tratar botões como antes, mas escrevendo no gamepad em vez de pynput
    ...
```

**1.4 — Manter retrocompatibilidade**

Idealmente, manter suporte a **ambos os modos** (teclado via pynput e joystick via evdev) com um argumento de linha de comando:

```bash
python STK_input_server_v2.py              # modo padrão: joystick virtual (novo)
python STK_input_server_v2.py --keyboard   # modo legado: pynput/teclado
```

Isso garante que nada quebre enquanto se testa a nova implementação.

**1.5 — Cleanup**

No encerramento (`STOPSERVEUR` ou `Ctrl+C`), fechar o dispositivo com `gamepad.close()` para remover o joystick virtual do sistema.

---

### Tarefa 2: Modificar `steer.py` — Eliminar PWM, Enviar Valor Contínuo

**Objetivo:** Simplificar drasticamente o `steer.py` removendo toda a lógica de PWM e enviando um valor contínuo de steering.

**2.1 — Novo formato de envio de steering**

Em vez de enviar `P_LEFT`/`R_LEFT` e fazer PWM, enviar um único valor contínuo:

```python
def send_steer(value):
    """Envia valor de -1.0 (esquerda max) a 1.0 (direita max). 0.0 = centro."""
    client_socket.sendto("STEER:{:.4f}".format(value).encode('utf8'), STK_ADDRESS)
```

**2.2 — Modificar `on_pitch()` (callback de orientação)**

O processamento do pitch (filtro adaptativo, dead zone, curva expo) **permanece igual** — é a parte boa do código. O que muda é o output:

```python
# ANTES (define variáveis para a thread de PWM consumir):
with lock:
    current_steer_dir       = new_dir
    current_steer_intensity = new_intensity

# DEPOIS (envia direto):
if new_dir is None:
    send_steer(0.0)
else:
    sign = 1.0 if new_dir == "RIGHT" else -1.0
    send_steer(sign * new_intensity)
```

**2.3 — Controle de taxa de envio**

Para não inundar o server com mensagens UDP, enviar steering updates a uma taxa controlada. Duas opções:

- **Opção A (simples):** Só enviar quando o valor mudar mais que um threshold mínimo (ex: 0.5% de mudança). Evita flood sem adicionar latência.
- **Opção B (thread dedicada):** Uma thread envia o valor atual a cada ~16ms (~60Hz, matching o framerate do jogo). Mais previsível.

> [!IMPORTANT]
> A **Opção A** é recomendada por ser mais simples e eficiente. O callback OSC já é chamado ~30-100x/s pelo sensor, então basta filtrar redundâncias.

Exemplo (Opção A):
```python
last_sent_steer = 0.0
STEER_SEND_THRESHOLD = 0.005  # ~0.5% de mudança mínima para enviar

def on_pitch(*values):
    global last_sent_steer
    # ... processamento existente (filtro, expo, dead zone) ...

    if new_dir is None:
        steer_value = 0.0
    else:
        sign = 1.0 if new_dir == "RIGHT" else -1.0
        steer_value = sign * new_intensity

    if abs(steer_value - last_sent_steer) > STEER_SEND_THRESHOLD:
        send_steer(steer_value)
        last_sent_steer = steer_value
```

**2.4 — Remover código de PWM**

Deletar as seguintes partes que ficam obsoletas:

- `steering_thread()` inteira (~70 linhas) — a thread de PWM
- `interruptible_sleep()`
- Variáveis globais: `current_steer_dir`, `current_steer_intensity`
- Constantes de PWM: `PWM_PERIOD`, `MIN_PRESS_MS`, `FULL_LOCK_THRESHOLD`, `MIN_DUTY_THRESHOLD`
- O `threading.Thread(target=steering_thread)` no `main()`
- O lock pode ser simplificado ou removido (depende de como ficar o touch)

**2.5 — Manter touch (aceleração/freio) sem mudanças funcionais**

O callback `on_pad_x()` continua enviando `P_ACCELERATE`/`R_ACCELERATE`/`P_BRAKE`/`R_BRAKE` via UDP como hoje. O server é que vai traduzir isso para botões do joystick virtual em vez de teclas.

A detecção de 2 dedos para recalibração também continua igual.

---

### Tarefa 3: Configuração do Sistema

**3.1 — Permissões do `/dev/uinput`**

O `uinput` requer permissões especiais. Configurar **uma** das opções:

**Opção A (recomendada): Regra udev permanente**
```bash
# Criar arquivo /etc/udev/rules.d/99-uinput.rules com:
KERNEL=="uinput", MODE="0660", GROUP="input"

# Adicionar o usuário ao grupo input:
sudo usermod -aG input $USER

# Recarregar regras e reiniciar sessão:
sudo udevadm control --reload-rules
sudo udevadm trigger
# (fazer logout/login para o grupo ter efeito)
```

**Opção B (rápida para testar):**
```bash
sudo chmod 666 /dev/uinput
# ou rodar o server com sudo
sudo python STK_input_server_v2.py
```

**3.2 — Instalar dependências**

```bash
pip install evdev
```

> [!NOTE]
> O `pynput` pode ser mantido como dependência para o modo `--keyboard` (retrocompatibilidade), ou removido se não for mais necessário.

**3.3 — Configurar o SuperTuxKart**

Após iniciar o `STK_input_server_v2.py` (que cria o joystick virtual):

1. Abrir o SuperTuxKart
2. Ir em **Options → Controls**
3. O jogo deve detectar o "STK-Celular-Controller" automaticamente
4. Mapear os eixos e botões:
   - Steer: Eixo X do joystick
   - Accelerate: Botão A
   - Brake: Botão B
   - Fire: Botão X
   - Nitro: Botão Y
   - etc.
5. Ajustar **deadzone** do joystick nas configurações do STK se necessário

---

### Tarefa 4: Testes e Ajuste Fino

**4.1 — Teste de sanidade do dispositivo virtual**

Antes de testar no STK, verificar se o dispositivo está funcionando:

```bash
# Listar dispositivos de input
ls /dev/input/

# Monitorar eventos do joystick virtual em tempo real
evtest /dev/input/eventX  # (substituir X pelo número correto)

# Ou usar jstest se disponível
jstest /dev/input/jsX
```

**4.2 — Teste de proporção do eixo**

Enviar valores de teste e verificar no `evtest`:
```bash
# No terminal, enviar manualmente via netcat:
echo "STEER:0.0" | nc -u localhost 6006
echo "STEER:0.5" | nc -u localhost 6006
echo "STEER:-1.0" | nc -u localhost 6006
```

**4.3 — Ajustes na curva de sensibilidade**

Após testar no jogo, possivelmente ajustar:

- **`EXPO_GAMMA`** no `steer.py`: O STK pode ter sua própria curva de sensibilidade para joystick. Se a direção parecer "quadrada" ou "lenta", experimentar valores entre 1.0 (linear) e 2.0 (muito exponencial).
- **`DEAD_ZONE`**: Com eixo analógico, a dead zone pode ser menor (ex: 3° em vez de 4.5°), porque não há mais tremor de PWM.
- **`MAX_STEER_ANGLE`**: Ajustar se a inclinação máxima de 30° parecer muito ou pouco.

**4.4 — Teste de latência**

Comparar a latência percebida entre o modo teclado (`--keyboard`) e joystick virtual. O joystick virtual deve ser perceptivelmente mais responsivo na direção.

---

## Ordem de Execução Recomendada

1. **Configurar permissões** do `/dev/uinput` (Tarefa 3.1)
2. **Instalar `evdev`** (Tarefa 3.2)
3. **Modificar `STK_input_server_v2.py`** (Tarefa 1) — criar joystick virtual, novo parser de comandos
4. **Testar o dispositivo virtual** isoladamente (Tarefa 4.1 e 4.2)
5. **Modificar `steer.py`** (Tarefa 2) — remover PWM, enviar valor contínuo
6. **Configurar o STK** para usar o joystick (Tarefa 3.3)
7. **Ajuste fino** de sensibilidade e gameplay (Tarefa 4.3 e 4.4)

---

## Arquivos Afetados

| Arquivo | Ação |
|---|---|
| `STK_input_server_v2.py` | Modificação significativa (evdev em vez de pynput) |
| `steer.py` | Simplificação (remover PWM, enviar valor contínuo) |
| `requirements.txt` | Criar ou atualizar (adicionar `evdev`) |

## Riscos e Mitigações

| Risco | Mitigação |
|---|---|
| STK não reconhece o joystick virtual | Testar vendor/product IDs diferentes. O STK usa SDL para input, que é compatível com evdev. |
| Permissões do uinput bloqueiam execução | Configurar regra udev ou usar sudo para teste rápido. |
| Latência de rede OSC domina a experiência | Não é afetado por esta mudança — mesma rede, mesmo protocolo. |
| Arduino e outras interfaces param de funcionar | Manter retrocompatibilidade com flag `--keyboard`. Comandos de botão (P_/R_) continuam funcionando no modo joystick. |
