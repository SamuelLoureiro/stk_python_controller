# TRIO — Contrôleur Collaboratif Multi-Modal pour SuperTuxKart

Projet de conception d'interfaces et interaction gestuelle/vocale (UE MCSI).  
Ce module implémente une expérience de jeu coopérative à trois joueurs sur un unique kart dans **SuperTuxKart**, où chaque participant contrôle une modalité physique distincte du véhicule.

---

## 1. Principe & Répartition des Rôles

Le kart ne peut être piloté par une seule personne : la victoire repose sur la coordination et la synchronisation des trois joueurs en temps réel.

```
                  [ Écran de jeu ]
                         ▲
                         │
     [Joueur 1 : Assis] ─┼─► Direction (Smartphone sous la chaise, OSC UDP :8000)
                         │   + High-Five avec le joueur debout
                         │
     [Joueur 2 : Debout] ─┼─► Vitesse & Objets (Webcam MediaPipe : 6-7, Tête, High-Five)
                         │
     [Joueur 3 : Voix]   ───► Objets, Sauvetage & Turbo (Microphone, Vosk offline)
                         │
     [Capteur Matériel]  ───► Dérapage Drift (Arduino Wi-Fi UDP :6006)
```

| Rôle / Modalité | Capteur & Technologie | Action dans le jeu | Description |
|---|---|---|---|
| **Joueur 1 (Assis)** | Smartphone sous la chaise (OSC UDP :8000) | **Direction (Volant)** | Pivoter sur la chaise de bureau fait tourner le kart de façon proportionnelle. |
| **Joueur 2 (Debout)** | Webcam (MediaPipe Pose, 60 fps) | **Accélération / Frein / Tir** | Gestes corporels : mouvement 6-7 (accélérer), mains sur la tête (freiner), high-five (tirer). |
| **Joueur 3 (Voix)** | Microphone (Modèle Vosk offline) | **Objets & Nitro** | Commandes vocales anglaises : *"fire"*, *"turbo"*, *"help me"*. |
| **Drift (Arduino)** | Capteur tactile capacitif Grove (Wi-Fi) | **Dérapage (Drift)** | Contact sur le capteur physique pour déclencher le dérapage contrôlé. |

---

## 2. Architecture Technique

Le système repose sur une architecture découplée évitant les conflits d'entrées système :

```text
 ┌──────────────────────┐      ┌─────────────────────┐      ┌────────────────────┐
 │ Smartphone (OSC)     │      │ Webcam (MediaPipe)  │      │ Micro (Vosk)       │
 │ ZIG SIM / MultiSense │      │ poses et gestes     │      │ reconnaissance     │
 └──────────┬───────────┘      └──────────┬──────────┘      └─────────┬──────────┘
            │ OSC UDP :8000               │                           │
            ▼                             ▼                           ▼
        chaise.py                     webcam.py                    voix.py
            │                             │                           │
            └──────────────────────┬──────┴───────────────────────────┘
                                   │
                                   ▼
                                trio.py (Orchestrateur & Fusion)
                                   │
                                   │ Commandes UDP :6006 (STEER, P_ACCELERATE...)
                                   ▼
 ┌──────────────────────┐      ┌─────────────────────────────────────────────────┐
 │ Arduino UNO R4 / ESP │─────►│ serveur.py (Serveur UDP centralisé)             │
 │ Drift tactile Wi-Fi  │      │  ├── Linux : evdev / uinput (Xbox 360) + pynput │
 └──────────────────────┘      │  ├── Windows : vgamepad (Xbox 360) + keyboard   │
                               │  └── Fallback : touches modulées en fréquence   │
                               └───────────────────────┬─────────────────────────┘
                                                       │
                                                       ▼
                                                 SuperTuxKart
```

### Détail des composants :

- **Direction analogique (`chaise.py`, `direction.py`) :**  
  Lit les quaternions et données gyroscopiques reçus par OSC. Le capteur projette la rotation relative autour de l'axe vertical, rendant la mesure insensible à l'angle de fixation sous l'assise. La valeur est transmise à une manette virtuelle Xbox 360 (axe `ABS_X`). En l'absence de pilote de manette virtuelle, un fallback (`modulation.py`) émule un comportement analogique en modulant la fréquence d'impulsion des flèches gauche/droite.

- **Vision par ordinateur (`webcam.py`) :**  
  Traite le flux vidéo avec MediaPipe Pose.  
  - *Accélération :* Geste « 6-7 » (les deux mains devant le torse montant et descendant de manière alternée au-dessus d'un seuil) ou deux mains levées.  
  - *Freinage :* Mains posées sur la tête (distance poignets-tête minimale) ou une seule main levée.  
  - *High-Five :* Contact rapproché entre une main levée du joueur assis et une main du joueur debout, déclenchant l'envoi d'une impulsion `FIRE`.

- **Reconnaissance vocale (`voix.py`) :**  
  Utilise le moteur Kaldi/Vosk en local à 16 kHz. Une grammaire restreinte filtre les bruits parasites et déclenche instantanément les actions correspondantes (`fire`, `rescue`, `turbo`) avec un délai anti-rebond.

- **Dérapage Arduino (`drift.ino`) :**  
  Programme pour microcontrôleur Wi-Fi (Arduino UNO R4 WiFi ou ESP32). Le capteur tactile Grove sur A0 envoie des paquets UDP `P_SKIDDING` et `R_SKIDDING` avec répétition au relâchement pour pallier les éventuelles pertes de trames réseau.

- **Serveur central (`serveur.py`) :**  
  Écoute sur `0.0.0.0:6006` pour centraliser les requêtes venant de la machine locale et du Wi-Fi Arduino. Il garantit un temps d'appui minimal de 50 ms pour chaque commande afin que le moteur de SuperTuxKart enregistre chaque frappe de façon déterministe.

---

## 3. Structure du Répertoire

| Fichier | Rôle |
|---|---|
| `trio.py` | Point d'entrée principal coordonnant la chaise, la webcam et la voix. |
| `serveur.py` | Serveur UDP d'émulation manette et clavier vers le jeu. |
| `config_trio.py` | Centralisation de tous les paramètres (seuils, ports, gains, touches). |
| `chaise.py` | Serveur OSC et traitement de l'orientation smartphone (testable en autonome). |
| `direction.py` | Conversion de l'angle de la chaise en consigne de braquage (-1.0 à +1.0). |
| `webcam.py` | Pipeline de vision MediaPipe pour la détection des gestes (testable en autonome). |
| `voix.py` | Thread d'écoute audio et reconnaissance vocale avec Vosk. |
| `modulation.py` | Émulation de signal analogique par trains d'impulsions clavier. |
| `sortie_stk.py` | Gestionnaire thread-safe de sortie UDP avec arbitrage des touches opposées. |
| `reseau.py` | Utilitaire de détection d'adresses IP locales pour la configuration mobile. |
| `installer.py` | Script de téléchargement des modèles (Vosk et MediaPipe Pose) et de vérification. |
| `drift.ino` | Firmware Arduino / ESP32 pour le bouton tactile de dérapage Wi-Fi. |
| `lancer.ps1` | Script d'automatisation PowerShell ouvrant le serveur et le contrôleur. |
| `requirements.txt` | Dépendances Python requises. |

---

## 4. Installation & Prérequis

### Prérequis système
- **Python 3.9+**
- **SuperTuxKart** installé sur la machine
- **Linux :** permissions d'écriture sur `/dev/uinput` pour la manette virtuelle Xbox :
  ```bash
  sudo chmod 666 /dev/uinput
  ```
- **Windows :** pilote **ViGEmBus** installé si vous utilisez `vgamepad`.

### Installation de l'environnement

1. Cloner la branche `trio` et installer les dépendances :
   ```bash
   git clone -b trio https://github.com/maybeeeeeeeeeeeee/stk_python_controller.git
   cd stk_python_controller
   python3 -m venv .venv
   source .venv/bin/activate      # Sous Windows : .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Télécharger les modèles légers (Vosk ~40 Mo et MediaPipe Pose ~6 Mo) :
   ```bash
   python installer.py
   ```

---

## 5. Configuration & Lancement

### Étape 1 : Configurer le smartphone
1. Télécharger l'application **ZIG SIM** (iOS / Android) ou **MultiSense OSC** (Android).
2. Vérifier l'adresse IP locale de votre machine en lançant :
   ```bash
   python reseau.py
   ```
3. Dans l'application mobile :
   - **Target IP :** L'adresse IP de votre PC.
   - **Port :** `8000` (protocole UDP).
   - **Capteurs activés :**
     - ZIG SIM : `QUATERNION` et `GYRO`.
     - MultiSense : `Orientation` et `Gyroscope`.
4. Fixer le téléphone sous l'assise de la chaise de bureau pivotante.

### Étape 2 : Lancer le serveur d'entrée
Le serveur doit toujours être démarré en premier afin que le système d'exploitation et SuperTuxKart détectent la manette virtuelle :
```bash
python serveur.py -d
```
*(Le flag `-d` permet de voir les commandes reçues en direct dans le terminal).*

### Étape 3 : Lancer le contrôleur TRIO
Dans un second terminal :
```bash
python trio.py
```
*(Sous Windows, le script `.\lancer.ps1` lance automatiquement les deux fenêtres).*

Au démarrage, un compte à rebours sonore retentit : le joueur assis doit rester immobile face à l'écran pendant 3 secondes pour fixer le neutre de la chaise.

### Étape 4 : Lancer le jeu
1. Ouvrir **SuperTuxKart** en mode fenêtré.
2. Vérifier dans les options de commandes que la manette Xbox 360 virtuelle est reconnue (ou les touches fléchées).
3. Cliquez dans la fenêtre du jeu pour lui donner le focus et démarrez la course.

---

## 6. Options de Lancement utiles

```bash
python trio.py --solo           # Mode entraînement solo (le kart accélère tout seul)
python trio.py --fleches        # Force l'utilisation des flèches au lieu de la manette
python trio.py --simulation     # Affiche les commandes sans les envoyer au serveur
python trio.py --camera 1       # Sélectionne un autre index de caméra
python trio.py --journal run.csv # Enregistre l'ensemble des métriques de la partie
```

### Outils de diagnostic autonome
Chaque module peut être exécuté individuellement pour tester et calibrer le matériel :
```bash
python chaise.py                # Visualiseur interactif de l'orientation de la chaise
python webcam.py                # Visualiseur du squelette et test des gestes
python installer.py             # Vérification de l'environnement et des modèles
```

---

## 7. Commandes en cours de jeu

- **Touche `C`** : Recentre instantanément le volant de la chaise sur sa position actuelle (sans recalibration complète).
- **Touche `Q`** (ou `Ctrl+C`) : Quitte le programme proprement et relâche toutes les touches enfoncées.
