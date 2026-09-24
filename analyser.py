#!/usr/bin/env python3
"""Resume un ou plusieurs journaux de partie (trio.py --journal).

    python analyser.py journaux\\equipe1_miroir.csv
    python analyser.py journaux\\*.csv            toutes les parties, une ligne chacune

Pour chaque partie :

    duree         secondes enregistrees
    inversions    changements de sens du braquage, et par minute : le kart
                  zigzague quand la consigne arrive trop tard ou que le guidage
                  est ambigu (CONCEPTION.md, section 2)
    sature        part du temps a braquage complet : ANGLE_MAXI trop petit, ou
                  l'aveugle sur-corrige
    demi-tour     part du temps ou l'aveugle s'est retourne
    FIRE NITRO RESCUE   nombre de commandes envoyees
"""

import argparse
import csv
import glob
import os


def resumer(chemin):
    with open(chemin, encoding='utf8') as f:
        lignes = list(csv.DictReader(f))
    if not lignes:
        return None
    etats = [l for l in lignes if l['type'] == 'etat']
    commandes = [l['detail'] for l in lignes if l['type'] == 'commande']
    duree = float(lignes[-1]['t']) - float(lignes[0]['t'])

    # Le signe du braquage, en ignorant le presque-droit (moins de 5 %).
    signes = [(s > 0.05) - (s < -0.05) for s in (float(l['steer']) for l in etats)]
    signes = [s for s in signes if s]
    inversions = sum(1 for a, b in zip(signes, signes[1:]) if a != b)

    def part(test):
        return sum(1 for l in etats if test(l)) / max(1, len(etats))

    return {
        'partie': os.path.basename(chemin),
        'duree': duree,
        'inversions': inversions,
        'par_minute': inversions / max(duree, 1) * 60,
        'sature': 100 * part(lambda l: abs(float(l['steer'])) > 0.95),
        'demi_tour': 100 * part(lambda l: l['detail'] == 'demi-tour'),
        'FIRE': commandes.count('FIRE'),
        'NITRO': commandes.count('NITRO'),
        'RESCUE': commandes.count('RESCUE'),
    }


def main():
    p = argparse.ArgumentParser(description='Resume des journaux de partie.')
    p.add_argument('journaux', nargs='+', help='fichiers CSV (jokers acceptes)')
    args = p.parse_args()

    # PowerShell ne developpe pas les jokers pour un programme externe : on le fait.
    chemins = []
    for motif in args.journaux:
        chemins += sorted(glob.glob(motif)) or [motif]

    print('%-28s %7s %6s %7s %7s %7s %5s %5s %6s'
          % ('partie', 'duree', 'inv.', 'inv/min', 'sature', 'demi-t', 'FIRE', 'NITRO', 'RESCUE'))
    for chemin in chemins:
        try:
            r = resumer(chemin)
        except (OSError, KeyError, ValueError) as erreur:
            print('%-28s illisible : %s' % (os.path.basename(chemin), erreur))
            continue
        if r is None:
            print('%-28s vide' % os.path.basename(chemin))
            continue
        print('%-28s %6.0fs %6d %7.1f %6.0f%% %6.0f%% %5d %5d %6d'
              % (r['partie'][:28], r['duree'], r['inversions'], r['par_minute'],
                 r['sature'], r['demi_tour'], r['FIRE'], r['NITRO'], r['RESCUE']))


if __name__ == '__main__':
    main()
