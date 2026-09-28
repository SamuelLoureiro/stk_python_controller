#!/usr/bin/env python3
"""Parametres et reglages pour le mode trio (ports, seuils, constantes)."""

import os

DOSSIER_TRIO = os.path.dirname(os.path.abspath(__file__))
MODELES = os.path.join(DOSSIER_TRIO, 'models')
MODELE_VOSK = os.path.join(MODELES, 'vosk-model-small-en-us-0.15')
MODELE_POSE = os.path.join(MODELES, 'pose_landmarker_lite.task')

# Configuration reseau
SERVEUR_STK = ('localhost', 6006)   # ecoute de serveur.py
PORT_OSC_CHAISE = 8000              # flux OSC du telephone (ZIG SIM / MultiSense)

# Mesure de l'angle de la chaise
# 'cap' = orientation absolue, 'gyro' = vitesse angulaire integree
METHODE_CHAISE = 'cap'

# Convention : angle > 0 quand on tourne a droite
SIGNE_CAP = {'zigsim': -1, 'multisense': +1}
SIGNE_GYRO = {'zigsim': -1, 'multisense': -1}

AXE_GYRO_MULTISENSE = 'z'           # telephone pose a plat

# Unites du gyroscope selon l'appli mobile utilisee
UNITE_GYRO = {'zigsim': 'rad', 'multisense': 'rad'}

# Calibration et timeouts
DUREE_CALIBRATION = 1.5             # temps d'attente immobile pour fixer le neutre
AGITATION_MAX = 3.0                 # seuil deg/s pour refuser la calibration
SILENCE_MAX = 0.5                   # delai sans paquet avant de recentrer le kart

# Mode de direction vers STK ('analogique' manette virtuelle ou 'fleches' batteur)
DIRECTION = 'analogique'

ANGLE_MINI = 5.0                    # zone morte en degres
ANGLE_MAXI = 35.0                   # braquage maximum
COURBE = 1.5                        # progression non lineaire (> 1 pour adoucir le centre)

# Detection des gestes par webcam (joueur debout)
ACCELERATION = 'webcam'             # ou 'automatique' pour tester en solo
CAMERA_INDEX = 0
CAMERA_LARGEUR = 640
CAMERA_HAUTEUR = 480
MIROIR = True                       # retour video en miroir pour le confort
FENETRE_WEBCAM = True

# Seuils de visibilite et position (coordonnees normalisees 0..1)
LIGNE_DEBOUT = 0.45                 # limite pour detecter la tete au-dessus du joueur assis
MARGE_MAIN = 0.2                    # hauteur mini au-dessus de l'epaule (en largeur d'epaules)
VISIBILITE_MIN = 0.5
ATTENTE_GESTE = 0.2                 # filtrage temporel anti-rebond
ABSENCE_MAX = 0.5                   # relache les commandes si le joueur n'est plus vu

# Geste 6-7 (mouvement alternatif des mains pour accelerer)
SIXSEPT_SEUIL = 0.15                # ecart relatif minimum entre les mains
SIXSEPT_FENETRE = 1.5               # fenetre glissante d'analyse (secondes)
SIXSEPT_BASCULES = 3                # nombre d'oscillations demandees
SIXSEPT_MAINTIEN = 0.6              # persistance apres le dernier mouvement

# Mains sur la tete (geste de frein d'urgence)
FREIN_DISTANCE_TETE = 0.9           # distance mains-tete en largeurs d'epaules
VISIBILITE_TETE = 0.3               # seuil reduit car les mains masquent parfois les oreilles

# High five (contact entre mains du joueur assis et debout pour lancer un objet)
HIGH_FIVE_DISTANCE = 0.5            # distance de declenchement en largeurs d'epaules
HIGH_FIVE_REPOS = 1.0               # delai mini entre deux tirs consecutifs

# Reconnaissance vocale (Vosk offline)
MOTS_VOIX = {
    'fire': 'fire',
    'help me': 'rescue',
    'turbo': 'turbo',
}
DELAI_VOIX = 0.5                    # temps mort entre deux declenchements identiques
MICRO = None                        # index du micro (None = defaut systeme)

# Drift externe Arduino
PORT_ARDUINO_DRIFT = 6006

# Frequences de boucle
PERIODE_BOUCLE = 1 / 60
PERIODE_ETAT = 0.5
