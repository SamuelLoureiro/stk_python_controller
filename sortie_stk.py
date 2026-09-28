#!/usr/bin/env python3
"""Module d'envoi UDP vers le serveur de jeu, avec fusion des entrees multi-sources."""

import contextlib
import socket
import threading
import time

# Actions continues (maintenues tant qu'une source est active)
CONTINUES = {
    'accelerate': 'ACCELERATE',
    'brake':      'BRAKE',
    'left':       'LEFT',
    'right':      'RIGHT',
    'look_back':  'LOOKBACK',
    'drift':      'SKIDDING',
}

# Actions ponctuelles traitees en impulsion
IMPULSIONS = {
    'fire':   'FIRE',
    'turbo':  'NITRO',
    'rescue': 'RESCUE',
}

SEUIL_STEER = 0.01

# Actions antagonistes qui se neutralisent mutuellement
OPPOSEES = [('left', 'right'), ('accelerate', 'brake')]


class SortieSTK:
    """Gestionnaire thread-safe pour envoyer les commandes UDP au serveur."""

    def __init__(self, serveur=('localhost', 6006), envoi_reel=True, trace=True):
        self.serveur = serveur
        self.envoi_reel = envoi_reel
        self.trace = trace

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._verrou = threading.RLock()

        self._differe = 0            # compteur pour le groupement de commandes
        self._demandes = {}          # action -> set(sources)
        self._enfoncees = set()      # actions actuellement envoyees comme enfoncees
        self._dernier_pulse = {}     # horodatage du dernier pulse par action

        self._dernier_steer = None   # memoire de la derniere valeur analogique

        self.derniere_commande = ''
        self.n_envois = 0

    def _envoyer(self, commande):
        self.derniere_commande = commande
        self.n_envois += 1
        if self.trace:
            print('        -> ' + commande)
        if self.envoi_reel:
            self._sock.sendto(commande.encode(), self.serveur)

    def set_continuous(self, action, source, active):
        """Enregistre la demande d'une source pour une action continue."""
        if action not in CONTINUES:
            return
        with self._verrou:
            sources = self._demandes.setdefault(action, set())
            if active:
                sources.add(source)
            else:
                sources.discard(source)
            if self._differe == 0:
                self._resoudre()

    @contextlib.contextmanager
    def groupe(self):
        """Contexte pour grouper les changements et eviter les etats transitoires."""
        with self._verrou:
            self._differe += 1
        try:
            yield self
        finally:
            with self._verrou:
                self._differe -= 1
                if self._differe == 0:
                    self._resoudre()

    def _resoudre(self):
        voulues = set(a for a, s in self._demandes.items() if s)

        for gauche, droite in OPPOSEES:
            if gauche in voulues and droite in voulues:
                voulues.discard(gauche)
                voulues.discard(droite)

        # Relacher avant d'enfoncer pour eviter les conflits de touches
        for action in sorted(self._enfoncees - voulues):
            self._envoyer('R_' + CONTINUES[action])
            self._enfoncees.discard(action)

        for action in sorted(voulues - self._enfoncees):
            self._envoyer('P_' + CONTINUES[action])
            self._enfoncees.add(action)

    def steer(self, valeur):
        """Transmet la consigne analogique normalisee (-1 a +1)."""
        valeur = max(-1.0, min(1.0, float(valeur)))
        with self._verrou:
            if (self._dernier_steer is not None
                    and abs(valeur - self._dernier_steer) < SEUIL_STEER):
                return
            self._dernier_steer = valeur
            self._envoyer('STEER:%+.3f' % valeur)

    def pulse(self, action, cooldown_s=0.0):
        """Envoie une commande ponctuelle avec delai anti-rebond."""
        if action not in IMPULSIONS:
            return
        maintenant = time.monotonic()
        with self._verrou:
            if maintenant - self._dernier_pulse.get(action, 0.0) < cooldown_s:
                return
            self._dernier_pulse[action] = maintenant
            self._envoyer(IMPULSIONS[action])

    def release_all(self):
        """Reinitialise et relache toutes les commandes vers le jeu."""
        with self._verrou:
            self._demandes.clear()
            self._enfoncees.clear()
            for nom in CONTINUES.values():
                self._envoyer('R_' + nom)
            self._dernier_steer = 0.0
            self._envoyer('STEER:+0.000')

    def etat_texte(self):
        """Resume textuel des actions actuellement maintenues."""
        with self._verrou:
            if not self._enfoncees:
                return '-'
            return ' '.join(sorted(CONTINUES[a] for a in self._enfoncees))
