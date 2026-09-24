#!/usr/bin/env python3
"""Fait bouger le stick de la manette virtuelle, pour l'assigner dans SuperTuxKart.

    python bouger_stick.py gauche
    python bouger_stick.py droite

A ne faire que si le kart avance sans tourner (GUIDE.md, section 5.5). Le
serveur (serveur.py) doit tourner, trio.py non.

Dans SuperTuxKart : Options > Controles > la manette Xbox 360 > cliquer sur
"Tourner a gauche" : le jeu attend un mouvement. Lancer ce script, puis
cliquer dans le jeu pendant les 5 secondes d'attente : le stick va et vient
six fois, le jeu enregistre l'axe.
"""

import argparse
import socket
import time

import config_trio as cfg


def main():
    p = argparse.ArgumentParser(description='Bouge le stick de la manette virtuelle.')
    p.add_argument('sens', choices=['gauche', 'droite'])
    p.add_argument('--attente', type=int, default=5, help='secondes pour cliquer dans le jeu')
    args = p.parse_args()

    valeur = b'STEER:-1.000' if args.sens == 'gauche' else b'STEER:+1.000'
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    for reste in range(args.attente, 0, -1):
        print('Clique dans SuperTuxKart... %d' % reste, flush=True)
        time.sleep(1)
    print('Le stick bouge vers la %s.' % args.sens)
    for _ in range(6):
        sock.sendto(valeur, cfg.SERVEUR_STK)
        time.sleep(0.4)
        sock.sendto(b'STEER:+0.000', cfg.SERVEUR_STK)
        time.sleep(0.4)
    print('Fini. Rien ne s est passe ? Verifier que serveur.py tourne, et que sa')
    print('fenetre affiche "manette Xbox 360 virtuelle" et non "REPLI".')


if __name__ == '__main__':
    main()
