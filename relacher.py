#!/usr/bin/env python3
"""Relache toutes les touches et remet la direction au centre.

    python relacher.py

Quand un programme meurt en plein virage sans passer par Q ou Ctrl+C (fenetre
fermee a la croix, plantage), la fleche reste enfoncee au niveau de Windows,
meme apres sa fermeture. Ce script relache tout, de deux facons :

  - directement au clavier, ce qui marche meme si le serveur est deja ferme ;
  - en envoyant au serveur (s'il tourne) le relachement de tout ce qui peut
    etre maintenu, et la manette virtuelle au centre.

Relacher une touche deja libre est sans effet : on peut le lancer sans risque.
"""

import socket

import config_trio as cfg
from sortie_stk import CONTINUES

# Les touches que le serveur peut tenir enfoncees (voir serveur.py).
TOUCHES = ('up', 'down', 'left', 'right', 'v', 'b')


def main():
    try:
        import keyboard
        for touche in TOUCHES:
            keyboard.release(touche)
        print('Clavier : %s relachees.' % ', '.join(TOUCHES))
    except Exception as erreur:
        print('Clavier : impossible de relacher directement (%s).' % erreur)

    commandes = ['R_' + nom for nom in CONTINUES.values()] + ['STEER:+0.000']
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for commande in commandes:
        sock.sendto(commande.encode(), cfg.SERVEUR_STK)
    sock.close()
    print('Serveur : %d commandes envoyees a %s:%d (sans effet s il est ferme).'
          % ((len(commandes),) + tuple(cfg.SERVEUR_STK)))


if __name__ == '__main__':
    main()
