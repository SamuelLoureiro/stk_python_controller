#!/usr/bin/env python3
"""Le point de convergence : toutes les sources finissent ici.

Chaise, boitier, voix -- chacun dit ce qu'il veut, en langage de jeu
("accelerate", "left", "fire"). Ce fichier est le seul a parler au serveur
d'entree, et le serveur est le seul a toucher au clavier et a la manette.

    chaise ----.
    boitier ---->  SortieSTK  --UDP:6006-->  serveur.py --> SuperTuxKart
    voix ------'

Pourquoi un seul point de sortie
--------------------------------
  - un seul endroit ou les demandes des sources sont fusionnees et arbitrees
    (deux demandes opposees s'annulent, voir OPPOSEES) ;
  - on n'envoie que les CHANGEMENTS : appelable a 60 Hz sans saturer le reseau ;
  - release_all() relache tout en une fois, quoi qu'il arrive ;
  - le vocabulaire du serveur (P_LEFT, R_LEFT, FIRE, STEER:...) reste lisible
    dans sa fenetre en mode -d.

Repris tel quel du volet performance du projet, ou il a ete mis au point.
"""

import contextlib
import socket
import threading
import time

# Actions maintenues : le serveur attend P_<NOM> pour enfoncer, R_<NOM> pour
# relacher. Tant qu'une source la demande, la touche reste enfoncee.
CONTINUES = {
    'accelerate': 'ACCELERATE',
    'brake':      'BRAKE',
    'left':       'LEFT',
    'right':      'RIGHT',
    'look_back':  'LOOKBACK',
    'drift':      'SKIDDING',
}

# Actions ponctuelles : un seul mot, sans P_ ni R_. Le serveur enfonce et
# relache lui-meme, en tenant la touche 50 ms (sinon le jeu ne la voit jamais,
# cf. l'en-tete de serveur.py).
IMPULSIONS = {
    'fire':   'FIRE',
    'turbo':  'NITRO',
    'rescue': 'RESCUE',
}

# Sous ce changement, on ne renvoie pas de consigne de direction : a 60 Hz,
# envoyer un paquet pour trois millemes de degre sature le reseau et le mode
# debug du serveur sans rien changer a l'ecran.
SEUIL_STEER = 0.01

# Paires qui s'annulent. Deux sources peuvent tres bien demander l'inverse l'une
# de l'autre en meme temps -- le sourd accelere pendant que l'aveugle fait
# demi-tour, par exemple.
# Envoyer les deux fleches donne un kart qui part n'importe ou : on prefere ne
# rien envoyer, c'est-a-dire tout droit.
OPPOSEES = [('left', 'right'), ('accelerate', 'brake')]


class SortieSTK:
    """Fusionne les demandes des sources et n'envoie que les changements.

    Thread-safe : la voix tourne dans son propre thread, la chaise et le
    boitier dans la boucle principale.
    """

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
        """Le seul endroit du programme qui ecrit sur la socket."""
        self.derniere_commande = commande
        self.n_envois += 1
        if self.trace:
            print('        -> ' + commande)
        if self.envoi_reel:
            self._sock.sendto(commande.encode(), self.serveur)

    # -------------------------------------------------- actions maintenues

    def set_continuous(self, action, source, active):
        """<source> declare qu'elle veut (ou ne veut plus) <action>.

        Appelable a 60 Hz sans rien saturer : la comparaison avec l'etat deja
        envoye fait que seuls les changements partent sur le reseau.
        """
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
        """Applique d'un seul coup toutes les demandes faites dans le bloc.

        Sans ca, plusieurs sources mises a jour l'une apres l'autre font passer
        la sortie par des etats intermediaires qui n'ont jamais existe. Mesure
        faite sur un scenario ou deux joueurs tournaient en sens oppose : en
        les relachant l'un apres l'autre, celui qui restait se retrouvait un
        instant seul demandeur, et un P_RIGHT partait, suivi d'un R_RIGHT
        quelques microsecondes plus tard.

        Le jeu ne lit le clavier qu'une fois par image, donc cet appui fantome
        est presque toujours invisible -- "presque" etant le mot genant : une
        fois sur soixante, la frontiere d'image tombe au milieu et le kart
        braque une image entiere sans raison.
        """
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
        """Calcule l'etat voulu, applique l'arbitrage, envoie les differences."""
        voulues = set(a for a, s in self._demandes.items() if s)

        for gauche, droite in OPPOSEES:
            if gauche in voulues and droite in voulues:
                voulues.discard(gauche)
                voulues.discard(droite)

        # Relacher avant d'enfoncer : si le joueur passe de gauche a droite en
        # une image, on ne veut pas des deux fleches enfoncees entre les deux.
        for action in sorted(self._enfoncees - voulues):
            self._envoyer('R_' + CONTINUES[action])
            self._enfoncees.discard(action)

        for action in sorted(voulues - self._enfoncees):
            self._envoyer('P_' + CONTINUES[action])
            self._enfoncees.add(action)

    # ------------------------------------------------ direction analogique

    def steer(self, valeur):
        """Direction continue, de -1 (a fond a gauche) a +1 (a fond a droite).

        Comprise par les serveurs qui savent creer une manette virtuelle :
        serveur.py de ce dossier (Windows, ViGEmBus) et STK_input_server_v2.py
        de la branche performance (Linux, evdev). Un serveur qui ne connait
        pas STEER l'ignore simplement -- d'ou le repli --fleches de trio.py.

        Rien a voir avec set_continuous : ici il n'y a pas d'etat a fusionner,
        une seule consigne resultante est envoyee. C'est au client de faire la
        somme de ses sources AVANT d'appeler cette methode.
        """
        valeur = max(-1.0, min(1.0, float(valeur)))
        with self._verrou:
            if (self._dernier_steer is not None
                    and abs(valeur - self._dernier_steer) < SEUIL_STEER):
                return
            self._dernier_steer = valeur
            self._envoyer('STEER:%+.3f' % valeur)

    # ------------------------------------------------- actions ponctuelles

    def pulse(self, action, cooldown_s=0.0):
        """Declenche une action ponctuelle, avec un temps mort anti-rafale.

        Le cooldown protege des rafales : une source qui redemande la meme
        action a chaque image lancerait sinon un objet par image.
        """
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
        """Relache tout. A appeler dans le finally, quoi qu'il arrive.

        On envoie les R_ de TOUTES les actions maintenues, pas seulement de
        celles qu'on croit enfoncees : si un client precedent est mort en plein
        virage, sa fleche est encore enfoncee au niveau du systeme et personne
        d'autre ne la relachera. Relacher une touche libre est sans effet.
        """
        with self._verrou:
            self._demandes.clear()
            self._enfoncees.clear()
            for nom in CONTINUES.values():
                self._envoyer('R_' + nom)
            # Et la direction analogique au centre : sans ca, un Ctrl+C en
            # plein virage laisse l'axe de la manette braque a fond.
            self._dernier_steer = 0.0
            self._envoyer('STEER:+0.000')

    def etat_texte(self):
        """Resume court des touches enfoncees, pour la ligne d'etat."""
        with self._verrou:
            if not self._enfoncees:
                return '-'
            return ' '.join(sorted(CONTINUES[a] for a in self._enfoncees))
