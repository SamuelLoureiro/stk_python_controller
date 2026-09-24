#!/usr/bin/env python3
"""Tous les reglages. Les valeurs "SUPPOSE" restent a verifier : chaise.py, webcam.py."""

import os

DOSSIER_TRIO = os.path.dirname(os.path.abspath(__file__))
MODELES = os.path.join(DOSSIER_TRIO, 'models')
MODELE_VOSK = os.path.join(MODELES, 'vosk-model-small-en-us-0.15')
MODELE_POSE = os.path.join(MODELES, 'pose_landmarker_lite.task')

# --- Reseau -------------------------------------------------------------
SERVEUR_STK = ('localhost', 6006)   # serveur.py
PORT_OSC_CHAISE = 8000              # telephone (ZIG SIM ou MultiSense)

# --- Chaise : mesure de l'angle -----------------------------------------
# 'cap'  : orientation du telephone. Ne derive pas, mais l'acier du verin
#          peut fausser la boussole.
# 'gyro' : vitesse integree. Insensible a l'acier, derive lentement.
# Mesure 2026-09-24 (iPhone 14 Pro, pose sur l'assise) : cap et gyro d'accord
# a ~1 deg pres sur +-66 deg. A reconfirmer telephone fixe dessous.
METHODE_CHAISE = 'cap'

# Ramene chaque mesure a la convention : angle > 0 = le joueur tourne a droite.
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
# 'analogique' : manette virtuelle (serveur.py). 'fleches' : fleche battue en
# rythme, avec n'importe quel serveur.
DIRECTION = 'analogique'

ANGLE_MINI = 5.0                    # deg, zone morte
ANGLE_MAXI = 35.0                   # deg, braquage complet (~80 % de l'angle confortable)
COURBE = 1.5                        # > 1 : plus doux pres du neutre

# --- Webcam : la personne debout ----------------------------------------
# Mains sur la tete = freiner, geste 6-7 = accelerer, et sinon :
# deux mains levees = accelerer, une seule = freiner, aucune = rien.
ACCELERATION = 'webcam'             # ou 'automatique' (--solo, --auto)
CAMERA_INDEX = 0
CAMERA_LARGEUR = 640
CAMERA_HAUTEUR = 480
MIROIR = True                       # affichage seulement
FENETRE_WEBCAM = True

# SUPPOSE, a regler avec webcam.py. Coordonnees d'image : 0 en haut, 1 en bas.
LIGNE_DEBOUT = 0.45                 # le nez de la personne debout doit etre au-dessus
MARGE_MAIN = 0.2                    # poignet au-dessus de l'epaule, en largeurs d'epaules
VISIBILITE_MIN = 0.5
ATTENTE_GESTE = 0.2                 # s : lever les deux mains passe par "une main"
ABSENCE_MAX = 0.5                   # s sans personne debout -> tout relache

# Geste 6-7, a regler avec webcam.py ("6-7 d=") : pendant le geste d doit
# passer nettement de +SEUIL a -SEUIL, au repos rester entre les deux.
SIXSEPT_SEUIL = 0.15                # largeurs d'epaules ; monter si une main qui bouge suffit
SIXSEPT_FENETRE = 1.5               # s dans lesquelles on compte les bascules
SIXSEPT_BASCULES = 3                # bascules necessaires (un aller-retour et demi)
SIXSEPT_MAINTIEN = 0.6              # s sans bascule -> on n'accelere plus

# Mains sur la tete, a regler avec webcam.py ("tete") : distance de la main la
# plus eloignee au centre de la tete, en largeurs d'epaules.
FREIN_DISTANCE_TETE = 0.9           # monter si des mains bien posees ne freinent pas
VISIBILITE_TETE = 0.3               # une main sur la tete est souvent a moitie cachee

# --- Voix -----------------------------------------------------------------
# Modele anglais : mots anglais. Une expression de plusieurs mots est
# reconnue comme un tout.
MOTS_VOIX = {
    'fire': 'fire',
    'help me': 'rescue',
    'turbo': 'turbo',
}
DELAI_VOIX = 0.5                    # s avant qu'une meme expression puisse redeclencher
MICRO = None                        # numero du micro, None = celui de Windows

# --- Affichage ----------------------------------------------------------
PERIODE_BOUCLE = 1 / 60
PERIODE_ETAT = 0.5
