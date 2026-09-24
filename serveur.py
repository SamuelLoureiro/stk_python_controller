#!/usr/bin/env python3
"""Serveur d'entree : le seul programme qui touche au clavier et a la manette.

    python serveur.py -d          (-d : affiche chaque commande recue)

Recoit sur UDP 6006 le vocabulaire du TP (P_LEFT, R_LEFT, FIRE...) plus
STEER:<-1..+1>, envoye a l'axe d'une manette Xbox virtuelle (vgamepad +
ViGEmBus). Sans vgamepad, STEER est traduit en fleches battues en rythme.
Windows seulement ; sous Linux, STK_input_server_v2.py (branche performance).

Lancer SuperTuxKart APRES ce serveur, qui cree la manette.

D'apres STK_input_server.py, Michael ORTEGA, 2018.
"""

import socket
import sys
import threading
import time

import keyboard

VERT = '\033[92m'
BLANC = '\x1b[0m'
JAUNE = '\033[93m'
ROUGE = '\033[91m'
BLEU = '\033[94m'

ADRESSE = ('localhost', 6006)

# Un appui de moins de 16 ms n'est jamais vu par le jeu (mesure) : avec le
# press_and_release d'origine, FIRE, RESCUE et NITRO n'arrivaient pas.
MAINTIEN = 0.05


def appui_bref(touche):
    keyboard.press(touche)
    time.sleep(MAINTIEN)
    keyboard.release(touche)


bindings = [['UP', 'up', appui_bref],
            ['DOWN', 'down', appui_bref],
            ['LEFT', 'left', appui_bref],
            ['RIGHT', 'right', appui_bref],
            ['SELECT', 'enter', appui_bref],
            ['CANCEL', 'backspace', appui_bref],
            ['BACK', 'backspace', appui_bref],
            ['FIRE', 'space', appui_bref],
            ['NITRO', 'n', appui_bref],
            ['P_SKIDDING', 'v', keyboard.press],
            ['R_SKIDDING', 'v', keyboard.release],
            ['P_LOOKBACK', 'b', keyboard.press],
            ['R_LOOKBACK', 'b', keyboard.release],
            ['RESCUE', 'backspace', appui_bref],
            ['PAUSE', 'escape', appui_bref],
            ['P_UP', 'up', keyboard.press],
            ['R_UP', 'up', keyboard.release],
            ['P_DOWN', 'down', keyboard.press],
            ['R_DOWN', 'down', keyboard.release],
            ['P_LEFT', 'left', keyboard.press],
            ['R_LEFT', 'left', keyboard.release],
            ['P_RIGHT', 'right', keyboard.press],
            ['R_RIGHT', 'right', keyboard.release],
            ['P_ACCELERATE', 'up', keyboard.press],
            ['R_ACCELERATE', 'up', keyboard.release],
            ['P_BRAKE', 'down', keyboard.press],
            ['R_BRAKE', 'down', keyboard.release]]

commandes = [b[0] for b in bindings]



class DirectionManette:

    def __init__(self):
        import vgamepad
        self.pad = vgamepad.VX360Gamepad()
        self.valeur = 0.0

    def regler(self, valeur):
        self.valeur = max(-1.0, min(1.0, valeur))
        self.pad.left_joystick_float(x_value_float=self.valeur, y_value_float=0.0)
        self.pad.update()

    def arreter(self):
        self.pad.reset()
        self.pad.update()

    def description(self):
        return 'manette Xbox 360 virtuelle (axe analogique)'


class DirectionModulee:
    """Repli sans manette : la fleche est battue en rythme."""

    PERIODE = 0.12
    APPUI_MINI = 0.034      # deux images a 60 fps
    PERIODE_MAXI = 0.45

    def __init__(self):
        self.valeur = 0.0
        self._touche_enfoncee = None
        self._arret = threading.Event()
        self._fil = threading.Thread(target=self._boucle, daemon=True)
        self._fil.start()

    def regler(self, valeur):
        self.valeur = max(-1.0, min(1.0, valeur))

    def _boucle(self):
        debut = time.time()
        while not self._arret.is_set():
            valeur = self.valeur
            intensite = abs(valeur)
            touche = 'left' if valeur < 0 else 'right'

            duree = intensite * self.PERIODE
            periode = self.PERIODE
            if intensite <= 0.0:
                actif = False
            elif intensite >= 1.0:
                actif = True
            elif duree < self.APPUI_MINI:
                periode = self.APPUI_MINI / intensite
                actif = (periode <= self.PERIODE_MAXI
                         and (time.time() - debut) % periode < self.APPUI_MINI)
            else:
                actif = (time.time() - debut) % periode < duree

            voulue = touche if actif else None
            if voulue != self._touche_enfoncee:
                if self._touche_enfoncee:
                    keyboard.release(self._touche_enfoncee)
                if voulue:
                    keyboard.press(voulue)
                self._touche_enfoncee = voulue

            time.sleep(1 / 120)

    def arreter(self):
        self._arret.set()
        self._fil.join(timeout=1)
        if self._touche_enfoncee:
            keyboard.release(self._touche_enfoncee)
            self._touche_enfoncee = None

    def description(self):
        return 'REPLI : fleches modulees (pip install vgamepad pour l analogique)'


def creer_direction():
    try:
        return DirectionManette()
    except ImportError:
        print(ROUGE + 'vgamepad absent' + BLANC + ' : direction en repli module.')
    except Exception as erreur:
        print(ROUGE + 'Manette virtuelle impossible' + BLANC + ' : %s' % erreur)
        print('Le pilote ViGEmBus est-il installe ?')
    return DirectionModulee()


# --------------------------------------------------------------------------

def main():
    debug = '-d' in sys.argv or '--debug' in sys.argv

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(ADRESSE)
    except OSError as erreur:
        print(ROUGE + 'Le port %d est deja utilise' % ADRESSE[1] + BLANC
              + ' : %s' % erreur, file=sys.stderr)
        print('Un autre serveur tourne deja. Ferme-le, puis relance.',
              file=sys.stderr)
        return 1

    direction = creer_direction()

    print()
    print('STK input server (manette) demarre ', end='')
    print(VERT + '(mode debug)' + BLANC if debug else '')
    print('  direction : ' + BLEU + direction.description() + BLANC)
    print('  touches   : clavier, appui de %d ms pour les commandes breves'
          % (MAINTIEN * 1000))
    print('  Ctrl+C pour arreter.')
    print()

    dernier_steer = None
    try:
        while True:
            data, _ = sock.recvfrom(1024)
            texte = data.decode('utf-8').strip().replace(',', '')

            if texte == 'STOPSERVEUR':
                break

            if texte.startswith('STEER:'):
                try:
                    valeur = float(texte.split(':', 1)[1])
                except ValueError:
                    if debug:
                        print(ROUGE + '\t' + texte + BLANC + ' (valeur illisible)')
                    continue
                direction.regler(valeur)
                if debug and (dernier_steer is None
                              or abs(valeur - dernier_steer) > 0.05):
                    dernier_steer = valeur
                    barre = int(abs(valeur) * 20)
                    cote = '<' if valeur < 0 else '>'
                    print(BLEU + '\tSTEER %+5.2f %s' % (valeur, cote * barre)
                          + BLANC)
                continue

            if texte in commandes:
                if debug:
                    print(JAUNE + '\t' + texte + BLANC)
                b = bindings[commandes.index(texte)]
                b[2](b[1])
            elif debug:
                print(ROUGE + '\t' + texte + BLANC + ' (inconnu)')

    except KeyboardInterrupt:
        pass
    finally:
        direction.arreter()
        for touche in ('up', 'down', 'left', 'right', 'v', 'b'):
            keyboard.release(touche)
        sock.close()
        print()
        print('STK input server arrete, direction remise au centre.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
