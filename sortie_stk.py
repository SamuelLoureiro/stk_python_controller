#!/usr/bin/env python3
"""Seul point de sortie vers le serveur : fusionne les demandes des sources
(chaise, boitier, voix), annule les opposees, et n'envoie que les changements."""

import contextlib
import socket
import threading
import time

# Maintenues : P_<NOM> / R_<NOM>, enfoncees tant qu'une source les demande.
CONTINUES = {
    'accelerate': 'ACCELERATE',
    'brake':      'BRAKE',
    'left':       'LEFT',
    'right':      'RIGHT',
    'look_back':  'LOOKBACK',
    'drift':      'SKIDDING',
}

# Ponctuelles : le serveur tient la touche 50 ms lui-meme.
IMPULSIONS = {
    'fire':   'FIRE',
    'turbo':  'NITRO',
    'rescue': 'RESCUE',
}

SEUIL_STEER = 0.01

# Demandees ensemble, elles s'annulent.
OPPOSEES = [('left', 'right'), ('accelerate', 'brake')]


class SortieSTK:
    """Thread-safe : la voix tourne dans son propre thread."""

    def __init__(self, serveur=('localhost', 6006), envoi_reel=True, trace=True):
        self.serveur = serveur
        self.envoi_reel = envoi_reel
        self.trace = trace

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._verrou = threading.RLock()

        self._differe = 0            # > 0 : on accumule sans encore envoyer
        self._demandes = {}          # action -> set(noms de sources)
        self._enfoncees = set()      # actions dont la touche est reellement enfoncee
        self._dernier_pulse = {}     # action -> instant du dernier envoi

        self._dernier_steer = None   # derniere consigne analogique envoyee

        self.derniere_commande = ''  # pour la ligne d'etat
        self.n_envois = 0

    # ------------------------------------------------------------------ envoi

    def _envoyer(self, commande):
        self.derniere_commande = commande
        self.n_envois += 1
        if self.trace:
            print('        -> ' + commande)
        if self.envoi_reel:
            self._sock.sendto(commande.encode(), self.serveur)

    # -------------------------------------------------- actions maintenues

    def set_continuous(self, action, source, active):
        """<source> veut (ou ne veut plus) <action>."""
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
        """Applique d'un coup les demandes du bloc : une par une, la sortie
        passerait par des etats intermediaires (appuis fantomes)."""
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

        # relacher avant d'enfoncer : jamais deux fleches a la fois
        for action in sorted(self._enfoncees - voulues):
            self._envoyer('R_' + CONTINUES[action])
            self._enfoncees.discard(action)

        for action in sorted(voulues - self._enfoncees):
            self._envoyer('P_' + CONTINUES[action])
            self._enfoncees.add(action)

    # ------------------------------------------------ direction analogique

    def steer(self, valeur):
        """Direction continue, -1 (gauche) a +1 (droite) : manette virtuelle."""
        valeur = max(-1.0, min(1.0, float(valeur)))
        with self._verrou:
            if (self._dernier_steer is not None
                    and abs(valeur - self._dernier_steer) < SEUIL_STEER):
                return
            self._dernier_steer = valeur
            self._envoyer('STEER:%+.3f' % valeur)

    # ------------------------------------------------- actions ponctuelles

    def pulse(self, action, cooldown_s=0.0):
        """Action ponctuelle, avec un temps mort anti-rafale."""
        if action not in IMPULSIONS:
            return
        maintenant = time.monotonic()
        with self._verrou:
            if maintenant - self._dernier_pulse.get(action, 0.0) < cooldown_s:
                return
            self._dernier_pulse[action] = maintenant
            self._envoyer(IMPULSIONS[action])

    # ------------------------------------------------------------ securite

    def release_all(self):
        """Relache TOUTES les actions, meme celles qu'on croit libres : un client
        mort en plein virage a pu laisser une fleche enfoncee."""
        with self._verrou:
            self._demandes.clear()
            self._enfoncees.clear()
            for nom in CONTINUES.values():
                self._envoyer('R_' + nom)
            self._dernier_steer = 0.0
            self._envoyer('STEER:+0.000')

    def etat_texte(self):
        with self._verrou:
            if not self._enfoncees:
                return '-'
            return ' '.join(sorted(CONTINUES[a] for a in self._enfoncees))
