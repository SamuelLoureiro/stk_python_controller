# PROMPT PARA AGENTE: Integração SuperTuxKart Controller Unificado

> **Instrução para o agente**: Lê este ficheiro por completo antes de começar.
> Segue os passos na ordem indicada. Não inventes funções — usa apenas o que
> já existe nos ficheiros originais. Testa cada passo mentalmente contra a
> tabela de comandos UDP da Secção 9.

---

## 0. Contexto

Este projeto controla o jogo **SuperTuxKart** usando vários dispositivos de
entrada. O objetivo é criar um script unificado (`run_all.py`) que lance todos
os módulos Python em conjunto, onde cada módulo controla **APENAS** estas ações:

| Módulo | Dispositivo | Ações ÚNICAS permitidas | Tipo |
|---|---|---|---|
| `steer_module.py` (NOVO) | Celular (OSC via MultiSense) | **Direção** (LEFT/RIGHT) + **Aceleração/Freio** | Contínuo / PWM |
| `voice_module.py` (REFATORAR) | Microfone do PC (Vosk) | **Turbo** (nitro) + **Fire** (tiro) | Impulso |
| `face_module.py` (REFATORAR) | Webcam do PC (Mediapipe) | **Look Back** + **Rescue** | Contínuo / Impulso |
| `drift.ino` (NÃO TOCAR) | Arduino + sensor toque (UDP Wi-Fi) | **Drift** (skidding) | Contínuo |

O `drift.ino` roda no Arduino de forma independente — **NÃO** é lançado pelo Python.
O `STK_input_server_v2.py` é o servidor central — **NÃO ALTERAR**.

---

## 1. Arquitetura Final

Todos os módulos Python enviam comandos via **UDP** para o servidor
`STK_input_server_v2.py` na porta 6006. O servidor é o **único** que
usa `pynput` para emular teclas. Isso elimina conflitos.

```
                           ┌──────────────────────────────────────────┐
                           │            run_all.py (Python)           │
                           │                                          │
┌──────────────┐  OSC      │  ┌──────────────┐                        │
│  Celular     │──────────►│  │ steer_module │ direção + aceleração   │
└──────────────┘           │  └──────┬───────┘                        │
                           │         │ UDP                            │
┌──────────┐  Mediapipe    │  ┌──────┴───────┐                        │     ┌─────────────────────┐
│  Webcam  │──────────────►│  │ face_module  │ look_back + rescue     │────►│ STK_input_server_v2 │
└──────────┘               │  └──────┬───────┘                        │     │  (porta 6006)       │
                           │         │ UDP                            │     │  UDP → pynput → STK │
┌──────────┐  Vosk         │  ┌──────┴───────┐                        │     └─────────────────────┘
│  Micro   │──────────────►│  │ voice_module │ turbo + fire           │────►          ▲
└──────────┘               │  └──────────────┘                        │              │
                           └──────────────────────────────────────────┘              │
                                                                                     │
┌──────────┐  touch        ┌──────────┐  UDP (Wi-Fi)                                │
│  Arduino │──────────────►│ drift.ino│ ────────────────────────────────────────────┘
└──────────┘               └──────────┘  P_SKIDDING / R_SKIDDING
```

**Princípio-chave**: Todos os módulos recebem uma função `send_fn(command: str)`
que envia uma string UDP para o servidor. Os módulos **NÃO** importam `pynput`
nem `input_controller.py`.

---

## 2. Ficheiros que NÃO devem ser alterados

- `STK_input_server_v2.py` — servidor UDP, já suporta tudo
- `drift.ino` — roda no Arduino, já envia `P_SKIDDING`/`R_SKIDDING` via UDP
- `steer.py` — manter intacto para uso standalone (criar `steer_module.py` à parte)
- `main.py` — legado, manter como está
- `input_controller.py` — legado, manter como está

---

## 3. Comandos UDP suportados pelo servidor

Referência dos comandos que o `STK_input_server_v2.py` aceita (verificar no
ficheiro original, linhas 36–62):

| Comando | Tecla | Tipo | Usado por |
|---|---|---|---|
| `P_LEFT` / `R_LEFT` | ← | press/release | steer_module |
| `P_RIGHT` / `R_RIGHT` | → | press/release | steer_module |
| `P_ACCELERATE` / `R_ACCELERATE` | ↑ | press/release | steer_module |
| `P_BRAKE` / `R_BRAKE` | ↓ | press/release | steer_module |
| `FIRE` | Espaço | tap (50ms) | voice_module |
| `NITRO` | N | tap (50ms) | voice_module |
| `P_LOOKBACK` / `R_LOOKBACK` | B | press/release | face_module |
| `RESCUE` | Backspace | tap (50ms) | face_module |
| `P_SKIDDING` / `R_SKIDDING` | V | press/release | drift.ino (Arduino) |

---

## 4. Passo a Passo de Implementação

### PASSO 1: Atualizar `config.py`

Fazer **duas** alterações:

**1a)** Adicionar esta constante (pode ser logo após os imports, antes do KEY_MAP):

```python
# Endereço do servidor UDP (STK_input_server_v2.py)
STK_SERVER_ADDRESS = ('localhost', 6006)
```

**1b)** Alterar o `VOICE_ACTION_MAP` existente (por volta da linha 83–90) para
mapear para os **comandos UDP do servidor** em vez dos nomes de ação do pynput:

```python
# ANTES (errado para UDP):
# VOICE_ACTION_MAP = {
#     "turbo": "turbo",
#     "fire": "fire",
# }

# DEPOIS (correto para UDP):
VOICE_ACTION_MAP = {
    "turbo": "NITRO",    # Comando UDP enviado ao servidor
    "fire":  "FIRE",     # Comando UDP enviado ao servidor
}
```

Tudo o resto em `config.py` fica como está (KEY_MAP, thresholds, caminhos dos
modelos, etc.).

---

### PASSO 2: Refatorar `voice_module.py`

O ficheiro original recebe um `controller` (instância de `KeyboardController`)
e chama `controller.pulse(action, cooldown)`. Precisa ser mudado para receber
uma `send_fn` e enviar comandos UDP diretamente.

**Regras:**
- `__init__(self, send_fn)` em vez de `__init__(self, controller)`
- Guardar `self._send_fn = send_fn`
- Remover o import de `input_controller` (não será mais usado)
- Manter os imports de `config`, `VOICE_ACTION_MAP`, `VOICE_COOLDOWN_S`, `VOICE_SAMPLE_RATE`
- Em `_check_keywords`: quando encontra uma palavra no `VOICE_ACTION_MAP`, o
  valor já é o comando UDP (ex: `"NITRO"`, `"FIRE"`). Chamar
  `self._send_fn(comando)` com cooldown interno.

**Ficheiro completo refatorado:**

```python
"""
voice_module.py — Reconhecimento vocal (Vosk) para SuperTuxKart.

Vocabulário restrito: "turbo" → NITRO, "fire" → FIRE.
Envia comandos via UDP (send_fn) para o STK_input_server_v2.
"""

import json
import queue
import threading
import time

import sounddevice as sd
import vosk

import config
from config import VOICE_ACTION_MAP, VOICE_COOLDOWN_S, VOICE_SAMPLE_RATE


class VoiceWorker(threading.Thread):
    def __init__(self, send_fn):
        super().__init__(daemon=True)
        self._send_fn = send_fn
        self._stop_event = threading.Event()
        self._audio_queue = queue.Queue()
        self._last_trigger_time = {}  # cooldown por ação

    def stop(self):
        self._stop_event.set()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[voice] statut audio: {status}")
        self._audio_queue.put(bytes(indata))

    def run(self):
        vosk.SetLogLevel(-1)
        model = vosk.Model(config.VOSK_MODEL_PATH)

        grammar_words = list(VOICE_ACTION_MAP.keys()) + ["[unk]"]
        grammar = json.dumps(grammar_words)
        recognizer = vosk.KaldiRecognizer(model, VOICE_SAMPLE_RATE, grammar)

        with sd.RawInputStream(
            samplerate=VOICE_SAMPLE_RATE,
            blocksize=4000,
            dtype="int16",
            channels=1,
            callback=self._audio_callback,
        ):
            while not self._stop_event.is_set():
                try:
                    data = self._audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    text = json.loads(recognizer.Result()).get("text", "")
                else:
                    text = json.loads(recognizer.PartialResult()).get("partial", "")

                self._check_keywords(text)

    def _check_keywords(self, text: str):
        if not text:
            return
        now = time.monotonic()
        words = text.lower().split()
        for word in words:
            udp_command = VOICE_ACTION_MAP.get(word)
            if udp_command:
                last = self._last_trigger_time.get(word, 0.0)
                if now - last >= VOICE_COOLDOWN_S:
                    self._last_trigger_time[word] = now
                    self._send_fn(udp_command)
                    print(f"[voice] '{word}' → {udp_command}")
```

---

### PASSO 3: Refatorar `face_module.py`

O ficheiro original faz MUITAS coisas: sorriso→accelerate, boca→fire,
sobrancelhas→turbo, wink→left/right, cabeça virada→look_back, nod→rescue.

**REMOVER TUDO exceto look_back e rescue.**

**Regras:**
- `__init__(self, send_fn)` em vez de `__init__(self, controller)`
- Guardar `self._send_fn = send_fn`
- Adicionar `self._lookback_active = False` (estado interno para evitar spam)
- **ELIMINAR** completamente o método `_process_expressions` (ou esvaziar com `pass`)
- **NÃO chamar** `_process_expressions` no loop principal
- Em `_process_head_pose`:
  - **Look back**: quando `turned` muda de `False→True` → `send_fn("P_LOOKBACK")`.
    Quando `True→False` → `send_fn("R_LOOKBACK")`. Usar `self._lookback_active`
    para controlar o estado e evitar enviar o mesmo comando repetidamente.
  - **Rescue (nod)**: `send_fn("RESCUE")` — sem cooldown extra (o `_NodDetector`
    já filtra + usar `RESCUE_COOLDOWN_S` do config como comparação)
- No método `stop()` ou no `finally` do `run()`: enviar `R_LOOKBACK` para
  segurança (não deixar tecla presa)
- Manter `_NodDetector` como está (funciona perfeitamente)
- Manter `_blendshape_dict` e `_yaw_pitch_from_matrix` como estão
- Manter a janela de debug se `DEBUG_WINDOW` estiver ativa (pode mostrar menos info)
- Remover imports de `input_controller`

**Ficheiro completo refatorado:**

```python
"""
face_module.py — Webcam + Mediapipe Face Landmarker para SuperTuxKart.

Detecta APENAS:
  - Cabeça virada (yaw)         → Look Back (contínuo: P_LOOKBACK / R_LOOKBACK)
  - Aceno de cabeça (nod)       → Rescue    (impulso: RESCUE)

Envia comandos via UDP (send_fn) para o STK_input_server_v2.
"""

import math
import threading
import time

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

import config


def _blendshape_dict(result) -> dict:
    """Transforme la sortie brute de Mediapipe en dict {nom: score}."""
    if not result.face_blendshapes:
        return {}
    return {c.category_name: c.score for c in result.face_blendshapes[0]}


def _yaw_pitch_from_matrix(matrix) -> tuple[float, float]:
    """
    Extrait yaw/pitch (en degrés) approximatifs à partir de la matrice de
    transformation faciale renvoyée par Mediapipe.
    """
    r = np.array(matrix).reshape(4, 4)[:3, :3]
    pitch = math.degrees(math.atan2(-r[2, 0], math.sqrt(r[0, 0] ** 2 + r[1, 0] ** 2)))
    yaw = math.degrees(math.atan2(r[1, 0], r[0, 0]))
    return yaw, pitch


class _NodDetector:
    """Détecte un hochement de tête bref: le pitch descend puis remonte vite."""

    def __init__(self, dip_threshold_deg: float, max_duration_s: float):
        self.dip_threshold_deg = dip_threshold_deg
        self.max_duration_s = max_duration_s
        self._dip_start = None

    def update(self, pitch_deg: float) -> bool:
        """Retourne True au moment exact où un hochement complet est détecté."""
        now = time.monotonic()
        if pitch_deg < -self.dip_threshold_deg:
            if self._dip_start is None:
                self._dip_start = now
        else:
            if self._dip_start is not None:
                duration = now - self._dip_start
                self._dip_start = None
                if duration <= self.max_duration_s:
                    return True
        return False


class FaceWorker(threading.Thread):
    def __init__(self, send_fn):
        super().__init__(daemon=True)
        self._send_fn = send_fn
        self._stop_event = threading.Event()
        self._lookback_active = False       # estado para evitar spam de P_LOOKBACK
        self._last_rescue_time = 0.0        # cooldown do rescue

    def stop(self):
        self._stop_event.set()

    def run(self):
        base_options = mp_python.BaseOptions(model_asset_path=config.FACE_MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
        )
        landmarker = vision.FaceLandmarker.create_from_options(options)

        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        nod_detector = _NodDetector(config.NOD_PITCH_DIP_DEG, config.NOD_MAX_DURATION_S)
        start_time = time.monotonic()

        try:
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int((time.monotonic() - start_time) * 1000)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                # NÃO processar expressões (sorriso, boca, sobrancelhas, wink)
                # Apenas processar orientação da cabeça (yaw → look_back, nod → rescue)

                if result.facial_transformation_matrixes:
                    yaw, pitch = _yaw_pitch_from_matrix(
                        result.facial_transformation_matrixes[0]
                    )
                    self._process_head_pose(yaw, pitch, nod_detector)

                if config.DEBUG_WINDOW:
                    self._draw_debug(frame, yaw if result.facial_transformation_matrixes else 0.0)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
        finally:
            # Garantir que look_back é solto ao sair
            if self._lookback_active:
                self._send_fn("R_LOOKBACK")
                self._lookback_active = False
            cap.release()
            if config.DEBUG_WINDOW:
                cv2.destroyAllWindows()

    def _process_head_pose(self, yaw_deg: float, pitch_deg: float, nod_detector: _NodDetector):
        # --- Look Back (contínuo com estado) ---
        turned = abs(yaw_deg) > config.LOOK_BACK_YAW_THRESHOLD_DEG

        if turned and not self._lookback_active:
            self._send_fn("P_LOOKBACK")
            self._lookback_active = True
            print("[face] Look Back ATIVADO")
        elif not turned and self._lookback_active:
            self._send_fn("R_LOOKBACK")
            self._lookback_active = False
            print("[face] Look Back DESATIVADO")

        # --- Rescue (impulso via nod) ---
        if nod_detector.update(pitch_deg):
            now = time.monotonic()
            if now - self._last_rescue_time >= config.RESCUE_COOLDOWN_S:
                self._last_rescue_time = now
                self._send_fn("RESCUE")
                print("[face] RESCUE enviado (aceno de cabeça)")

    def _draw_debug(self, frame, yaw_deg: float):
        lb_text = "LOOK_BACK: ON" if self._lookback_active else "LOOK_BACK: off"
        color = (0, 0, 255) if self._lookback_active else (0, 255, 0)
        cv2.putText(frame, f"yaw: {yaw_deg:.1f} | {lb_text}", (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        cv2.imshow("Face Module (q para sair)", frame)
```

---

### PASSO 4: Criar `steer_module.py` (NOVO FICHEIRO)

Extrair a lógica do `steer.py` para um módulo importável. O `steer.py` original
**NÃO deve ser alterado** (manter para uso standalone).

**Regras:**
- Copiar toda a lógica do `steer.py` para `steer_module.py`
- A função principal é `start_steer(send_fn)`:
  - Recebe `send_fn` como parâmetro (em vez do socket UDP global do steer.py)
  - Substitui a chamada `send_command()` interna para usar `send_fn`
  - Lança as threads daemon: `steering_thread`, `release_watchdog`, `keyboard_listener_thread`
  - Inicia o servidor OSC na porta 8000 com os mesmos binds
  - **RETORNA** uma função `stop()` que faz cleanup (para o OSC, solta teclas)
  - **NÃO bloqueia** (sem `while True: sleep(1)`)
- Manter TODAS as constantes (DEAD_ZONE, MAX_STEER_ANGLE, EXPO_GAMMA, PWM_PERIOD, etc.)
- Manter TODA a lógica de steering PWM, filtro adaptativo, recalibração, etc.
- Manter o COMMANDS dict com "LEFT", "RIGHT", "ACCELERATE", "BRAKE"

**Esqueleto:**

```python
"""
steer_module.py — Módulo de steering importável (extraído do steer.py).

Controla direção (LEFT/RIGHT) e aceleração/freio via OSC do celular.
Envia comandos UDP através da send_fn recebida.
"""

import sys
import math
import threading
import time

from oscpy.server import OSCThreadServer

# --- Copiar TODAS as constantes do steer.py (DEAD_ZONE, MAX_STEER_ANGLE, etc.) ---

# ... (copiar as constantes das linhas 65-81 do steer.py)

COMMANDS = {
    "LEFT":       ("P_LEFT",       "R_LEFT"),
    "RIGHT":      ("P_RIGHT",      "R_RIGHT"),
    "ACCELERATE": ("P_ACCELERATE", "R_ACCELERATE"),
    "BRAKE":      ("P_BRAKE",      "R_BRAKE"),
}

# --- Estado partilhado (copiar do steer.py, linhas 86-100) ---

# ... (copiar todas as variáveis globais de estado)

# --- Funções auxiliares (copiar normalize_angle, trigger_recalibrate) ---

# ... (copiar exatamente como estão, mas usar _send_fn do módulo)

# --- Threads (copiar steering_thread, release_watchdog, keyboard_listener_thread) ---

# ... (copiar exatamente como estão, mas usar _send_fn do módulo)

# --- Callbacks OSC (copiar on_pitch, on_pad_x, on_multitouch_event) ---

# ... (copiar exatamente como estão)


# Variável global do módulo para a função de envio
_send_fn = None

def _module_send_command(command):
    """Wrapper que usa a send_fn injetada."""
    if _send_fn is not None:
        _send_fn(command)


def start_steer(send_fn):
    """
    Inicia o módulo de steering.

    Args:
        send_fn: Callable que recebe uma string e a envia via UDP.

    Returns:
        stop: Callable que para o módulo limpo.
    """
    global _send_fn
    _send_fn = send_fn

    # Substituir todas as chamadas a send_command no código copiado
    # para usar _module_send_command (que delega para _send_fn)

    # Lançar threads daemon
    threading.Thread(target=steering_thread, daemon=True).start()
    threading.Thread(target=release_watchdog, daemon=True).start()
    threading.Thread(target=keyboard_listener_thread, daemon=True).start()

    # Servidor OSC
    osc = OSCThreadServer()
    sock = osc.listen(address='0.0.0.0', port=8000, default=True)

    PITCH_ADDRESS = b'/multisense/orientation/pitch'
    PAD_ADDRESS_X = b'/multisense/pad/x'

    osc.bind(PITCH_ADDRESS, on_pitch)
    osc.bind(PAD_ADDRESS_X, on_pad_x)
    osc.bind(b'/multisense/pad/touches', on_multitouch_event)
    osc.bind(b'/multisense/pad/2/x', on_multitouch_event)
    osc.bind(b'/multisense/pad/2/y', on_multitouch_event)
    osc.bind(b'/multisense/multitouch', on_multitouch_event)

    print()
    print("=" * 65)
    print("🏎️  MÓDULO STEER INICIADO (OSC porta 8000 → UDP)")
    print("=" * 65)

    def stop():
        """Para o módulo de steering e solta todas as teclas."""
        global current_steer_dir, current_steer_intensity, current_vertical
        with lock:
            current_steer_dir = None
            current_steer_intensity = 0.0
            if current_vertical is not None:
                _module_send_command(COMMANDS[current_vertical][1])
                current_vertical = None
            _module_send_command("R_LEFT")
            _module_send_command("R_RIGHT")
        time.sleep(0.05)
        osc.stop()
        print("Módulo steer encerrado.")

    return stop
```

**IMPORTANTE**: No código copiado do `steer.py`, toda referência à função
`send_command()` original deve ser substituída por `_module_send_command()`.
Isto inclui:
- Dentro de `steering_thread` → `press()` e `release()`
- Dentro de `release_watchdog`
- Dentro de `trigger_recalibrate`
- Dentro de `on_pad_x`

O socket UDP original (`client_socket`) do `steer.py` **NÃO** deve ser criado
no `steer_module.py` — a `send_fn` recebida já cuida disso.

---

### PASSO 5: Criar `run_all.py` (NOVO FICHEIRO)

Este é o script principal que o utilizador vai executar.

```python
"""
run_all.py — Script unificado para controlar SuperTuxKart.

Pré-requisitos:
  1. STK_input_server_v2.py rodando em outro terminal
  2. Arduino com drift.ino ligado e na mesma rede Wi-Fi
  3. SuperTuxKart aberto e em primeiro plano

Módulos lançados:
  - SteerModule  (celular OSC)  → Direção + Aceleração/Freio
  - VoiceModule  (microfone)    → Turbo (NITRO) + Fire (FIRE)
  - FaceModule   (webcam)       → Look Back + Rescue

O Drift é gerido pelo Arduino de forma independente.
"""

import socket
import time

from config import STK_SERVER_ADDRESS

# ---------------------------------------------------------------------------
# Socket UDP partilhado — todos os módulos usam esta função
# ---------------------------------------------------------------------------
_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_command(command: str):
    """Envia um comando UDP para o STK_input_server_v2."""
    _udp_socket.sendto(command.encode('utf8'), STK_SERVER_ADDRESS)


# ---------------------------------------------------------------------------
# Importar módulos refatorados
# ---------------------------------------------------------------------------
from steer_module import start_steer
from face_module import FaceWorker
from voice_module import VoiceWorker


def main():
    # 1. Steer (celular OSC): direção + aceleração
    steer_stop = start_steer(send_command)

    # 2. Face (webcam): look_back + rescue
    face_worker = FaceWorker(send_command)
    face_worker.start()

    # 3. Voice (microfone): turbo + fire
    voice_worker = VoiceWorker(send_command)
    voice_worker.start()

    print()
    print("=" * 60)
    print("🏎️  TODOS OS MÓDULOS ATIVOS — SuperTuxKart Controller")
    print("=" * 60)
    print("  📱 Steer   (celular)  → Direção + Aceleração")
    print("  🎤 Voice   (micro)    → Turbo + Fire")
    print("  📷 Face    (webcam)   → Look Back + Rescue")
    print("  🕹️  Drift   (Arduino)  → Skidding (independente)")
    print()
    print("  Ctrl+C para parar.")
    print("=" * 60)
    print()

    try:
        while face_worker.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nEncerrando todos os módulos...")
    finally:
        # Parar módulos
        steer_stop()
        face_worker.stop()
        voice_worker.stop()
        face_worker.join(timeout=2)
        voice_worker.join(timeout=2)

        # Garantir que NENHUMA tecla fica presa
        for cmd in ["R_LEFT", "R_RIGHT", "R_ACCELERATE", "R_BRAKE", "R_LOOKBACK"]:
            send_command(cmd)

        _udp_socket.close()
        print("✅ Encerrado com sucesso. Nenhuma tecla ficou presa.")


if __name__ == "__main__":
    main()
```

---

### PASSO 6: Atualizar `requirements.txt`

Adicionar `oscpy` (usado pelo steer_module, não estava listado):

```
opencv-python
mediapipe
pynput
vosk
sounddevice
numpy
oscpy
```

---

## 5. Ordem de Execução para o Utilizador

```bash
# 1. Ligar o Arduino com drift.ino (USB ou bateria)
#    → Ele conecta ao Wi-Fi automaticamente

# 2. Terminal 1 — Servidor (PRIMEIRO)
python STK_input_server_v2.py

# 3. Abrir SuperTuxKart e entrar numa corrida

# 4. Terminal 2 — Controller unificado
python run_all.py

# 5. No celular: abrir MultiSense, ativar Orientation + Pad,
#    IP do PC, porta 8000
```

---

## 6. Verificações Finais (Testar Depois de Implementar)

- [ ] `python run_all.py` inicia sem erros
- [ ] Celular (OSC) controla **apenas** direção e aceleração — nada mais
- [ ] Gritar "turbo" envia `NITRO` — visível no servidor com `-d`
- [ ] Gritar "fire" envia `FIRE` — visível no servidor com `-d`
- [ ] Virar a cabeça envia `P_LOOKBACK` / `R_LOOKBACK` — visível no servidor com `-d`
- [ ] Acenar com a cabeça envia `RESCUE` — visível no servidor com `-d`
- [ ] Tocar no sensor do Arduino envia `P_SKIDDING` / `R_SKIDDING`
- [ ] `Ctrl+C` para tudo limpo, nenhuma tecla presa
- [ ] Face **NÃO** envia `P_ACCELERATE`, `FIRE`, `NITRO`, `P_LEFT`, `P_RIGHT`
- [ ] Voice **NÃO** envia `P_LOOKBACK`, `RESCUE`, `P_LEFT`, `P_ACCELERATE`

---

## 7. Mapa Final de Comandos

| Módulo | Dispositivo | Quando | Comando UDP |
|---|---|---|---|
| **Steer** | Celular | Inclina para esquerda | `P_LEFT` |
| **Steer** | Celular | Volta ao centro (esq) | `R_LEFT` |
| **Steer** | Celular | Inclina para direita | `P_RIGHT` |
| **Steer** | Celular | Volta ao centro (dir) | `R_RIGHT` |
| **Steer** | Celular | Toque na metade direita | `P_ACCELERATE` |
| **Steer** | Celular | Levanta dedo (acelerador) | `R_ACCELERATE` |
| **Steer** | Celular | Toque na metade esquerda | `P_BRAKE` |
| **Steer** | Celular | Levanta dedo (freio) | `R_BRAKE` |
| **Voice** | Microfone | Grita "turbo" | `NITRO` |
| **Voice** | Microfone | Grita "fire" | `FIRE` |
| **Face** | Webcam | Vira a cabeça (yaw > 35°) | `P_LOOKBACK` |
| **Face** | Webcam | Cabeça volta ao centro | `R_LOOKBACK` |
| **Face** | Webcam | Aceno de cabeça rápido | `RESCUE` |
| **Drift** | Arduino | Sensor tocado | `P_SKIDDING` |
| **Drift** | Arduino | Sensor solto | `R_SKIDDING` ×3 |

---

## 8. Estrutura Final de Ficheiros

```
stk_python_controller/
├── STK_input_server_v2.py     # NÃO ALTERAR — servidor UDP → pynput → STK
├── run_all.py                 # ✨ NOVO — script unificado
├── steer_module.py            # ✨ NOVO — lógica do steer.py como módulo importável
├── steer.py                   # NÃO ALTERAR — standalone original
├── face_module.py             # ✏️  REFATORAR — só look_back + rescue, via UDP
├── voice_module.py            # ✏️  REFATORAR — turbo + fire, via UDP
├── config.py                  # ✏️  PEQUENA ALTERAÇÃO — +STK_SERVER_ADDRESS, +VOICE_ACTION_MAP
├── input_controller.py        # NÃO ALTERAR — legado
├── main.py                    # NÃO ALTERAR — legado
├── drift.ino                  # NÃO ALTERAR — Arduino independente
├── requirements.txt           # ✏️  ADICIONAR oscpy
├── PLANO_INTEGRACAO.md        # ESTE FICHEIRO
└── models/                    # NÃO ALTERAR
```
