#!/usr/bin/env python3
"""Serveur d'entree : le seul programme qui touche au clavier et a la manette.

    python serveur.py -d          (-d : affiche chaque commande recue)

Recoit sur UDP 6006 le vocabulaire du TP (P_LEFT, R_LEFT, FIRE...) plus
STEER:<-1..+1>, envoye a l'axe d'une manette Xbox virtuelle.
Compatible Linux (evdev/pynput) et Windows (vgamepad/keyboard).
Accepte les connexions locales et reseau (Wi-Fi Arduino).

Lancer SuperTuxKart APRES ce serveur, qui cree la manette.

D'apres STK_input_server.py, Michael ORTEGA, 2018.
"""

import os
import socket
import sys
import threading
import time

VERT = '\033[92m'
BLANC = '\x1b[0m'
JAUNE = '\033[93m'
ROUGE = '\033[91m'
BLEU = '\033[94m'

# Ecoute sur 0.0.0.0 pour accepter a la fois localhost (trio.py) et le Wi-Fi (Arduino)
ADRESSE = ('0.0.0.0', 6006)

# Un appui de moins de 16 ms n'est jamais vu par le jeu (mesure) : avec le
# press_and_release d'origine, FIRE, RESCUE et NITRO n'arrivaient pas.
MAINTIEN = 0.05

# --------------------------------------------------------------------------
# Emulation du clavier (multiplateforme Linux / Windows)
# --------------------------------------------------------------------------
try:
    from pynput.keyboard import Key, Controller as PynputController
    _pynput_kb = PynputController()
    _KEY_MAP = {
        'up': Key.up,
        'down': Key.down,
        'left': Key.left,
        'right': Key.right,
        'enter': Key.enter,
        'backspace': Key.backspace,
        'space': Key.space,
        'escape': Key.esc,
    }

    def _press(touche):
        _pynput_kb.press(_KEY_MAP.get(touche, touche))

    def _release(touche):
        _pynput_kb.release(_KEY_MAP.get(touche, touche))

except ImportError:
    import keyboard

    def _press(touche):
        keyboard.press(touche)

    def _release(touche):
        keyboard.release(touche)


def appui_bref(touche):
    _press(touche)
    time.sleep(MAINTIEN)
    _release(touche)


bindings = [
    ['UP',           'up',        appui_bref],
    ['DOWN',         'down',      appui_bref],
    ['LEFT',         'left',      appui_bref],
    ['RIGHT',        'right',     appui_bref],
    ['SELECT',       'enter',     appui_bref],
    ['CANCEL',       'backspace', appui_bref],
    ['BACK',         'backspace', appui_bref],
    ['FIRE',         'space',     appui_bref],
    ['NITRO',        'n',         appui_bref],
    ['P_SKIDDING',   'v',         _press],
    ['R_SKIDDING',   'v',         _release],
    ['P_LOOKBACK',   'b',         _press],
    ['R_LOOKBACK',   'b',         _release],
    ['RESCUE',       'backspace', appui_bref],
    ['PAUSE',        'escape',    appui_bref],
    ['P_UP',         'up',        _press],
    ['R_UP',         'up',        _release],
    ['P_DOWN',       'down',      _press],
    ['R_DOWN',       'down',      _release],
    ['P_LEFT',       'left',      _press],
    ['R_LEFT',       'left',      _release],
    ['P_RIGHT',      'right',     _press],
    ['R_RIGHT',      'right',     _release],
    ['P_ACCELERATE', 'up',        _press],
    ['R_ACCELERATE', 'up',        _release],
    ['P_BRAKE',      'down',      _press],
    ['R_BRAKE',      'down',      _release],
]

commandes = [b[0] for b in bindings]


# --------------------------------------------------------------------------
# Direction : manette virtuelle ou repli module
# --------------------------------------------------------------------------
class DirectionManetteLinux:
    """Manette virtuelle Xbox 360 pour Linux via evdev/uinput."""

    def __init__(self):
        from evdev import UInput, AbsInfo, ecodes
        self.ecodes = ecodes
        capabilities = {
            ecodes.EV_ABS: [
                (ecodes.ABS_X, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
                (ecodes.ABS_Y, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
            ],
            ecodes.EV_KEY: [
                ecodes.BTN_A, ecodes.BTN_B, ecodes.BTN_X, ecodes.BTN_Y,
                ecodes.BTN_TL, ecodes.BTN_TR, ecodes.BTN_SELECT, ecodes.BTN_START,
            ],
        }
        self.pad = UInput(capabilities, name="Xbox 360 Controller", vendor=0x045e, product=0x028e)
        self.valeur = 0.0

    def regler(self, valeur):
        self.valeur = max(-1.0, min(1.0, valeur))
        val_int = int(self.valeur * 32767)
        self.pad.write(self.ecodes.EV_ABS, self.ecodes.ABS_X, val_int)
        self.pad.syn()

    def arreter(self):
        if self.pad:
            try:
                self.pad.write(self.ecodes.EV_ABS, self.ecodes.ABS_X, 0)
                self.pad.syn()
                self.pad.close()
            except Exception:
                pass

    def description(self):
        return 'manette Xbox 360 Linux (evdev/uinput, axe analogique ABS_X)'


class DirectionManetteWindows:
    """Manette virtuelle Xbox 360 pour Windows via vgamepad."""

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
        return 'manette Xbox 360 Windows (vgamepad, axe analogique)'


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
                    _release(self._touche_enfoncee)
                if voulue:
                    _press(voulue)
                self._touche_enfoncee = voulue

            time.sleep(1 / 120)

    def arreter(self):
        self._arret.set()
        self._fil.join(timeout=1)
        if self._touche_enfoncee:
            _release(self._touche_enfoncee)
            self._touche_enfoncee = None

    def description(self):
        return 'REPLI : fleches modulees (sans manette)'


def creer_direction():
    # 1. Essai Linux (evdev)
    if sys.platform.startswith('linux'):
        try:
            return DirectionManetteLinux()
        except Exception as erreur:
            print(ROUGE + 'Manette Linux uinput impossible' + BLANC + ' : %s' % erreur)
            print('Permission /dev/uinput ? Essaie : sudo chmod 666 /dev/uinput')

    # 2. Essai Windows (vgamepad)
    if sys.platform.startswith('win'):
        try:
            return DirectionManetteWindows()
        except ImportError:
            print(ROUGE + 'vgamepad absent' + BLANC + ' : direction en repli module.')
        except Exception as erreur:
            print(ROUGE + 'Manette virtuelle impossible' + BLANC + ' : %s' % erreur)
            print('Le pilote ViGEmBus est-il installe ?')

    # 3. Repli touche modulee
    return DirectionModulee()


# --------------------------------------------------------------------------
# Point d'entree principal
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
    print('STK input server (manette + UDP :6006) demarre ', end='')
    print(VERT + '(mode debug)' + BLANC if debug else '')
    print('  ecoute    : ' + JAUNE + '%s:%d (localhost + Wi-Fi Arduino)' % ADRESSE + BLANC)
    print('  direction : ' + BLEU + direction.description() + BLANC)
    print('  touches   : clavier, appui de %d ms pour les commandes breves'
          % (MAINTIEN * 1000))
    print('  drift     : accepte P_SKIDDING / R_SKIDDING (Arduino touch sensor)')
    print('  Ctrl+C pour arreter.')
    print()

    dernier_steer = None
    try:
        while True:
            data, source = sock.recvfrom(1024)
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
                    src_info = f" [{source[0]}]" if source[0] not in ('127.0.0.1', 'localhost') else ""
                    print(JAUNE + '\t' + texte + src_info + BLANC)
                b = bindings[commandes.index(texte)]
                b[2](b[1])
            elif debug:
                print(ROUGE + '\t' + texte + BLANC + ' (inconnu)')

    except KeyboardInterrupt:
        pass
    finally:
        direction.arreter()
        for touche in ('up', 'down', 'left', 'right', 'v', 'b'):
            _release(touche)
        sock.close()
        print()
        print('STK input server arrete, direction remise au centre.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
