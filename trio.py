#!/usr/bin/env python3
"""Le jeu a trois : le joueur assis braque avec la chaise, la personne debout
derriere lui regle la vitesse avec ses mains (webcam), et la voix lance les objets.

    python trio.py                  chaise + webcam + voix
    python trio.py --solo           sans personne debout : le kart accelere tout seul
    python trio.py --chaise         la chaise seule (--webcam, --voix : idem)
    python trio.py --fleches        si le jeu ignore la manette virtuelle
    python trio.py --simulation     affiche les commandes sans les envoyer
    python trio.py --journal partie.csv --duree 180

Le serveur (serveur.py) doit tourner : .\\lancer.ps1 ouvre les deux fenetres.
Pendant la partie : C recentre la chaise, Q quitte (terminal ou fenetre webcam).
"""

import argparse
import csv
import os
import sys
import time

import config_trio as cfg
from sortie_stk import SortieSTK


def bip(frequence=880, duree_ms=120):
    try:
        import winsound
        winsound.Beep(frequence, duree_ms)
    except Exception:
        print('\a', end='', flush=True)


def touche():
    """Touche pressee dans ce terminal, ou None. Windows seulement."""
    try:
        import msvcrt
    except ImportError:
        return None
    if msvcrt.kbhit():
        return msvcrt.getwch().lower()
    return None


class Journal:
    """CSV de la partie : une ligne d'etat par tour de boucle, une par commande."""

    def __init__(self, chemin):
        dossier = os.path.dirname(chemin)
        if dossier:
            os.makedirs(dossier, exist_ok=True)
        self._fichier = open(chemin, 'w', newline='', encoding='utf8')
        self._csv = csv.writer(self._fichier)
        self._csv.writerow(['t', 'type', 'angle_chaise', 'steer', 'touches', 'detail'])
        self._t0 = time.time()
        self.chemin = chemin

    def _ligne(self, *champs):
        self._csv.writerow(['%.3f' % (time.time() - self._t0)] + list(champs))

    def etat(self, angle, steer, touches, detail=''):
        self._ligne('etat', '' if angle is None else '%.2f' % angle,
                    '%.3f' % steer, touches, detail)

    def commande(self, commande):
        self._ligne('commande', '', '', '', commande)

    def fermer(self):
        self._fichier.close()


class SortieJournalisee(SortieSTK):
    def __init__(self, *args, journal=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.journal = journal

    def _envoyer(self, commande):
        super()._envoyer(commande)
        if self.journal:
            self.journal.commande(commande)


def demarrer_chaise(sortie, port):
    """Ouvre le port, attend le telephone, calibre. Renvoie (capteur, direction) ou (None, None)."""
    from chaise import CapteurChaise
    from direction import Direction
    from reseau import bandeau_reseau, ips_locales

    capteur = CapteurChaise(port=port)
    try:
        capteur.demarrer()
    except OSError as erreur:
        print('[chaise] port %d deja utilise (%s).' % (port, erreur))
        print('[chaise] ferme chaise.py ou l autre fenetre TRIO, puis relance.')
        return None, None

    print('[chaise] ecoute sur le port %d. Reglages du telephone :' % port)
    print(bandeau_reseau(ips_locales(), port))
    print('[chaise] ZIG SIM : QUATERNION + GYRO.  MultiSense : Orientation + Gyroscope.')
    print('[chaise] en attente du telephone...', flush=True)
    if not capteur.attendre_donnees(30):
        print('[chaise] aucune donnee en 30 s : la chaise ne pilotera pas.')
        capteur.arreter()
        return None, None
    time.sleep(1.0)     # une fenetre pleine pour la frequence
    e = capteur.etat()
    print('[chaise] %s detecte (%s), orientation %d Hz, gyro %d Hz.'
          % (e.profil, e.appareil or 'appareil inconnu', e.hz_orientation, e.hz_gyro))

    for essai in range(3):
        print('[chaise] ASSIS FACE A L ECRAN, IMMOBILE. Calibration dans :')
        for n in (3, 2, 1):
            print('[chaise]   %d' % n, flush=True)
            bip(660, 120)
            time.sleep(0.88)
        ok, explication = capteur.calibrer()
        if ok:
            bip(1320, 400)
            print('[chaise] calibre : %s.' % explication)
            break
        bip(330, 200)
        bip(330, 200)
        print('[chaise] REFUSE : %s. On recommence.' % explication)
    else:
        print('[chaise] calibration impossible : touche C pour recentrer.')

    return capteur, Direction(sortie, capteur)


def lire_arguments():
    p = argparse.ArgumentParser(description='SuperTuxKart a trois : chaise, webcam, voix.')
    p.add_argument('--chaise', action='store_true', help='la chaise (telephone dessous)')
    p.add_argument('--webcam', action='store_true', help='la personne debout (vitesse)')
    p.add_argument('--voix', action='store_true', help='fire, help me, turbo')
    p.add_argument('--solo', '--auto', dest='auto', action='store_true',
                   help='le kart accelere tout seul, sans personne debout')
    p.add_argument('--fleches', action='store_true',
                   help='fleches battues en rythme au lieu de la manette virtuelle')
    p.add_argument('--simulation', action='store_true', help='n envoie rien au serveur')
    p.add_argument('--silencieux', action='store_true', help='n affiche plus chaque commande')
    p.add_argument('--journal', metavar='FICHIER.csv', help='enregistre la partie')
    p.add_argument('--duree', type=float, default=None, metavar='S',
                   help='s arrete tout seul au bout de S secondes')
    p.add_argument('--port', type=int, default=cfg.PORT_OSC_CHAISE, help='port OSC du telephone')
    p.add_argument('--camera', type=int, default=None, help='numero de la webcam')
    p.add_argument('--micro', type=int, default=None, help='numero du micro')
    p.add_argument('--methode', choices=['cap', 'gyro'], default=None)
    args = p.parse_args()
    if not (args.chaise or args.webcam or args.voix):
        args.chaise = args.voix = True
        args.webcam = not args.auto
    return args


def main():
    args = lire_arguments()
    if args.micro is not None:
        cfg.MICRO = args.micro
    if args.auto:
        cfg.ACCELERATION = 'automatique'
    if args.methode:
        cfg.METHODE_CHAISE = args.methode
    if args.fleches:
        cfg.DIRECTION = 'fleches'

    journal = Journal(args.journal) if args.journal else None
    sortie = SortieJournalisee(serveur=cfg.SERVEUR_STK, envoi_reel=not args.simulation,
                               trace=not args.silencieux, journal=journal)

    print()
    print('=== TRIO : chaise / webcam / voix ===')
    if args.simulation:
        print('MODE SIMULATION : rien n est envoye au serveur.')
    else:
        print('Commandes vers %s:%d.' % cfg.SERVEUR_STK)
        if cfg.DIRECTION == 'analogique':
            print('Direction ANALOGIQUE (serveur.py). Si le kart avance sans tourner : --fleches.')
        else:
            print('Direction par FLECHES modulees.')
    print('Acceleration : %s.' % cfg.ACCELERATION)
    print()

    roles = []          # (nom, objet) : mettre_a_jour / etat_texte / arreter
    capteur = direction = webcam = None

    if args.chaise:
        capteur, direction = demarrer_chaise(sortie, args.port)
        if direction:
            roles.append(('chaise', direction))

    if args.webcam:
        from webcam import Webcam
        webcam = Webcam(sortie, camera=args.camera)
        try:
            webcam.demarrer()
            roles.append(('webcam', webcam))
        except Exception as erreur:
            print('[webcam] non demarree : %s' % erreur)
            webcam = None

    if args.voix:
        from voix import Voix
        voix = Voix(sortie)
        try:
            voix.verifier()
            voix.start()
            roles.append(('voix', voix))
            print('[voix] expressions reconnues : %s.' % ', '.join(
                '"%s" (%s)' % kv for kv in cfg.MOTS_VOIX.items()))
        except RuntimeError as erreur:
            print('[voix] non demarree : %s' % erreur)

    if not roles:
        print('Rien n a pu demarrer. Rien a piloter, on s arrete.')
        if capteur:
            capteur.arreter()
        return 1

    if cfg.ACCELERATION == 'automatique':
        sortie.set_continuous('accelerate', 'automatique', True)

    print()
    print('Roles actifs : %s' % ', '.join(nom for nom, _ in roles))
    print('  * Arduino (drift.ino) : Pret a recevoir le drift en Wi-Fi (UDP :%d)' % cfg.PORT_ARDUINO_DRIFT)
    if not args.simulation:
        print('Passe sur SuperTuxKart EN MODE FENETRE et clique dedans : les touches')
        print('partent dans la fenetre qui a le focus.')
    print('C : recentrer la chaise   Q ou Ctrl+C : quitter et tout relacher.')
    print()

    prochaine_ligne = 0.0
    fin = time.time() + args.duree if args.duree else None
    try:
        while True:
            maintenant = time.time()
            if fin and maintenant >= fin:
                print('Duree ecoulee (%.0f s).' % args.duree)
                break

            k = touche()
            if webcam and cfg.FENETRE_WEBCAM:
                k = webcam.afficher() or k
            if k == 'q':
                break
            if k == 'c' and capteur and capteur.recentrer():
                bip(1320, 150)
                print('        -- chaise recentree --')

            with sortie.groupe():
                for nom, role in roles:
                    if hasattr(role, 'mettre_a_jour'):
                        role.mettre_a_jour()

            if journal:
                journal.etat(direction.angle if direction else None,
                             direction.consigne if direction else 0.0,
                             sortie.etat_texte(),
                             webcam.geste() if webcam else '')

            if maintenant >= prochaine_ligne:
                prochaine_ligne = maintenant + cfg.PERIODE_ETAT
                morceaux = ['touches=[%s]' % sortie.etat_texte()]
                morceaux += ['%s: %s' % (nom, role.etat_texte()) for nom, role in roles]
                print('   '.join(morceaux), flush=True)

            time.sleep(cfg.PERIODE_BOUCLE)

    except KeyboardInterrupt:
        pass
    finally:
        for nom, role in roles:
            try:
                role.arreter()
            except Exception as erreur:
                print('[%s] arret imparfait : %s' % (nom, erreur))
        if capteur:
            capteur.arreter()
        sortie.release_all()
        if journal:
            journal.fermer()
            print('Journal ecrit : %s' % journal.chemin)
        print()
        print('Arrete, tout est relache.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
