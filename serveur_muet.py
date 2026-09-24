#!/usr/bin/env python3
"""Un serveur d'entree qui affiche tout et n'appuie sur rien.

A lancer A LA PLACE de serveur.py quand on met au point sans vouloir que des
fleches partent dans la fenetre au premier plan (lancer.ps1 -Muet le fait).
Meme port, meme vocabulaire : le reste de la chaine ne voit pas la
difference.

    python serveur_muet.py

C'est l'outil a prendre quand on doute de la moitie reseau de la chaine : si les
commandes s'affichent ici, le probleme est entre le serveur et le jeu (focus,
mode fenetre, touches du jeu) et pas avant.
"""

import socket
import sys

PORT = 6006

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    sock.bind(('localhost', PORT))
except OSError as erreur:
    print('Le port %d est deja utilise (%s).' % (PORT, erreur), file=sys.stderr)
    print('Le vrai serveur tourne sans doute deja : ferme-le d abord.',
          file=sys.stderr)
    sys.exit(1)

print('Serveur MUET sur le port %d : rien ne sera tape au clavier.' % PORT)
print('Ctrl+C pour arreter.')
print()

compte = {}
try:
    while True:
        data, _ = sock.recvfrom(1024)
        commande = data.decode('utf-8').replace(',', '')
        compte[commande] = compte.get(commande, 0) + 1
        print('  %-14s (%d fois)' % (commande, compte[commande]))
except KeyboardInterrupt:
    print()
    print('Arrete. Recapitulatif :')
    for commande in sorted(compte):
        print('  %-14s %d' % (commande, compte[commande]))
