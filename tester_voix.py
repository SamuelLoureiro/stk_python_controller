#!/usr/bin/env python3
"""Montre ce que le micro entend, et ce que Vosk en comprend. N'envoie rien au jeu.

    python tester_voix.py --liste              liste les micros et sort
    python tester_voix.py --mots               niveau + mots reconnus, 15 s
    python tester_voix.py --mots --duree 120   a laisser tourner PENDANT une course
    python tester_voix.py --peripherique 1 --mots   un micro precis

Trois pannes donnent le meme symptome ("la voix ne marche pas") :

  1. le micro n'entend rien     -> le niveau reste a 0 : cote Windows
  2. il entend, Vosk ne         -> le niveau bouge, aucun mot : prononciation,
     comprend pas                  bruit, mot hors de la liste
  3. le mauvais micro           -> le niveau bouge quand on parle dans UN AUTRE
                                   micro que celui qu'on croit

Et une quatrieme, l'inverse : des mots reconnus alors que personne ne les dit.
Avec une liste de quatre mots, Vosk ramene tout son vers le mot le plus proche.
Laisser tourner --mots pendant une course, musique du jeu comprise : chaque
mot reconnu s'affiche avec son heure. C'est ce qui a explique les sauvetages
inattendus du 2026-09-24 (d'ou la regle "help help", config_trio.MOTS_A_REPETER).
"""

import argparse
import collections
import json
import math
import os
import time

import sounddevice as sd

import config_trio as cfg


def lister():
    """Les entrees disponibles, avec celle que Windows a choisie par defaut."""
    try:
        defaut = sd.query_devices(kind='input')['name']
    except Exception:
        defaut = None

    print('Entrees audio disponibles :')
    print()
    for i, d in enumerate(sd.query_devices()):
        if d['max_input_channels'] <= 0:
            continue
        api = sd.query_hostapis(d['hostapi'])['name']
        marque = '  <-- defaut' if d['name'] == defaut and api == 'MME' else ''
        print('  %3d  %-42s %-18s %d voie(s)%s'
              % (i, d['name'][:42], api, d['max_input_channels'], marque))
    print()
    if defaut:
        print('Windows utilise par defaut : %s' % defaut)
        print('Pour en changer : Parametres > Systeme > Son > Entree,')
        print('ou MICRO = numero dans config_trio.py, ou trio.py --micro numero.')
    else:
        print('AUCUNE entree par defaut : Windows ne voit pas de micro.')
    print()


def barre(niveau, largeur=40):
    """Niveau 0..1 en barre de texte. Une echelle lineaire ecrase la parole, on
    prend donc une racine, qui etale le bas de l'echelle."""
    plein = int(min(1.0, math.sqrt(niveau)) * largeur)
    return '[' + '#' * plein + '.' * (largeur - plein) + ']'


def mesurer(peripherique, duree, avec_vosk):
    rec = None
    if avec_vosk:
        if not os.path.isdir(cfg.MODELE_VOSK):
            print('Modele Vosk introuvable : %s' % cfg.MODELE_VOSK)
            print('Lance une fois : python installer.py')
            return
        import vosk
        vosk.SetLogLevel(-1)
        # La MEME grammaire que le jeu : on voit exactement ce que trio.py verrait.
        grammaire = json.dumps(list(cfg.MOTS_VOIX) + ['[unk]'])
        rec = vosk.KaldiRecognizer(vosk.Model(cfg.MODELE_VOSK), 16000, grammaire)

    nom = (sd.query_devices(peripherique)['name'] if peripherique is not None
           else sd.query_devices(kind='input')['name'])
    print('Ecoute de : %s' % nom)
    if avec_vosk:
        print('Mots du jeu : %s' % ', '.join(cfg.MOTS_VOIX))
    print()

    maxi = 0.0
    dernier_partiel = ''
    reconnus = collections.Counter()
    debut = time.time()
    fin = debut + duree

    with sd.RawInputStream(samplerate=16000, blocksize=4000, dtype='int16',
                           channels=1, device=peripherique) as flux:
        while time.time() < fin:
            donnees, _ = flux.read(4000)
            octets = bytes(donnees)

            # Niveau crete, en fraction de la pleine echelle 16 bits.
            echantillons = memoryview(octets).cast('h')
            crete = max(max(echantillons), -min(echantillons)) / 32768.0
            maxi = max(maxi, crete)

            if rec is not None:
                if rec.AcceptWaveform(octets):
                    texte = json.loads(rec.Result()).get('text', '')
                    mots = [m for m in texte.split() if m in cfg.MOTS_VOIX]
                    if mots:
                        reconnus.update(mots)
                        print('\r%-78s' % ('  %5.1f s  FINAL    %s'
                                           % (time.time() - debut, ' '.join(mots))))
                    dernier_partiel = ''
                else:
                    texte = json.loads(rec.PartialResult()).get('partial', '')
                    mots = ' '.join(m for m in texte.split() if m in cfg.MOTS_VOIX)
                    if mots and mots != dernier_partiel:
                        print('\r%-78s' % ('  %5.1f s  partiel  %s'
                                           % (time.time() - debut, mots)))
                    dernier_partiel = mots

            reste = int(fin - time.time()) + 1
            print('\r%s %5.1f %%   max %5.1f %%   %3ds ' %
                  (barre(crete), crete * 100, maxi * 100, reste), end='', flush=True)

    print()
    print()
    print('Niveau maximal atteint : %.1f %%' % (maxi * 100))
    if maxi < 0.005:
        print('VERDICT : le micro ne capte RIEN (que du silence numerique).')
        print('  - casque bien branche ? Parametres > Systeme > Son > Entree :')
        print('    le bon peripherique, volume non nul, pas "Muet" ;')
        print('  - Confidentialite > Microphone : acces autorise aux applications')
        print('    de bureau ;')
        print('  - essaie une autre entree : python tester_voix.py --liste')
    elif maxi < 0.05:
        print('VERDICT : le micro capte, mais TRES faiblement. Monte le volume')
        print('  d entree dans Windows, ou approche le micro.')
    else:
        print('VERDICT : le micro capte correctement.')
    if rec is not None:
        if reconnus:
            print('Mots reconnus (resultats finaux) : %s'
                  % ', '.join('%s x%d' % kv for kv in reconnus.most_common()))
            print('Si des mots sont apparus alors que PERSONNE ne les disait, ce sont')
            print('des faux declenchements : casque-micro, ou mots a repeter')
            print('(MOTS_A_REPETER dans config_trio.py).')
        else:
            print('Aucun mot reconnu. Les mots sont ANGLAIS : "fire" se dit "fa-ieur".')


def main():
    p = argparse.ArgumentParser(description='Diagnostic du micro et de la voix.')
    p.add_argument('--liste', action='store_true', help='liste les entrees et sort')
    p.add_argument('--peripherique', type=int, default=None,
                   help='numero de l entree a tester (voir --liste)')
    p.add_argument('--duree', type=float, default=15.0, help='secondes de mesure')
    p.add_argument('--mots', action='store_true', help='fait aussi tourner Vosk')
    args = p.parse_args()

    lister()
    if args.liste:
        return
    peripherique = args.peripherique if args.peripherique is not None else cfg.MICRO
    try:
        mesurer(peripherique, args.duree, args.mots)
    except KeyboardInterrupt:
        print()
    except Exception as erreur:
        print()
        print('Impossible d ouvrir cette entree : %s' % erreur)
        print('Essaie un autre numero avec --peripherique.')


if __name__ == '__main__':
    main()
