#!/usr/bin/env python3
"""Prepare le dossier et verifie que tout est pret. A lancer une fois.

    pip install -r requirements.txt
    python installer.py

Ce qu'il fait, dans l'ordre :

  1. verifie la version de Python et les paquets ;
  2. telecharge le modele de voix Vosk (~40 Mo) dans models/, s'il manque ;
  3. essaie de creer la manette virtuelle (Windows) : sans elle, on joue
     avec --fleches ;
  4. verifie les calculs de la chaise (faux_chaise.py --verifier).

Il ne modifie rien d'autre que le dossier models/, et peut etre relance sans
risque : ce qui est deja fait est saute.
"""

import importlib
import os
import sys
import urllib.request
import zipfile

import config_trio as cfg

URL_MODELE = 'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip'

PAQUETS = [
    ('oscpy', 'reception OSC du telephone'),
    ('keyboard', 'le serveur tape les touches'),
    ('vosk', 'reconnaissance vocale'),
    ('sounddevice', 'micro'),
]

bilan = []          # (ok, texte)


def noter(ok, texte):
    bilan.append((ok, texte))
    print('  [%s] %s' % ('OK' if ok else '!!', texte))


def verifier_python():
    print('1. Python et paquets')
    v = sys.version_info
    noter(v >= (3, 9), 'Python %d.%d (%s)' % (v.major, v.minor, sys.executable))
    manquants = []
    for nom, role in PAQUETS:
        try:
            importlib.import_module(nom)
            noter(True, '%-12s %s' % (nom, role))
        except ImportError:
            manquants.append(nom)
            noter(False, '%-12s MANQUANT (%s)' % (nom, role))
    if manquants:
        print('     -> pip install -r requirements.txt')
    return not manquants


def telecharger_modele():
    print()
    print('2. Modele de voix Vosk')
    if os.path.isdir(cfg.MODELE_VOSK):
        noter(True, 'deja present : %s' % cfg.MODELE_VOSK)
        return True
    dossier = os.path.dirname(cfg.MODELE_VOSK)
    os.makedirs(dossier, exist_ok=True)
    archive = os.path.join(dossier, 'vosk-model.zip')
    print('  telechargement de %s (~40 Mo)...' % URL_MODELE)

    def progression(blocs, taille_bloc, total):
        if total > 0:
            fait = min(100, blocs * taille_bloc * 100 // total)
            print('\r  %3d %%' % fait, end='', flush=True)

    try:
        urllib.request.urlretrieve(URL_MODELE, archive, progression)
        print()
        with zipfile.ZipFile(archive) as z:
            z.extractall(dossier)
    except Exception as erreur:
        print()
        noter(False, 'telechargement impossible : %s' % erreur)
        print('     -> telecharger a la main %s' % URL_MODELE)
        print('        et le decompresser dans %s' % dossier)
        return False
    finally:
        if os.path.exists(archive):
            os.remove(archive)
    ok = os.path.isdir(cfg.MODELE_VOSK)
    noter(ok, 'modele installe dans %s' % cfg.MODELE_VOSK if ok
          else 'archive decompressee, mais %s introuvable' % cfg.MODELE_VOSK)
    return ok


def verifier_manette():
    print()
    print('3. Manette virtuelle (direction analogique)')
    if sys.platform != 'win32':
        noter(False, 'hors Windows : utiliser STK_input_server_v2.py (branche performance)'
                     ' ou jouer avec --fleches')
        return False
    try:
        import vgamepad
        vgamepad.VX360Gamepad()     # Windows fait le bruit d'un branchement : normal
        noter(True, 'manette Xbox 360 virtuelle creee')
        return True
    except ImportError:
        noter(False, 'vgamepad absent : pip install -r requirements.txt, ou jouer avec --fleches')
    except Exception as erreur:
        noter(False, 'pilote ViGEmBus absent ou en panne (%s) : le reinstaller,'
                     ' ou jouer avec --fleches' % erreur)
    return False


def verifier_calculs():
    print()
    print('4. Calculs de la chaise')
    import faux_chaise
    import contextlib
    import io
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        code = faux_chaise.verifier()
    noter(code == 0, 'faux_chaise.py --verifier : %s'
          % ('TOUT EST JUSTE' if code == 0 else 'ECHEC, voir python faux_chaise.py --verifier'))
    return code == 0


def main():
    print()
    print('=== Installation de TRIO ===')
    print()
    paquets = verifier_python()
    telecharger_modele()
    verifier_manette()
    if paquets:
        verifier_calculs()

    problemes = [texte for ok, texte in bilan if not ok]
    print()
    if not problemes:
        print('Tout est pret. Suite : GUIDE.md, section 2 (tester sans materiel).')
    else:
        print('%d point(s) a regler :' % len(problemes))
        for texte in problemes:
            print('  - %s' % texte)
    return 0 if not problemes else 1


if __name__ == '__main__':
    sys.exit(main())
