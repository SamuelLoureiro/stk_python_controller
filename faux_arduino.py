#!/usr/bin/env python3
"""Un faux boitier du sourd : envoie le meme etat que la carte, toutes les 50 ms.

    python faux_arduino.py              scenario complet

L'etape de la pedale (dist=10) ne freine que si FREIN_CM est regle au-dessus
de 10 dans config_trio.py ; a None, la distance est ignoree.

A lancer dans un second terminal, pendant que tourne :

    python trio.py --arduino --simulation

Le scenario finit par une COUPURE en plein appui, comme une carte qui
redemarre ou un Wi-Fi qui tombe : trio.py doit relacher l'accelerateur tout
seul au bout de WATCHDOG_ARDUINO, sans attendre un "touche=0" qui ne viendra
jamais.
"""

import argparse
import socket
import time

import config_trio as cfg

# (duree en s, touche, distance en cm, tapes pendant l'etape, ce qu'on attend)
SCENARIO = [
    (2.0, 0, -1, 0, 'boitier connecte, rien d enfonce'),
    (2.0, 1, -1, 0, 'P_ACCELERATE'),
    (1.5, 1, -1, 2, 'FIRE deux fois, l acceleration tenue'),
    (1.5, 0, -1, 0, 'R_ACCELERATE'),
    (2.0, 0, 10, 0, 'P_BRAKE si FREIN_CM > 10, sinon rien'),
    (1.0, 0, -1, 0, 'R_BRAKE si le frein etait enfonce'),
    (1.5, 1, -1, 0, 'P_ACCELERATE'),
]


def main():
    p = argparse.ArgumentParser(description='Faux boitier Arduino du sourd.')
    p.add_argument('--hote', default='127.0.0.1')
    p.add_argument('--port', type=int, default=cfg.PORT_ARDUINO)
    args = p.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tapes = 0
    print('Faux boitier -> %s:%d' % (args.hote, args.port))
    for duree, doigt, distance, n_tapes, attendu in SCENARIO:
        print('--- %3.1f s  touche=%d dist=%3d  +%d tapes   attendu : %s'
              % (duree, doigt, distance, n_tapes, attendu), flush=True)
        fin = time.time() + duree
        intervalle = duree / (n_tapes + 1)
        prochaine_tape = time.time() + intervalle if n_tapes else None
        while time.time() < fin:
            if prochaine_tape and time.time() >= prochaine_tape:
                tapes += 1
                prochaine_tape += intervalle
            paquet = 'touche=%d dist=%d tapes=%d piezo=%d' % (
                doigt, distance, tapes, 600 if prochaine_tape else 20)
            sock.sendto(paquet.encode(), (args.hote, args.port))
            time.sleep(0.05)
    print('--- COUPURE en plein appui   attendu : R_ACCELERATE au bout de %.1f s'
          % cfg.WATCHDOG_ARDUINO)
    print('scenario termine')


if __name__ == '__main__':
    main()
