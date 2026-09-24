# TRIO — trois joueurs, un kart : l'aveugle, le muet, le sourd

Volet collaboratif du mini-projet SuperTuxKart (UE MCSI, M2 SIIA). Personne ne
peut conduire seul : chacun n'a qu'une partie de ce qu'il faut. Inspiré du jeu
BOMBANANA!, où trois joueurs aux sens limités désamorcent une bombe ensemble.

| Rôle | Contrainte | Ce qu'il fait |
|---|---|---|
| **aveugle** | dos à l'écran, sur une chaise pivotante | **tourne la chaise = braque le kart** (téléphone fixé sous l'assise) |
| **muet** | face à l'aveugle, voit l'écran, ne parle pas | le guide par gestes — aucune entrée dans le système |
| **sourd** | casque antibruit | accélère, freine, gère les objets : **boîtier Arduino + voix** |

```
  écran                     téléphone sous l'assise --OSC:8000--.
    |                        boîtier Arduino ----------UDP:6010--->  trio.py --UDP:6006--> serveur.py --> SuperTuxKart
  [MUET]  (voit l'écran)     micro (Vosk) ------------------------'                         (manette virtuelle + clavier)
    |  gestes
 [AVEUGLE] (dos à l'écran, sur la chaise)          [SOURD] (casque, boîtier)
```

**Ce dossier se suffit à lui-même** : aucun fichier extérieur, aucun chemin en
dur. Il est la branche `trio` du dépôt de l'équipe.

| Document | Pour quoi |
|---|---|
| **[GUIDE.md](GUIDE.md)** | **tout, pas à pas** : installation, téléphone, tests, jeu, dépannage |
| [CONCEPTION.md](CONCEPTION.md) | l'analyse de l'idée, les propositions d'interaction, l'évaluation |

---

## Démarrage rapide

Dans un terminal ouvert dans ce dossier, l'environnement Python actif :

```powershell
pip install -r requirements.txt     # une fois
python installer.py                 # une fois : modèle de voix + vérifications
python chaise.py                    # le téléphone arrive-t-il ? (IP à saisir, fréquences)
.\lancer.ps1 --solo                 # jouer seul, face à l'écran
.\lancer.ps1                        # jouer à trois
```

Depuis zéro, chez un coéquipier :

```powershell
git clone -b trio https://github.com/maybeeeeeeeeeeeee/stk_python_controller.git TRIO
cd TRIO
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python installer.py
```

Le téléphone : **ZIG SIM** (iPhone, capteurs QUATERNION + GYRO) ou
**MultiSense OSC** (Android, Orientation + Gyroscope), vers l'IP du PC, port
8000. Le setup complet est dans le GUIDE, §3.

---

## Les fichiers

| Fichier | Rôle |
|---|---|
| `trio.py` | **le jeu** : rôles, calibration aux bips, boucle à 60 Hz, journal CSV |
| `lancer.ps1` | ouvre le serveur et TRIO dans deux fenêtres |
| `serveur.py` | le seul qui touche au clavier et à la manette virtuelle (port 6006) |
| `chaise.py` | le capteur sous la chaise (MultiSense **et** ZIG SIM) ; lancé seul = **outil de mesure** |
| `aveugle.py` | angle de la chaise → direction (zone morte, courbe, miroir), demi-tour, flux coupé |
| `sourd.py` | la voix (Vosk) et la réception du boîtier Arduino |
| `sortie_stk.py` | fusionne les demandes, annule les opposées, n'envoie que les changements |
| `modulation.py` | angle → intensité ; flèche battue en rythme (mode `--fleches`) |
| `reseau.py` | l'IP du PC à saisir dans l'appli |
| `config_trio.py` | **tous les réglages** |
| `installer.py` | vérifications, téléchargement du modèle de voix |
| `tester_voix.py` | micro et mots reconnus : diagnostic de la voix |
| `faux_chaise.py` / `faux_arduino.py` | faux téléphone / faux boîtier ; `faux_chaise.py --verifier` contrôle les calculs |
| `analyser.py` | résumé des journaux de partie, pour l'évaluation |
| `relacher.py` | relâche une touche restée enfoncée |
| `bouger_stick.py` | fait bouger la manette virtuelle, pour l'assigner dans le jeu |
| `serveur_muet.py` | un serveur qui affiche tout et ne tape rien |
| `stk_fenetre.ps1` | met SuperTuxKart dans une vraie fenêtre, et le lance |
| `arduino/boitier_sourd/boitier_sourd.ino` | le programme du boîtier (UNO R4 WiFi + Grove) |
| `requirements.txt`, `.gitignore` | paquets ; ce qui ne va pas dans git (`models/`, journaux) |

---

## Les idées qui tiennent le tout

- **La chaise mesure un cap, pas une inclinaison.** Pivoter autour de la
  verticale ne change pas la gravité : l'angle de volant habituel resterait
  figé. `chaise.py` prend la rotation du téléphone autour de la verticale,
  exacte quel que soit son montage.
- **Le miroir.** Face à face, la droite de l'écran est la gauche de l'aveugle.
  Le muet tient un objet repère, l'aveugle tourne pour lui faire face : personne
  n'inverse rien de tête (`CORRESPONDANCE = 'miroir'`).
- **Les règles tenues par le système** :
  - l'aveugle qui se retourne vers l'écran fait lâcher les gaz ;
  - un téléphone qui se tait remet la direction au centre ;
  - un boîtier qui se tait relâche l'accélérateur.
- **Les actions coûteuses se confirment** : le sauvetage vocal demande « help »
  **deux fois**. La reconnaissance vocale, limitée à quatre mots, entend parfois
  des mots que personne n'a dits.

Le détail et les propositions : [CONCEPTION.md](CONCEPTION.md).

---

## Ce qui est vérifié, et ce qui ne l'est pas

Vérifié :

- **le calcul de l'angle** est exact à 10⁻¹³ degré près sur tous les montages
  (écran dessus ou dessous, portrait, paysage, incliné, vertical), y compris au
  passage de ±180° et avec un gyro biaisé (`python faux_chaise.py --verifier`) ;
- **sur le vrai iPhone 14 Pro** (2026-09-24) : les signes sont bons, l'unité
  du gyro aussi, et `cap` et `gyro` restent d'accord à ~1° près sur ±66° ;
- **en jeu, en solo** : la chaise pilote le kart ;
- **sans matériel** :
  - la chaîne jusqu'au serveur, en MultiSense comme en ZIG SIM ;
  - le demi-tour, le flux coupé, `--solo`, `--fleches` ;
  - le boîtier simulé et son watchdog ;
  - la règle des deux « help ».

Pas encore vérifié :

- le téléphone **fixé** sous l'assise, près de l'acier ;
- le programme Arduino sur la carte ;
- une partie à trois.
