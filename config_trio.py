#!/usr/bin/env python3
"""Tous les reglages du trio aveugle / muet / sourd, au meme endroit.

Le dossier est autonome : tout ce dont il a besoin est a cote de ce fichier, et
le modele de voix se telecharge avec `python installer.py`.

Les valeurs marquees "SUPPOSE" sont deduites de la physique ou de la doc, pas
encore mesurees. Elles se verifient en une minute avec `python chaise.py`
(GUIDE.md, section 5), et la mesure s'ecrit ensuite ici, en commentaire a cote
de la constante.
"""

import os

DOSSIER_TRIO = os.path.dirname(os.path.abspath(__file__))
MODELE_VOSK = os.path.join(DOSSIER_TRIO, 'models', 'vosk-model-small-en-us-0.15')

# ---------------------------------------------------------------------------
# Reseau. Trois ports, trois emetteurs :
#   8000  le telephone sous la chaise (OSC, MultiSense ou ZIG SIM)
#   6010  le boitier Arduino du sourd (texte UDP, un etat toutes les 50 ms)
#   6006  le serveur d'entree, qui seul touche au clavier et a la manette
# ---------------------------------------------------------------------------
SERVEUR_STK = ('localhost', 6006)
PORT_OSC_CHAISE = 8000
PORT_ARDUINO = 6010

# ---------------------------------------------------------------------------
# La chaise : comment on mesure l'angle
# ---------------------------------------------------------------------------
# 'cap'  : orientation absolue fournie par le telephone.
#            ZIG SIM    -> rotation du quaternion autour de la verticale
#            MultiSense -> /multisense/orientation/yaw
#          Pas de derive, mais si le telephone la cale sur la boussole,
#          l'acier du verin de la chaise peut la fausser.
# 'gyro' : vitesse de rotation integree. Insensible a l'acier, mais derive
#          lentement (recalibrer avec C ou en disant "center").
# C'est la mesure qui tranche : `python chaise.py` affiche les deux cote a
# cote. Si leur ecart grandit a chaque aller-retour, garder 'gyro'.
#
# MESURE 2026-09-24, iPhone 14 Pro / ZIG SIM 30 Hz : cap et gyro d'accord a
# ~1 deg pres sur +-66 deg (+66.0 / +66.6, -67.4 / -66.6), pas de perturbation
# visible. Telephone seulement pose sur l'assise, chaise soulevee en tournant :
# a reconfirmer une fois fixe DESSOUS, plus pres du mecanisme en acier.
METHODE_CHAISE = 'cap'

# Convention interne : angle > 0 quand l'aveugle tourne vers SA droite
# (sens des aiguilles d'une montre, vu de dessus). Ces signes ramenent chaque
# mesure brute a cette convention.
#
# ZIG SIM, cap et gyro : -1, MESURE le 2026-09-24 (iPhone 14 Pro) : tourne a
#   droite -> cap +66.0 / gyro +66.6, a gauche -> -67.4 / -66.6. C'etait bien
#   ce que predisait la regle de la main droite (z de CoreMotion vers le haut,
#   rotation positive = sens inverse des aiguilles = vers la GAUCHE).
# MultiSense, cap : SUPPOSE +1. Le yaw d'Android (azimut) croit vers l'est,
#   dans le sens des aiguilles.
# MultiSense, gyro : SUPPOSE -1 pour un telephone ecran vers le HAUT, +1 ecran
#   vers le BAS (l'axe z du telephone se retourne avec lui). A mesurer.
SIGNE_CAP = {'zigsim': -1, 'multisense': +1}
SIGNE_GYRO = {'zigsim': -1, 'multisense': -1}

# Axe du gyroscope de MultiSense qui porte la rotation de la chaise. 'z' pour
# un telephone pose a plat. `python chaise.py` affiche l'axe dominant.
# (ZIG SIM n'en a pas besoin : le gyro est projete sur la verticale donnee par
# le quaternion, quelle que soit la facon dont le telephone est fixe.)
AXE_GYRO_MULTISENSE = 'z'

# Unite du gyroscope. CoreMotion donne des rad/s. Pour MultiSense c'est la
# question Q11 jamais tranchee : `python chaise.py` affiche le rapport
# gyro / cap sur un grand mouvement. ~57 => mettre 'deg' ; ~0,017 => 'rad'.
# ZIG SIM : 'rad' confirme le 2026-09-24 (gyro / cap = 1,0 a 66 deg).
UNITE_GYRO = {'zigsim': 'rad', 'multisense': 'rad'}

# Calibration : duree pendant laquelle la chaise doit rester immobile (neutre
# + biais du gyro), et agitation au-dela de laquelle on refuse de calibrer.
DUREE_CALIBRATION = 1.5         # s
AGITATION_MAX = 3.0             # deg/s, moyenne quadratique de la vitesse verticale

# Sans message du telephone depuis ce delai, la direction revient au centre :
# ecran verrouille, appli fermee, Wi-Fi coupe. ZIG SIM et MultiSense emettent a
# 30 Hz ou plus : 0,5 s = 15 messages manques, ce n'est plus un trou de reseau.
SILENCE_MAX = 0.5

# ---------------------------------------------------------------------------
# La chaise : ce que l'angle fait au kart
# ---------------------------------------------------------------------------
# Le muet et l'aveugle sont face a face : la droite de l'ecran est la GAUCHE
# de l'aveugle.
#   'miroir'       l'aveugle tourne vers sa gauche -> le kart tourne a droite.
#                  C'est ce qu'il faut quand l'aveugle suit un objet que le
#                  muet tient devant lui (il tourne pour lui faire face) : le
#                  muet pense en coordonnees de l'ecran, l'aveugle suit, et
#                  personne n'inverse rien de tete. Voir CONCEPTION.md, §3.
#   'egocentrique' l'aveugle tourne vers sa droite -> le kart tourne a droite.
#                  Pour le jeu en chaine, quand la consigne arrive par la voix
#                  ("droite !").
# Ce reglage est un choix de conception, PAS un signe de capteur : si le kart
# part du mauvais cote alors que `chaise.py` affiche le bon signe, c'est ici ;
# si `chaise.py` affiche deja le mauvais signe, c'est SIGNE_CAP / SIGNE_GYRO.
CORRESPONDANCE = 'miroir'

# Comment la direction arrive au jeu :
#   'analogique' STEER:<-1..+1> vers serveur.py, qui le donne
#                a l'axe d'une manette Xbox virtuelle. Le plus fluide.
#   'fleches'    la fleche est battue en rythme cote client (ToucheModulee de
#                modulation.py, methode deja validee en jeu). Marche avec
#                N'IMPORTE QUEL serveur : c'est le repli si le jeu ignore la
#                manette virtuelle.
DIRECTION = 'analogique'

# Zone morte, braquage complet, courbe. Points de depart, A REGLER sur la
# vraie chaise : faire tourner l'aveugle aussi loin qu'il le peut
# confortablement, lire l'angle dans `chaise.py`, et prendre ~80 % de ca.
ANGLE_MINI = 5.0                # deg : en dessous, roues droites
ANGLE_MAXI = 35.0               # deg : au-dela, braquage complet
COURBE = 1.5                    # > 1 : plus doux pres du neutre

# L'aveugle qui pivote au-dela de cet angle est en train de se retourner pour
# regarder l'ecran : le kart lache les gaz tant qu'il ne revient pas. Une
# hysteresis evite le clignotement quand il hesite pile a la limite.
ANGLE_DEMI_TOUR = 100.0         # deg ; None = pas de detection (mode --solo)
HYSTERESIS_DEMI_TOUR = 20.0     # deg

# ---------------------------------------------------------------------------
# Le sourd
# ---------------------------------------------------------------------------
# 'sourd'       il tient l'acceleration (capteur tactile du boitier Arduino)
# 'automatique' le kart accelere tout seul : pour tester sans le boitier
ACCELERATION = 'sourd'

# Voix : mot crie -> action. Vosk ne reconnait QUE ces mots (grammaire
# restreinte), ce qui le rend rapide et fiable sur un mot crie en course.
# Modele anglais : les mots doivent etre anglais. 'center' ne va pas au jeu :
# il recalibre le neutre de la chaise.
MOTS_VOIX = {
    'fire':   'fire',       # lancer l'objet
    'turbo':  'turbo',      # nitro
    'help':   'rescue',     # sauvetage
    'center': 'recentrer',  # l'aveugle est face au muet : c'est le neutre
}
# Filet contre les revisions de Vosk. Les repetitions dans une meme phrase
# sont deja comptees une a une (sourd.VoixSourd._traiter) ; ce delai empeche
# seulement qu'un "fire" revu par le reconnaisseur parte deux fois.
DELAI_VOIX = 0.5            # s avant qu'un meme mot puisse redeclencher

# Mots qu'il faut dire DEUX FOIS, dans ce delai en secondes, pour agir. Pour
# les actions couteuses : un sauvetage fait perdre plusieurs secondes. Le
# 2026-09-24, en solo, des sauvetages sont partis tout seuls : avec une
# grammaire de quatre mots, Vosk ramene n'importe quel son (musique du jeu,
# paroles en francais) vers le mot le plus proche. Un bruit produit rarement
# deux fois le meme mot en 1,5 s. Diagnostic : python tester_voix.py --mots.
MOTS_A_REPETER = {'help': 1.5}
MICRO = None                # numero du micro, None = defaut de Windows
                            # (liste : python tester_voix.py --liste)

# Boitier Arduino. Il envoie son ETAT (pas des evenements) toutes les 50 ms :
#   touche=1 dist=23 tapes=12 piezo=412
# Au-dela de ce silence, on relache tout ce qu'il tenait : une carte qui
# redemarre en plein virage ne doit pas laisser l'accelerateur enfonce.
WATCHDOG_ARDUINO = 0.5      # s

# Pedale a ultrason : frein quand la main ou le pied passe sous cette distance.
# Seuil cote PC et pas dans le .ino, pour le regler sans reflasher la carte.
# None = pas de pedale (dist ignoree).
FREIN_CM = None             # ex. 15 ; a regler en lisant dist= dans la ligne d'etat

# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------
PERIODE_BOUCLE = 1 / 60
PERIODE_ETAT = 0.5
