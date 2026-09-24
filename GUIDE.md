# TRIO — le guide complet, pas à pas

Tout ce qu'il faut pour **installer, tester et jouer**, dans l'ordre.

**Toutes les commandes se lancent depuis le dossier TRIO**, dans un terminal
PowerShell où l'environnement Python est actif : le prompt commence par
`(.venv)`. Rien d'autre à déclarer.

- Le **pourquoi** des choix (miroir, latence, niveaux) : [CONCEPTION.md](CONCEPTION.md).
- Le **résumé** du projet : [README.md](README.md).

## Sommaire

0. [Comprendre la chaîne en 30 secondes](#0-comprendre-la-chaîne-en-30-secondes)
1. [Installer](#1-installer)
2. [Tester sans rien : ni téléphone, ni jeu](#2-tester-sans-rien--ni-téléphone-ni-jeu)
3. [Le téléphone : le setup complet](#3-le-téléphone--le-setup-complet)
4. [Mesurer la chaise](#4-mesurer-la-chaise)
5. [Jouer seul](#5-jouer-seul)
6. [La voix](#6-la-voix)
7. [Le boîtier Arduino du sourd](#7-le-boîtier-arduino-du-sourd)
8. [Jouer à trois](#8-jouer-à-trois)
9. [Enregistrer une partie et l'analyser](#9-enregistrer-une-partie-et-lanalyser)
10. [Sauvetages inexpliqués](#10-sauvetages-inexpliqués)
11. [Arrêter proprement, touche bloquée](#11-arrêter-proprement-touche-bloquée)
12. [Partager avec git](#12-partager-avec-git)
13. [Dépannage](#13-dépannage)
14. [Toutes les options](#14-toutes-les-options)

---

## 0. Comprendre la chaîne en 30 secondes

```
 téléphone sous la chaise ──OSC, port 8000──┐
 boîtier Arduino ───────────UDP, port 6010──┼──> trio.py ──UDP, port 6006──> serveur.py ──> SuperTuxKart
 micro (voix) ──────────────────────────────┘                              (manette virtuelle + clavier)
```

Pour jouer, il faut toujours **trois choses ouvertes** :

| # | Quoi | Rôle |
|---|---|---|
| 1 | la fenêtre **SERVEUR** (`serveur.py`) | seule à toucher au clavier et à la manette virtuelle |
| 2 | la fenêtre **TRIO** (`trio.py`) | lit la chaise, le boîtier et la voix, et décide |
| 3 | **SuperTuxKart**, en mode fenêtré, **avec le focus** | reçoit les touches |

`.\lancer.ps1` ouvre les fenêtres 1 et 2 d'un coup. Le jeu se lance **après**,
parce que c'est le serveur qui crée la manette virtuelle.

> **La règle d'or : le focus.** Le serveur tape dans la fenêtre au premier plan.
> Si c'est un terminal qui a le focus, les touches partent dans le terminal.
> **Toujours cliquer dans la fenêtre du jeu** avant de jouer.

---

## 1. Installer

### 1.1 Si le dossier est déjà là et l'environnement actif

```powershell
python installer.py
```

Il vérifie Python et les paquets, télécharge le modèle de voix (~40 Mo) s'il
manque, essaie la manette virtuelle, puis contrôle les calculs. À la fin, soit
`Tout est pret`, soit la liste de ce qui reste à régler.

La création de la manette virtuelle fait le bruit de branchement d'un
périphérique : c'est normal.

### 1.2 Pour un coéquipier, depuis zéro

Il faut Python 3.11 (3.9 minimum), git, et SuperTuxKart 1.2.

```powershell
git clone -b trio https://github.com/maybeeeeeeeeeeeee/stk_python_controller.git TRIO
cd TRIO
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python installer.py
```

- `Activate.ps1` refusé (« l'exécution de scripts est désactivée ») : une fois
  pour toutes, `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- `pip install` propose d'installer **ViGEmBus**, le pilote de la manette
  virtuelle : accepter.
- Les fois suivantes : `cd TRIO` puis `.\.venv\Scripts\Activate.ps1`. VS Code le
  fait tout seul quand on ouvre le dossier.
- **Sous Linux** : `serveur.py` ne marche pas (manette Windows, et `keyboard`
  exige root). Utiliser `STK_input_server_v2.py` de la branche `performance`,
  qui parle le même langage.

### 1.3 Mettre SuperTuxKart dans une vraie fenêtre

SuperTuxKart doit être **fermé** (il réécrit sa configuration en quittant) :

```powershell
.\stk_fenetre.ps1                 # 1280 x 720, puis lance le jeu
.\stk_fenetre.ps1 -SansLancer     # règle seulement
```

Sur un écran mis à l'échelle (125 %), le jeu « fenêtré » peut faire pile la
taille de l'écran, et décocher « plein écran » ne change rien de visible.

### 1.4 Le pare-feu (si le téléphone ou le boîtier n'arrive pas)

Au premier lancement, Windows demande d'autoriser Python : **accepter sur les
réseaux privés**. Si la fenêtre a été refusée, dans un terminal
**administrateur** :

```powershell
New-NetFirewallRule -DisplayName "TRIO telephone 8000" -Direction Inbound -Protocol UDP -LocalPort 8000 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "TRIO boitier 6010"   -Direction Inbound -Protocol UDP -LocalPort 6010 -Action Allow -Profile Private
```

---

## 2. Tester sans rien : ni téléphone, ni jeu

Pour vérifier que le programme marche **avant** de toucher au matériel. Rien
n'est tapé au clavier. Il faut **deux terminaux** ouverts dans TRIO.

### 2.1 La chaise simulée (40 secondes)

```powershell
# TERMINAL 1 : trio en simulation (affiche les commandes, n'envoie rien)
python trio.py --aveugle --simulation
```

```powershell
# TERMINAL 2 : un faux téléphone qui déroule un scénario
python faux_chaise.py --profil multisense
```

Ce qu'on doit voir dans le terminal 1 :

| Étape annoncée par le terminal 2 | Terminal 1 |
|---|---|
| repos | trois bips, puis `calibre : neutre fixe` |
| l'aveugle tourne vers SA droite | des `-> STEER:-0.xxx` de plus en plus négatifs (miroir) |
| il passe vers SA gauche | `STEER` redevient positif |
| demi-tour | `-- DEMI-TOUR : l aveugle se retourne...` |
| flux coupé | `-- FLUX DU TELEPHONE COUPE : direction au centre --` puis `STEER:+0.000` |

Puis `Ctrl+C` dans le terminal 1. Variantes du faux téléphone :

```powershell
python faux_chaise.py --profil zigsim                   # façon iPhone
python faux_chaise.py --profil zigsim --ecran-dessous   # téléphone retourné
python faux_chaise.py --cap-initial 170                 # départ près de la coupure à 180°
python faux_chaise.py --biais-gyro 0.02                 # gyroscope qui dérive
python faux_chaise.py --angle 20 --duree 10             # tenir 20° pendant 10 s
python faux_chaise.py --verifier                        # contrôle des calculs, sans réseau
```

### 2.2 Le mode solo simulé

```powershell
python trio.py --solo --aveugle --simulation
```

En solo, **les signes sont inversés** par rapport à ce qu'annonce le faux
téléphone (pas de miroir), et le demi-tour ne déclenche rien. C'est normal.

### 2.3 Le boîtier Arduino simulé (12 secondes)

```powershell
# TERMINAL 1
python trio.py --arduino --simulation
```

```powershell
# TERMINAL 2
python faux_arduino.py
```

On doit voir dans l'ordre : `boitier connecte`, `P_ACCELERATE`, `FIRE`, `FIRE`,
`R_ACCELERATE`, `P_ACCELERATE`, puis `BOITIER MUET : tout est relache` et
`R_ACCELERATE`. Ce dernier relâchement prouve que le **watchdog** marche.

### 2.4 La chaîne complète, avec un serveur qui ne tape rien

```powershell
.\lancer.ps1 -Muet --solo
```

Deux fenêtres s'ouvrent : SERVEUR MUET et TRIO. Dans un troisième terminal,
`python faux_chaise.py`. Le serveur muet affiche chaque commande reçue : la
moitié réseau de la chaîne est vérifiée.

> **Une partie est en cours ?** Ne lance pas de faux téléphone sur le port
> 8000 : ses mesures se mélangeraient à celles du vrai. Pour tester à côté,
> changer de port des deux côtés :
> `python trio.py --aveugle --simulation --port 8100` avec
> `python faux_chaise.py --port 8100`.

---

## 3. Le téléphone : le setup complet

Compter une dizaine de minutes la première fois, deux ensuite. **Dans cet
ordre** :

1. le réseau ;
2. l'appli ;
3. vérifier que ça arrive ;
4. fixer le téléphone **en dernier**, parce que l'appli se règle bien plus
   facilement le téléphone en main.

### 3.1 Le réseau : le téléphone et le PC sur le même Wi-Fi

Le téléphone envoie ses mesures au PC par le Wi-Fi. Ils doivent être sur **le
même réseau**, et ce réseau doit laisser deux appareils se parler.

| Réseau | Est-ce que ça marche ? |
|---|---|
| **partage de connexion du téléphone**, avec le PC connecté dessus | **oui, partout** : la solution recommandée |
| Wi-Fi de la maison (box) | oui en général |
| Wi-Fi de l'université (eduroam…) | **souvent non** : ces réseaux isolent les appareils les uns des autres. Le téléphone émet, mais le PC ne reçoit rien |

**Partage de connexion depuis l'iPhone** :

1. iPhone : *Réglages → Partage de connexion → Autoriser d'autres
   utilisateurs* : activé. Activer aussi **Maximiser la compatibilité** : le
   réseau passe en 2,4 GHz, la seule bande que la carte Arduino UNO R4 sait
   joindre (§7).
2. PC : se connecter au Wi-Fi de l'iPhone (icône Wi-Fi de la barre des tâches).
3. L'IP du PC sera en `172.20.10.x`.

Le téléphone sous la chaise peut très bien être celui qui partage la connexion.

**Depuis un Android** : *Paramètres → Réseau et Internet → Point d'accès et
partage de connexion → Point d'accès Wi-Fi* (le chemin varie selon les
marques). Choisir la bande **2,4 GHz** si l'option existe, pour l'Arduino.

### 3.2 L'IP du PC

```powershell
python chaise.py
```

Tant qu'aucun téléphone n'émet, l'écran affiche
`IP a saisir dans l'application : 172.20.10.3 (Wi-Fi)` et le port **8000**.

- Prendre celle de la carte **Wi-Fi**, jamais une carte VMware, VirtualBox ou
  un « Ethernet » virtuel : le téléphone ne peut rien y envoyer.
- **Laisser tourner** : il sert aussi à vérifier la réception au §3.5.
- L'IP change quand on change de réseau : **la relire à chaque séance**.

### 3.3 iPhone : ZIG SIM

**Installer** : App Store → « ZIG SIM ».

**Régler**, une seule fois, puisque ZIG SIM retient ses réglages. Les onglets
sont en anglais, en bas de l'écran.

1. Onglet **Sensor** : activer **QUATERNION** et **GYRO**, et **désactiver tout
   le reste**. Sous la chaise, TOUCH enverrait des contacts parasites, et les
   capteurs inutiles noient le débogage.
2. Onglet **Settings** :

   | Réglage | Valeur |
   |---|---|
   | Data destination | **Other app** |
   | Protocol | **UDP** |
   | IP address | l'IP du PC (§3.2) |
   | Port number | **8000** |
   | Message format | **OSC** |
   | Message rate | **30** ou **60** (par seconde) |

3. Onglet **Start** : les valeurs défilent à l'écran, l'envoi est en cours.
   **Rester sur cet onglet** : c'est lui qui émet.

**Empêcher l'écran de s'éteindre** : *Réglages → Luminosité et affichage →
Verrouillage automatique → **Jamais***. Un écran qui s'éteint coupe le flux ; le
kart revient alors tout droit et la fenêtre TRIO affiche `[FLUX COUPE]`.

### 3.4 Android : MultiSense OSC

**Installer** : l'appli n'est plus sur le Play Store, il faut l'**APK** (fourni
sur le Moodle de l'UE). Copier l'APK sur le téléphone et l'ouvrir. Si Android
refuse, autoriser l'installation d'applications d'origine inconnue
(*Paramètres → Applications*), et vérifier l'espace libre.

**Régler et lancer** :

1. Ouvrir MultiSense OSC : il demande une **adresse IP** et un **port**. Mettre
   l'IP du PC (§3.2) et **8000**.
2. Choisir les données à envoyer : **Orientation** et **Gyroscope**, rien
   d'autre.
3. Appuyer sur le **bouton rouge** : l'envoi démarre.

**Empêcher l'écran de s'éteindre** : *Paramètres → Affichage → Mise en veille
de l'écran*, choisir la durée maximale. Mieux : brancher une batterie externe
et activer *Options pour les développeurs → Rester activé*, qui garde l'écran
allumé pendant la charge.

### 3.5 Vérifier que le PC reçoit, AVANT de fixer le téléphone

Dans la fenêtre de `chaise.py` (§3.2), dès que le téléphone émet :

- la première ligne affiche `profil=zigsim   iPhone 14 Pro` (ou `profil=multisense`) ;
- la deuxième affiche `orientation 30 Hz   gyro 30 Hz`.

Faire tourner le téléphone posé à plat sur la table : `CAP` et `GYRO` doivent
bouger. Puis **Q** pour quitter et libérer le port 8000, qu'un seul programme à
la fois peut écouter.

**Rien n'apparaît ?** Vérifier dans cet ordre :

1. même réseau ?
2. bonne IP (pas une carte VMware) ?
3. port 8000 ?
4. appli sur l'onglet Start, ou bouton rouge appuyé ?
5. pare-feu (§1.4) ?

`orientation 0 Hz` mais `gyro 30 Hz` (ou l'inverse) : un des deux capteurs n'est
pas activé dans l'appli.

### 3.6 Fixer le téléphone sous la chaise

```
            vue de côté

     ┌─────────────────────────┐    assise : elle tourne
     └───[▓▓▓▓▓▓▓]─────────────┘
          téléphone : dos contre l'assise, ÉCRAN VERS LE SOL
                 ║
                 ║   vérin
            ─────╨─────   pied étoile : il ne tourne pas
```

- **Le dos du téléphone contre le dessous de l'assise, écran vers le sol.**
  - Un écran collé à l'assise serait pressé en permanence. Les contacts
    parasites pourraient faire quitter l'onglet Start et couper le flux.
  - Écran vers le sol, on peut **se pencher pour vérifier** que les valeurs
    défilent toujours.
  - Le calcul est juste dans les deux sens (`python faux_chaise.py --verifier`).
- **Portrait ou paysage : peu importe pour la mesure.** Vérifié : portrait,
  paysage et même en biais donnent un angle exact. On choisit ce qui tient le
  mieux :
  - le **côté long d'avant en arrière** de l'assise ;
  - rien qui dépasse du bord, sinon les mollets de l'aveugle le heurtent ;
  - le **port de charge vers l'arrière** de la chaise, loin des jambes.
- **Sous l'assise, pas sur le pied étoile, qui ne tourne pas.** Selon les
  modèles, le vérin tourne ou non avec l'assise : ne pas compter dessus.
- **Pas besoin d'être au centre** : toute l'assise tourne du même angle. Si
  possible, **s'écarter du mécanisme en acier** du centre, qui peut perturber la
  boussole du téléphone (§4, test de l'acier).
- **Solide** : deux bandes de gaffer en croix, du velcro, ou un élastique large
  autour de l'assise. Le téléphone ne doit **jamais glisser** : s'il pivote sur
  lui-même, le neutre se décale.
- **Séance longue** : une batterie externe fixée à côté, câble branché.

### 3.7 Bloquer le téléphone dans l'appli (conseillé)

Sous la chaise, on ne voit pas si l'appli est toujours au premier plan.

**iPhone : l'Accès guidé** bloque l'iPhone dans ZIG SIM et coupe le tactile.

1. *Réglages → Accessibilité → Accès guidé* : activer, et définir un code. Dans
   le même menu, régler le verrouillage automatique de l'écran sur **Jamais**.
2. Ouvrir ZIG SIM sur l'onglet **Start**, puis **triple-clic sur le bouton
   latéral**.
3. *Options* : désactiver **Toucher**. Laisser **Mouvement** activé, par
   prudence. Puis *Démarrer*.
4. Pour sortir : triple-clic sur le bouton latéral, puis le code.

**Android : l'épinglage d'application.** *Paramètres → Sécurité → Épinglage
d'application* (le chemin varie selon les marques), puis épingler MultiSense
depuis l'écran des applications récentes.

### 3.8 La check-list avant chaque partie

- [ ] PC et téléphone sur le même réseau (partage de connexion)
- [ ] IP du PC relue dans `chaise.py`, la même que dans l'appli
- [ ] ZIG SIM : QUATERNION + GYRO, onglet Start ; ou MultiSense : Orientation + Gyroscope, bouton rouge
- [ ] `chaise.py` voit le téléphone (profil, fréquences), puis **Q**
- [ ] téléphone fixé écran vers le sol, verrouillage sur Jamais (ou Accès guidé)
- [ ] batterie suffisante, ou batterie externe

---

## 4. Mesurer la chaise

**Le jeu n'est pas nécessaire.** C'est l'étape qui règle les constantes.

```powershell
python chaise.py
```

Touches, avec la fenêtre du terminal active :

| Touche | Effet |
|---|---|
| **C** | calibrer : ne pas bouger pendant 1,5 s |
| **R** | la position actuelle devient le neutre |
| **Entrée** | noter un point dans le tableau |
| **Q** | quitter (affiche les points notés) |

### Déjà mesuré (2026-09-24, iPhone 14 Pro, ZIG SIM 30 Hz)

| Question | Mesure | Conclusion |
|---|---|---|
| le sens | à droite +66,0 / +66,6 ; à gauche −67,4 / −66,6 | signes bons |
| l'unité du gyro | gyro / cap = 1,0 | bonne unité (rad/s) |
| cap ou gyro | d'accord à ~1° près | on garde `cap` |

Il reste à refaire ces mesures **avec le téléphone fixé dessous** (plus près de
l'acier), et à mesurer l'amplitude **assis**.

### Le protocole (5 minutes)

1. **Repères au sol** : du scotch sous le bord de l'assise à **0°**, **+45°**,
   **−45°** et **+90°**. Le plus simple : l'assise pointe vers un mur à 0°, vers
   un mur voisin à 90°.
2. Assis, sur le 0 : **C**. La ligne du bas dit `calibre : ...`.
3. **Tourne vers TA droite.** `CAP` et `GYRO` doivent devenir **positifs**.
   Si l'un est négatif, change son signe dans `config_trio.py`, à la ligne
   `SIGNE_CAP` ou `SIGNE_GYRO`, pour le profil affiché en haut.
4. Place-toi sur chaque repère et appuie sur **Entrée**. Compare les angles lus
   aux vrais angles.
5. **Le test de l'acier** : fais 5 allers-retours rapides et reviens sur le 0.
   - `CAP` revient à 0 et `GYRO` aussi : on garde `METHODE_CHAISE = 'cap'`.
   - `CAP` ne revient pas à 0 mais `GYRO` si : l'acier fausse la boussole,
     mettre `METHODE_CHAISE = 'gyro'`.
6. **L'amplitude**, assis, en poussant avec les pieds : tourne aussi loin que
   c'est **confortable** et lis l'angle. Environ 80 % de cette valeur donne
   `ANGLE_MAXI`.
7. **L'unité du gyro** (MultiSense seulement) : après un grand mouvement, la
   ligne `gyro / cap = ...` le dit elle-même.

**Écris les valeurs mesurées en commentaire** dans `config_trio.py`, à côté de
la constante. Exemple :

```python
ANGLE_MAXI = 30.0               # mesure 2026-09-24 : 38 deg confortable, 80 % -> 30
```

Un changement de réglage demande de **relancer** `trio.py`.

---

## 5. Jouer seul

Seul, tu fais l'aveugle **face à l'écran**. Le mode `--solo` :

- **tourner à droite fait tourner le kart à droite** (pas de miroir) ;
- **le kart accélère tout seul** ;
- **pas de détection de demi-tour**, puisque tu regardes l'écran ;
- la voix marche si le micro est là (et le boîtier, s'il émet).

### 5.1 Lancer

Le téléphone émet, fixé sous la chaise (§3). SuperTuxKart est **fermé**.

```powershell
.\lancer.ps1 --solo
```

Deux fenêtres s'ouvrent : **SERVEUR STK** et **TRIO**.

Pour jouer **sans la voix** (micro absent, ou pour éviter tout faux
sauvetage) : `.\lancer.ps1 --solo --aveugle`.

### 5.2 La calibration

Dans la fenêtre TRIO :

1. `en attente du telephone...` : jusqu'à 30 s ;
2. `zigsim detecte ..., orientation 30 Hz, gyro 30 Hz` ;
3. **assis face à l'écran, immobile** : trois bips (3, 2, 1) ;
4. **bip aigu** = calibré. Deux bips graves = tu as bougé : il recommence tout
   seul, jusqu'à trois fois.

### 5.3 Lancer SuperTuxKart

**Après** le serveur, pour qu'il voie la manette virtuelle : depuis le menu
Démarrer, ou

```powershell
.\stk_fenetre.ps1
```

qui règle la fenêtre en 1280 × 720 **et** lance le jeu. Puis une course (par
exemple *En ligne → Réseau local → Créer un serveur → Créer → Commencer la
course*), un kart, une piste. **Au départ, cliquer dans la fenêtre du jeu.**

### 5.4 Pendant la course

| Tu fais | Le kart |
|---|---|
| tourner la chaise à droite, un peu ou beaucoup | tourne à droite, **proportionnellement** |
| revenir face à l'écran | va tout droit (zone morte de 5°) |
| dire « **fire** » | lance l'objet |
| dire « **turbo** » | nitro |
| dire « **help help** » (deux fois, en moins de 1,5 s) | sauvetage |
| dire « **center** » | la position actuelle devient le neutre |

La fenêtre TRIO affiche toutes les 0,5 s une ligne comme
`touches=[ACCELERATE]   aveugle: chaise= +12.3 steer=+0.21`.

> **Recentrer au clavier (touche C) vole le focus** : il faut cliquer dans la
> fenêtre TRIO pour appuyer sur C, puis **re-cliquer dans le jeu**. En course,
> dire « center » est plus simple.

### 5.5 Si le kart avance mais ne tourne pas

La direction passe par une manette Xbox virtuelle. Deux solutions :

**Immédiate : les flèches.** Fermer les deux fenêtres, puis :

```powershell
.\lancer.ps1 --solo --fleches
```

La flèche est battue en rythme : moins fluide, mais déjà validé en jeu.

**Propre : assigner le stick dans SuperTuxKart.** Normalement le stick gauche
d'une manette est déjà assigné à la direction, mais on peut le faire à la main :

1. fermer la fenêtre TRIO, garder le **SERVEUR** ouvert ;
2. dans SuperTuxKart : *Options → Contrôles*, choisir la manette **Xbox 360** ;
3. cliquer sur **Tourner à gauche** : le jeu attend un mouvement ;
4. dans un terminal : `python bouger_stick.py gauche`, puis **cliquer dans le
   jeu** pendant les 5 secondes d'attente ;
5. même chose pour **Tourner à droite** avec `python bouger_stick.py droite` ;
6. laisser **tout le reste au clavier**.

### 5.6 Ce qu'il faut noter

- [ ] l'amplitude confortable assis, donc `ANGLE_MAXI`
- [ ] `cap` revient-il à 0 avec le téléphone fixé dessous ?
- [ ] analogique ou `--fleches` : lequel a marché ?
- [ ] la voix a-t-elle compris les mots ? Des faux déclenchements ?

---

## 6. La voix

### 6.1 Choisir le bon micro

```powershell
python tester_voix.py --liste
```

Liste les micros avec leur numéro. Tester celui qu'on veut en parlant :

```powershell
python tester_voix.py --peripherique 1 --mots
```

Si la barre de niveau reste à plat, le micro est muet. Si elle bouge sans
qu'aucun mot n'apparaisse, c'est Vosk qui ne comprend pas : les mots sont
**anglais** (« fire » se dit « fa-ïeur »).

Pour garder ce micro à chaque partie : `MICRO = 1` dans `config_trio.py`, ou
`python trio.py --micro 1`.

### 6.2 Les mots

| Mot | Action | Combien de fois |
|---|---|---|
| **fire** | lancer l'objet | une |
| **turbo** | nitro | une |
| **help** | sauvetage | **deux**, en moins de 1,5 s (« help help ») |
| **center** | la chaise se recentre | une |

Pourquoi deux fois pour `help` : voir §10.

### 6.3 Tester la voix seule

```powershell
python trio.py --voix --simulation
```

Dire « fire » : la ligne `[voix] "fire" -> fire` apparaît. Dire « help » une
fois : `[voix] "help" (1/2) : redis-le...`. Le redire : `-> rescue`.

---

## 7. Le boîtier Arduino du sourd

Le programme de la carte est `arduino\boitier_sourd\boitier_sourd.ino`. **Il
n'a pas encore été testé sur la carte** ; la partie PC, elle, l'est (§2.3).

### 7.1 Les branchements (Grove Base Shield V2 sur l'UNO R4 WiFi)

| Port de la Base Shield | Capteur Grove | Action |
|---|---|---|
| **D2** | Touch Sensor | doigt posé = **accélérer** (tenu) |
| **A0** | Piezo Vibration Sensor | une tape = **lancer l'objet** |
| **D4** | Ultrasonic Ranger (optionnel) | main ou pied proche = **freiner** |

### 7.2 Téléverser

1. Arduino IDE → *Outils → Carte → Gestionnaire de cartes* → installer
   **Arduino UNO R4 Boards**.
2. *Outils → Carte* : **Arduino UNO R4 WiFi** ; *Outils → Port* : le `COMx` de
   la carte.
3. *Fichier → Ouvrir* : `arduino\boitier_sourd\boitier_sourd.ino`, dans le
   dossier TRIO.
4. En haut du fichier, remplir :
   - `WIFI_NOM` et `WIFI_MDP` : le **même réseau** que le PC, en **2,4 GHz**
     (partage de connexion de l'iPhone : *Maximiser la compatibilité*, §3.1) ;
   - `IP_PC(...)` : l'IP du PC (§3.2), avec des virgules, par exemple
     `IPAddress IP_PC(172, 20, 10, 3);` ;
   - `AVEC_ULTRASON = false` si le capteur à ultrason n'est pas branché.
5. **Téléverser** (la flèche →).
6. *Outils → Moniteur série*, **115200 bauds**. On doit lire
   `Connecte, IP de la carte : ...`, puis une ligne par seconde :
   `touche=0 dist=-1 tapes=0 piezo=12`.

Vérifier chaque capteur **dans le moniteur série**, avant de passer au PC :

- un doigt sur le Touch → `touche=1` ;
- une tape sur la table → `tapes` augmente ;
- la main devant l'ultrason → `dist` descend.

### 7.3 Côté PC

```powershell
python trio.py --arduino --simulation
```

La ligne d'état affiche `arduino: dist=.. piezo=.. tapes=.. touche=..` et
`[arduino] boitier connecte (IP de la carte)`.

### 7.4 Régler

| Réglage | Où | Comment |
|---|---|---|
| `SEUIL_PIEZO` | le `.ino` (**reflasher**) | lire `piezo=` au repos puis pendant une tape, et mettre le seuil entre les deux. Trop bas : des tirs sans taper. Trop haut : des tapes ignorées |
| `FREIN_CM` | `config_trio.py` (**sans reflasher**) | lire `dist=` pied posé et pied levé, et mettre la valeur entre les deux. `None` = pas de frein |

---

## 8. Jouer à trois

### 8.1 L'installation

```
                 ÉCRAN
                   │
               [ MUET ]      debout, voit l'écran par-dessus l'aveugle
                   │  gestes
             [ AVEUGLE ]     dos à l'écran, chaise pivotante sur un tapis
                            (téléphone sous l'assise)

   [ SOURD ]  sur le côté, casque sur les oreilles, boîtier sous la main
```

| Joueur | Il a | Règles à annoncer avant la partie |
|---|---|---|
| **aveugle** | la chaise | ne jamais se retourner vers l'écran : au-delà de 100°, le kart lâche les gaz |
| **muet** | les yeux, les mains, un objet repère voyant, un masque sur la bouche | ne jamais parler, ni articuler en silence ; **ne jamais toucher la chaise** |
| **sourd** | le boîtier, sa voix, un casque avec du bruit ou de la musique | il peut parler (« fire », « turbo »…) mais n'entend rien |

**Le guidage : suivre le repère.** Le muet tient l'objet repère à hauteur de
visage et le déplace vers le côté où le kart doit aller, **comme on le voit à
l'écran**. L'aveugle **tourne pour faire face au repère**, rien d'autre. Le
programme est réglé pour ça (`CORRESPONDANCE = 'miroir'`).

### 8.2 Lancer

```powershell
.\lancer.ps1
```

Puis :

1. dans la fenêtre TRIO, **l'aveugle face au muet, immobile**, pendant les
   trois bips ;
2. SuperTuxKart (`.\stk_fenetre.ps1` ou le menu Démarrer), une course, **clic
   dans la fenêtre du jeu** ;
3. le sourd pose le doigt sur le Touch : le kart avance.

### 8.3 Les variantes

```powershell
.\lancer.ps1 --auto                          # le boîtier n'est pas prêt : le kart accélère seul
.\lancer.ps1 --correspondance egocentrique   # le muet mime "à ta droite" au lieu du repère
.\lancer.ps1 --aveugle --voix                # sans le boîtier
.\lancer.ps1 --fleches                       # si la manette virtuelle ne marche pas (§5.5)
```

Les **niveaux de difficulté** se règlent en déplaçant les gens, sans rien
changer au code :

| Niveau | Qui voit l'écran |
|---|---|
| facile | le muet et le sourd |
| difficile | **le muet seul** : le sourd s'assoit lui aussi dos à l'écran, face au muet, qui le guide de l'autre main |

Les gestes du muet vers le sourd (proposition, à coller sur le boîtier) :

| Geste | Veut dire |
|---|---|
| main à plat qui pousse vers l'avant | accélère |
| poing fermé | freine |
| index pointé vers l'avant | tire l'objet |
| moulinet de la main | turbo |
| deux mains en l'air | sauvetage |

### 8.4 Pendant la partie

- **Le neutre a glissé** (le kart tire d'un côté alors que l'aveugle est face au
  muet) : n'importe qui dit « **center** ».
- La fenêtre TRIO annonce les événements : `DEMI-TOUR`, `FLUX DU TELEPHONE
  COUPE`, `BOITIER MUET`.

---

## 9. Enregistrer une partie et l'analyser

Pour l'évaluation du mini-projet :

```powershell
.\lancer.ps1 --journal journaux\equipe1_miroir.csv --duree 180
```

- `--journal` : un CSV avec une ligne d'état par image (angle de la chaise,
  consigne, touches) et une ligne par commande envoyée. Le dossier `journaux`
  est créé tout seul, et git l'ignore.
- `--duree 180` : s'arrête seul au bout de 3 minutes et relâche tout.
- Nommer les fichiers selon la condition testée : `equipe1_miroir.csv`,
  `equipe1_egocentrique.csv`, `equipe1_difficile.csv`…

**Analyser** : une ligne par partie, pour comparer les conditions.

```powershell
python analyser.py journaux\*.csv
```

| Colonne | Ce qu'elle dit |
|---|---|
| **inv/min** | inversions de braquage par minute : le kart zigzague, la consigne arrive trop tard ou le guidage est ambigu (CONCEPTION.md, §2) |
| sature | part du temps à braquage complet : `ANGLE_MAXI` trop petit, ou l'aveugle sur-corrige |
| demi-t | part du temps où l'aveugle s'est retourné |
| RESCUE | les sauvetages demandés par le programme (pas ceux que le jeu fait seul) |

---

## 10. Sauvetages inexpliqués

Un sauvetage (le kart ramené sur la piste) a **deux origines possibles**. La
fenêtre TRIO permet de les distinguer.

| Juste avant, la fenêtre TRIO affiche… | Origine | Quoi faire |
|---|---|---|
| `[voix] "help" -> rescue` | **la voix** a cru entendre « help » | voir ci-dessous |
| rien | **SuperTuxKart lui-même** : il ramène le kart tout seul quand il sort de la piste ou tombe | rien à corriger dans le code : c'est le jeu |

**Pourquoi la voix se trompe.** Vosk ne connaît que quatre mots : tout son est
ramené vers le plus proche, y compris la musique du jeu dans les haut-parleurs
et les paroles en français. D'où les règles :

- **« help » doit être dit deux fois** en moins de 1,5 s. Un bruit produit
  rarement deux fois le même mot (réglable : `MOTS_A_REPETER` dans
  `config_trio.py`).
- **Voir ce que Vosk entend** : pendant une course, musique comprise, lancer
  `python tester_voix.py --mots --duree 120`. Chaque mot reconnu s'affiche
  avec son heure. S'il en apparaît alors que personne ne parle : casque-micro,
  ou baisser le son du jeu.
- **Jouer sans la voix** : `.\lancer.ps1 --solo --aveugle`.

---

## 11. Arrêter proprement, touche bloquée

- **Arrêter** : **Q** dans la fenêtre TRIO, ou `Ctrl+C`. Toutes les touches sont
  relâchées et la direction revient au centre (`Arrete, tout est relache.`).
  Fermer ensuite la fenêtre SERVEUR avec `Ctrl+C`.
- **Une touche est restée enfoncée**, par exemple après la fermeture d'une
  fenêtre à la croix :

```powershell
python relacher.py
```

---

## 12. Partager avec git

Ce dossier **est** la branche `trio` du dépôt de l'équipe : il ne contient
que TRIO, et il se suffit à lui-même.

**Envoyer ses modifications** :

```powershell
git status                          # voir ce qui a changé
git add -A
git commit -m "ce que j'ai change"
git push -u origin trio             # la premiere fois
git push                            # les fois suivantes
```

**Récupérer celles des autres** : `git pull`.

Ne partent **jamais** dans git : le modèle de voix (`models/`, retéléchargé
par `python installer.py`), les journaux (`journaux/`, `*.csv`), les
environnements Python.

---

## 13. Dépannage

| Symptôme | Cause probable | Quoi faire |
|---|---|---|
| `ModuleNotFoundError` | l'environnement n'est pas actif | `.\.venv\Scripts\Activate.ps1`, puis `pip install -r requirements.txt` |
| `aucune donnee en 30 s` | IP ou port faux, capteurs non activés, téléphone verrouillé | `python chaise.py` pour voir ce qui arrive (§3.5) |
| `port 8000 deja utilise` | `chaise.py` ou un autre `trio.py` tourne encore | le fermer (**Q** ou `Ctrl+C`) |
| `Le port 6006 est deja utilise` (fenêtre serveur) | un autre serveur tourne déjà | fermer l'autre fenêtre serveur |
| `REFUSE : la chaise a bouge` | quelqu'un a bougé pendant les bips | rien : il recommence seul |
| le kart tourne du mauvais côté | signe du capteur, ou correspondance | `chaise.py` : positif à droite ? **Non** → `SIGNE_*`. **Oui** → `CORRESPONDANCE` (en solo, forcée à égocentrique) |
| le kart avance mais ne tourne jamais | le jeu ignore la manette virtuelle | `--fleches` (§5.5) |
| le kart ne bouge pas du tout | focus, ou accélération non demandée | cliquer dans le jeu ; `--auto` ou `--solo` ; la fenêtre SERVEUR doit afficher `P_ACCELERATE` |
| les touches s'écrivent dans un terminal | le focus est sur le terminal | cliquer dans le jeu |
| sauvetages inattendus | la voix, ou le jeu lui-même | §10 |
| le kart dérive tout seul peu à peu | méthode `gyro` qui dérive | dire « center » ; ou `--methode cap` |
| `[FLUX COUPE]` en boucle | écran du téléphone éteint, appli en arrière-plan | verrouillage sur **Jamais**, appli au premier plan (§3.7) |
| `[DEMI-TOUR]` alors que personne ne se retourne | le neutre a glissé | dire « center » |
| `(repli gyro)` dans la ligne d'état | QUATERNION (ou Orientation) n'est pas activé | l'activer dans l'appli |
| la voix n'entend rien | mauvais micro | §6.1, puis `--micro N` |
| le boîtier reste `en attente sur le port 6010` | IP du PC fausse dans le `.ino`, autre réseau, ou pare-feu | moniteur série (§7.2), §1.4 |
| `BOITIER MUET` en pleine partie | Wi-Fi de la carte coupé | la LED clignote pendant la reconnexion ; tout est relâché en attendant |
| le jeu remplit tout l'écran | fenêtre à la taille de l'écran | §1.3 |
| `l'exécution de scripts est désactivée` | politique PowerShell | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (une fois) |

---

## 14. Toutes les options

### `trio.py`

| Option | Effet |
|---|---|
| *(aucune)* | tout ce qui peut démarrer : chaise, boîtier, voix |
| `--aveugle` / `--arduino` / `--voix` | seulement ces rôles (se combinent) |
| `--solo` | un joueur face à l'écran : égocentrique, accélération automatique, pas de demi-tour |
| `--auto` | le kart accélère tout seul |
| `--fleches` | direction par flèches battues en rythme au lieu de la manette virtuelle |
| `--correspondance miroir` ou `egocentrique` | sens chaise → kart |
| `--methode cap` ou `gyro` | méthode de mesure de la chaise |
| `--simulation` | affiche les commandes sans rien envoyer |
| `--silencieux` | n'affiche plus chaque commande (la ligne d'état reste) |
| `--journal FICHIER.csv` | enregistre la partie |
| `--duree S` | s'arrête seul au bout de S secondes |
| `--port N` | port OSC du téléphone (8000) |
| `--port-arduino N` | port du boîtier (6010) |
| `--micro N` | numéro du micro |

Dans la fenêtre TRIO : **C** recentre la chaise, **Q** quitte.

### `lancer.ps1`

Toutes les options de `trio.py` passent telles quelles. En plus : `-Muet`,
pour un serveur qui affiche tout et ne tape rien.

### Les autres scripts

| Commande | Rôle |
|---|---|
| `python installer.py` | vérifications + modèle de voix |
| `python chaise.py` | l'outil de mesure de la chaise (§4) ; `--profil`, `--methode`, `-p PORT` |
| `python tester_voix.py` | micro et mots reconnus (§6) ; `--liste`, `--mots`, `--duree`, `--peripherique` |
| `python faux_chaise.py` | faux téléphone (§2) ; `--verifier`, `--profil`, `--ecran-dessous`, `--cap-initial`, `--biais-gyro`, `--angle`, `--duree`, `--port`, `--hz` |
| `python faux_arduino.py` | faux boîtier (§2.3) ; `--port`, `--hote` |
| `python analyser.py FICHIERS` | résumé des journaux (§9) |
| `python relacher.py` | relâche toutes les touches (§11) |
| `python bouger_stick.py gauche` | fait bouger le stick pour l'assigner dans le jeu (§5.5) |
| `python serveur.py -d` | le serveur seul (d'habitude ouvert par `lancer.ps1`) |
| `python serveur_muet.py` | un serveur qui ne tape rien |
| `.\stk_fenetre.ps1` | met SuperTuxKart en 1280 × 720 et le lance ; `-SansLancer`, `-Largeur`, `-Hauteur` |

### Les réglages de `config_trio.py`

| Réglage | Défaut | Rôle |
|---|---|---|
| `METHODE_CHAISE` | `'cap'` | `'cap'` ou `'gyro'` (§4) |
| `SIGNE_CAP`, `SIGNE_GYRO` | par appli | ZIG SIM mesuré ; MultiSense à vérifier avec `chaise.py` |
| `UNITE_GYRO` | `'rad'` | `'deg'` si `gyro / cap` vaut environ 57 |
| `AXE_GYRO_MULTISENSE` | `'z'` | l'axe de la chaise affiché par `chaise.py` |
| `CORRESPONDANCE` | `'miroir'` | `'egocentrique'` |
| `DIRECTION` | `'analogique'` | `'fleches'` |
| `ANGLE_MINI` / `ANGLE_MAXI` | 5° / 35° | zone morte / braquage complet |
| `COURBE` | 1,5 | plus grand = plus doux près du centre |
| `ANGLE_DEMI_TOUR` | 100° | `None` pour désactiver |
| `ACCELERATION` | `'sourd'` | `'automatique'` |
| `MOTS_VOIX` | fire, turbo, help, center | modèle anglais : mots anglais |
| `MOTS_A_REPETER` | `{'help': 1.5}` | mots à dire deux fois, et en combien de secondes |
| `MICRO` | `None` | numéro du micro |
| `FREIN_CM` | `None` | seuil de la pédale à ultrason |
| `WATCHDOG_ARDUINO` | 0,5 s | silence du boîtier avant de tout relâcher |
| `SILENCE_MAX` | 0,5 s | silence du téléphone avant de remettre la direction au centre |
