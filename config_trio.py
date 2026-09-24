#!/usr/bin/env python3
"""Tous les reglages. Les valeurs "SUPPOSE" restent a verifier avec `python chaise.py`."""

import os

DOSSIER_TRIO = os.path.dirname(os.path.abspath(__file__))
MODELE_VOSK = os.path.join(DOSSIER_TRIO, 'models', 'vosk-model-small-en-us-0.15')

# --- Reseau -------------------------------------------------------------
SERVEUR_STK = ('localhost', 6006)   # serveur.py
PORT_OSC_CHAISE = 8000              # telephone (ZIG SIM ou MultiSense)
PORT_ARDUINO = 6010                 # boitier du sourd

# --- Chaise : mesure de l'angle -----------------------------------------
# 'cap'  : orientation du telephone. Ne derive pas, mais l'acier du verin
#          peut fausser la boussole.
# 'gyro' : vitesse integree. Insensible a l'acier, derive lentement.
# Mesure 2026-09-24 (iPhone 14 Pro, pose sur l'assise) : cap et gyro d'accord
# a ~1 deg pres sur +-66 deg. A reconfirmer telephone fixe dessous.
METHODE_CHAISE = 'cap'

# Ramene chaque mesure a la convention : angle > 0 = l'aveugle tourne a SA droite.
# ZIG SIM : -1 mesure le 2026-09-24. MultiSense : SUPPOSE (le gyro change de
# signe si le telephone est retourne).
SIGNE_CAP = {'zigsim': -1, 'multisense': +1}
SIGNE_GYRO = {'zigsim': -1, 'multisense': -1}

AXE_GYRO_MULTISENSE = 'z'           # 'z' si le telephone est a plat

# ZIG SIM : 'rad' mesure. MultiSense : SUPPOSE ; chaise.py affiche gyro/cap,
# ~57 veut dire 'deg'.
UNITE_GYRO = {'zigsim': 'rad', 'multisense': 'rad'}

DUREE_CALIBRATION = 1.5             # s d'immobilite pour le neutre et le biais
AGITATION_MAX = 3.0                 # deg/s au-dela desquels la calibration est refusee
SILENCE_MAX = 0.5                   # s sans message du telephone -> direction au centre

# --- Chaise : effet sur le kart -----------------------------------------
# 'miroir'       : l'aveugle tourne a sa gauche -> kart a droite. Pour un
#                  aveugle qui fait face au repere tenu par le muet.
# 'egocentrique' : l'aveugle tourne a sa droite -> kart a droite.
CORRESPONDANCE = 'miroir'

# 'analogique' : manette virtuelle (serveur.py). 'fleches' : fleche battue en
# rythme, avec n'importe quel serveur.
DIRECTION = 'analogique'

ANGLE_MINI = 5.0                    # deg, zone morte
ANGLE_MAXI = 35.0                   # deg, braquage complet (~80 % de l'angle confortable)
COURBE = 1.5                        # > 1 : plus doux pres du neutre

ANGLE_DEMI_TOUR = 100.0             # deg : l'aveugle se retourne, gaz coupes. None = off
HYSTERESIS_DEMI_TOUR = 20.0         # deg

# --- Sourd ----------------------------------------------------------------
ACCELERATION = 'sourd'              # ou 'automatique'

# Modele anglais : mots anglais.
MOTS_VOIX = {
    'fire': 'fire',
    'turbo': 'turbo',
    'help': 'rescue',
    'center': 'recentrer',          # recentre la chaise
}
DELAI_VOIX = 0.5                    # s avant qu'un meme mot puisse redeclencher

# Mots a dire deux fois dans le delai (s). Vosk, limite a quatre mots, prend
# parfois la musique du jeu pour "help" : sauvetages parasites le 2026-09-24.
MOTS_A_REPETER = {'help': 1.5}

MICRO = None                        # numero du micro, None = celui de Windows

WATCHDOG_ARDUINO = 0.5              # s sans paquet du boitier -> tout relache
FREIN_CM = None                     # pedale a ultrason : frein sous cette distance

# --- Affichage ----------------------------------------------------------
PERIODE_BOUCLE = 1 / 60
PERIODE_ETAT = 0.5
