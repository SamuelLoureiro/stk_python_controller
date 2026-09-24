#!/usr/bin/env python3
"""Un faux telephone fixe sous la chaise : emet sur le port 8000 comme le vrai.

    python faux_chaise.py                       scenario complet, MultiSense
    python faux_chaise.py --profil zigsim       le meme, facon iPhone
    python faux_chaise.py --cap-initial 170     depart pres de la coupure a 180
    python faux_chaise.py --ecran-dessous       telephone retourne sous l'assise
    python faux_chaise.py --biais-gyro 0.02     gyroscope qui derive (rad/s)
    python faux_chaise.py --verifier            controle les calculs, sans reseau

A lancer dans un SECOND terminal, pendant que tourne :

    python trio.py --aveugle --simulation

Ce que ce script prouve, et ce qu'il ne prouve pas
--------------------------------------------------
Il emet avec les conventions SUPPOSEES dans config_trio.py (sens du yaw de
MultiSense, unite du gyro...). Il valide donc le CODE : calcul de l'angle,
calibration, securites, envoi au serveur. Il ne valide PAS ces suppositions :
seule une mesure sur le vrai telephone sous la vraie chaise le fait
(`python chaise.py`, protocole dans README.md).
"""

import argparse
import math
import sys
import time

import config_trio as cfg
from chaise import (ORDRE_QUATERNION, CapteurChaise, _conjugue, _produit,
                    ecart_angulaire, rotation_verticale)

UUID = b'/ZIGSIM/FAUX-CHAISE'


# ------------------------------------------------------------------ geometrie

def q_axe(axe, degres):
    """Quaternion (x, y, z, w) d'une rotation de <degres> autour de <axe>."""
    n = math.sqrt(sum(a * a for a in axe))
    s = math.sin(math.radians(degres) / 2) / n
    return (axe[0] * s, axe[1] * s, axe[2] * s, math.cos(math.radians(degres) / 2))


def tourner(q, v):
    """Applique la rotation q au vecteur v."""
    x, y, z, _ = _produit(_produit(q, (v[0], v[1], v[2], 0.0)), _conjugue(q))
    return (x, y, z)


MONTAGES = {
    'ecran dessus':           (0.0, 0.0, 0.0, 1.0),
    'ecran dessous':          q_axe((1, 0, 0), 180),
    'incline 20 deg':         q_axe((1, 0, 0), 20),
    'dessous + incline 15':   _produit(q_axe((0, 1, 0), 15), q_axe((1, 0, 0), 180)),
}


def quaternion_chaise(droite, cap_initial, montage):
    """Telephone fixe sous l'assise, chaise tournee de <droite> degres vers la
    droite de l'aveugle (sens des aiguilles vu de dessus).

    Le quaternion va du repere du telephone au repere du monde, z vers le
    haut, comme celui de CoreMotion : la rotation de la chaise, autour de la
    verticale du MONDE, se compose a gauche du montage.
    """
    return _produit(q_axe((0, 0, 1), cap_initial - droite), montage)


def _vers_zigsim(q):
    """(x, y, z, w) -> ordre d'emission de ZIG SIM."""
    x, y, z, w = q
    return (w, x, y, z) if ORDRE_QUATERNION == 'wxyz' else q


# ------------------------------------------------------------------ emission

def _emettre(client, profil, droite, vitesse_droite, args, montage):
    """Un paquet de mesures. vitesse_droite en deg/s, sens des aiguilles."""
    if profil == 'zigsim':
        q = quaternion_chaise(droite, args.cap_initial, montage)
        # Rotation du monde : autour de +z, de -vitesse (sens direct). Le
        # gyroscope la mesure dans le repere du telephone.
        w_monde = (0.0, 0.0, -math.radians(vitesse_droite))
        w = tourner(_conjugue(q), w_monde)
        client.send_message(UUID + b'/quaternion', [float(v) for v in _vers_zigsim(q)])
        client.send_message(UUID + b'/gyro', [float(v + args.biais_gyro) for v in w])
    else:
        # MultiSense : yaw d'Android, qui croit dans le sens des aiguilles.
        yaw = ecart_angulaire(args.cap_initial + droite, 0.0)
        client.send_message(b'/multisense/orientation/yaw', [float(yaw)])
        client.send_message(b'/multisense/orientation/pitch', [0.0])
        client.send_message(b'/multisense/orientation/roll',
                            [180.0 if args.ecran_dessous else 0.0])
        # Ecran dessus, z sort de l'ecran vers le haut : tourner dans le sens
        # des aiguilles est une rotation negative autour de z.
        wz = math.radians(vitesse_droite) * (1 if args.ecran_dessous else -1)
        for axe, v in (('x', 0.0), ('y', 0.0), ('z', wz)):
            client.send_message(('/multisense/gyroscope/' + axe).encode(),
                                [float(v + args.biais_gyro)])


# (duree en s, angle d'arrivee, flux coupe ?, ce qui se passe, ce qu'on attend)
# Angles : > 0 = l'aveugle tourne vers SA droite. En CORRESPONDANCE 'miroir',
# le kart part alors a GAUCHE, donc STEER negatif.
SCENARIO = [
    (7.0,    0, False, 'repos : trio.py attend puis calibre', 'calibration reussie'),
    (2.0,  +30, False, 'l aveugle tourne vers SA droite', 'STEER de plus en plus negatif (miroir)'),
    (2.0,  +30, False, 'il tient la position', 'STEER stable, pres de -0,7'),
    (3.0,  -30, False, 'il passe vers SA gauche', 'STEER passe positif'),
    (2.0,  -30, False, 'il tient', 'STEER stable, pres de +0,7'),
    (1.5,    0, False, 'retour face au muet', 'STEER:+0.000'),
    (2.0, +150, False, 'demi-tour pour regarder l ecran', 'TRICHE (et R_ACCELERATE si le kart accelerait)'),
    (2.0, +150, False, 'il regarde', 'TRICHE maintenu'),
    (2.0,    0, False, 'il se retourne', 'fin de TRICHE'),
    (1.0,  +25, False, 'il tourne a nouveau', 'STEER negatif'),
    (2.0,  +25, True,  'FLUX COUPE (ecran verrouille)', 'STEER:+0.000 apres 0,5 s'),
    (1.0,  +25, False, 'le flux revient', 'STEER negatif a nouveau'),
    (1.5,    0, False, 'retour au neutre', 'STEER:+0.000'),
]


def jouer(args):
    from oscpy.client import OSCClient
    client = OSCClient('127.0.0.1', args.port)
    montage = MONTAGES['ecran dessous' if args.ecran_dessous else 'ecran dessus']
    periode = 1.0 / args.hz
    angle = 0.0
    print('Faux telephone %s sous la chaise -> port %d, %d Hz%s'
          % (args.profil, args.port, args.hz,
             ', ECRAN DESSOUS' if args.ecran_dessous else ''))
    emis, date_emis = 0.0, None     # dernier angle reellement emis, et quand
    for duree, arrivee, coupe, quoi, attendu in SCENARIO:
        print('--- %4.1f s  %-38s attendu : %s' % (duree, quoi, attendu), flush=True)
        depart = angle
        debut = time.time()
        while True:
            ecoule = min(time.time() - debut, duree)
            angle = depart + (arrivee - depart) * ecoule / duree
            if not coupe:
                # Vitesse tiree des angles REELLEMENT emis : le gyro integre
                # alors exactement ce que le cap affiche. Une vitesse theorique
                # par etape laissait 1 a 4 deg d'ecart qui venaient du faux
                # telephone, pas du capteur.
                maintenant = time.time()
                vitesse = 0.0
                if date_emis is not None and maintenant > date_emis:
                    vitesse = (angle - emis) / (maintenant - date_emis)
                _emettre(client, args.profil, angle, vitesse, args, montage)
                emis, date_emis = angle, maintenant
            else:
                date_emis = None
            if ecoule >= duree:
                break
            time.sleep(periode)
    print('scenario termine')


def tenir(args):
    from oscpy.client import OSCClient
    client = OSCClient('127.0.0.1', args.port)
    montage = MONTAGES['ecran dessous' if args.ecran_dessous else 'ecran dessus']
    fin = time.time() + args.duree
    while time.time() < fin:
        _emettre(client, args.profil, args.angle, 0.0, args, montage)
        time.sleep(1.0 / args.hz)
    print('fin')


# ------------------------------------------------------------ verification

def _rejouer(profil, etapes, biais=0.0, cap_initial=0.0, montage=None, hz=30):
    """Rejoue des mesures datees dans un CapteurChaise, sans reseau.

    etapes : liste de (duree, angle d'arrivee). La premiere sert de repos et
    de calibration. Renvoie l'etat final.
    """
    montage = montage or MONTAGES['ecran dessus']
    c = CapteurChaise(port=0, profil=profil)
    t, angle = 1000.0, 0.0
    for n, (duree, arrivee) in enumerate(etapes):
        if n == 1:
            ok, explication = c.fin_calibration()
            assert ok, explication
        if n == 0:
            c.debut_calibration()
        pas = int(duree * hz)
        depart = angle
        vitesse = (arrivee - depart) / duree
        for i in range(1, pas + 1):
            angle = depart + (arrivee - depart) * i / pas
            t += 1.0 / hz
            if profil == 'zigsim':
                q = quaternion_chaise(angle, cap_initial, montage)
                w = tourner(_conjugue(q), (0.0, 0.0, -math.radians(vitesse)))
                c._recevoir(UUID + b'/quaternion', _vers_zigsim(q), t)
                c._recevoir(UUID + b'/gyro', [v + biais for v in w], t)
            else:
                c._recevoir(b'/multisense/orientation/yaw',
                            [ecart_angulaire(cap_initial + angle, 0.0)], t)
                for axe, v in (('x', 0.0), ('y', 0.0), ('z', -math.radians(vitesse))):
                    c._recevoir(('/multisense/gyroscope/' + axe).encode(), [v + biais], t)
    return c.etat(maintenant=t)


def verifier():
    ok = True

    print('1. Rotation relative autour de la verticale, sur quatre montages')
    print('   (l aveugle tourne de -170 a +170 deg, depart a plusieurs caps)')
    for nom, montage in MONTAGES.items():
        pire = 0.0
        for cap_initial in (0.0, 90.0, 170.0, -179.0):
            q0 = quaternion_chaise(0.0, cap_initial, montage)
            for droite in range(-170, 171, 5):
                q = quaternion_chaise(droite, cap_initial, montage)
                mesure = cfg.SIGNE_CAP['zigsim'] * rotation_verticale(_vers_zigsim(q),
                                                                        _vers_zigsim(q0))
                pire = max(pire, abs(mesure - droite))
        ok &= pire < 1e-6
        print('   %-22s erreur max %.2e deg   %s' % (nom, pire, 'OK' if pire < 1e-6 else 'ECHEC'))

    print()
    print('2. Pourquoi il faut la rotation RELATIVE : cap du quaternion absolu')
    for nom in ('ecran dessus', 'ecran dessous'):
        x, y, z, w = quaternion_chaise(30.0, 0.0, MONTAGES[nom])
        print('   %-14s z=%+.3f w=%+.3f -> %s' % (
            nom, z, w, 'indefini (atan2(0, 0))' if abs(z) + abs(w) < 1e-9
            else '%+.1f deg' % math.degrees(2 * math.atan2(z, w))))

    print()
    print('3. Assise qui bascule de 5 deg en plus (chaise a bascule) : erreur induite')
    pire = 0.0
    for droite in range(-60, 61, 5):
        q0 = quaternion_chaise(0.0, 0.0, MONTAGES['ecran dessus'])
        q = _produit(q_axe((1, 0, 0), 5), quaternion_chaise(droite, 0.0, MONTAGES['ecran dessus']))
        mesure = cfg.SIGNE_CAP['zigsim'] * rotation_verticale(_vers_zigsim(q), _vers_zigsim(q0))
        pire = max(pire, abs(mesure - droite))
    print('   erreur max %.2f deg sur +-60 deg (pour information)' % pire)

    print()
    print('4. Chaine complete du capteur, rejouee hors reseau')
    cas = [
        ('zigsim, ecran dessous, gyro biaise', 'zigsim',
         dict(biais=0.02, montage=MONTAGES['ecran dessous'])),
        ('zigsim, dessous + incline 15', 'zigsim',
         dict(biais=0.02, montage=MONTAGES['dessous + incline 15'])),
        ('multisense, depart a 170 (coupure)', 'multisense',
         dict(biais=0.02, cap_initial=170.0)),
    ]
    for titre, profil, options in cas:
        for cible in (40.0, -30.0, 150.0):
            e = _rejouer(profil, [(1.5, 0.0), (2.0, cible)], **options)
            juste_cap = abs(e.angle_cap - cible) < 0.01
            juste_gyro = abs(ecart_angulaire(e.angle_gyro, cible)) < 1.0
            ok &= juste_cap and juste_gyro
            print('   %-36s cible %+6.1f   cap %+7.2f   gyro %+7.2f   %s'
                  % (titre, cible, e.angle_cap, e.angle_gyro,
                     'OK' if juste_cap and juste_gyro else 'ECHEC'))

    print()
    print('5. Calibration refusee si la chaise bouge')
    c = CapteurChaise(port=0, profil='zigsim')
    c.debut_calibration()
    t = 0.0
    for i in range(45):
        t += 1 / 30
        q = quaternion_chaise(i * 0.5, 0.0, MONTAGES['ecran dessus'])
        c._recevoir(UUID + b'/quaternion', _vers_zigsim(q), t)
        c._recevoir(UUID + b'/gyro', tourner(_conjugue(q), (0, 0, -math.radians(15))), t)
    reussi, explication = c.fin_calibration()
    ok &= not reussi
    print('   %s : %s' % ('OK, refusee' if not reussi else 'ECHEC, acceptee', explication))

    print()
    print('TOUT EST JUSTE' if ok else 'AU MOINS UNE VERIFICATION ECHOUE')
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description='Faux telephone sous la chaise.')
    p.add_argument('--profil', choices=['multisense', 'zigsim'], default='multisense')
    p.add_argument('--port', type=int, default=cfg.PORT_OSC_CHAISE)
    p.add_argument('--hz', type=int, default=30)
    p.add_argument('--cap-initial', type=float, default=0.0,
                   help='cap de depart en degres (170 : tester la coupure a 180)')
    p.add_argument('--ecran-dessous', action='store_true')
    p.add_argument('--biais-gyro', type=float, default=0.0, help='rad/s ajoutes au gyro')
    p.add_argument('--angle', type=float, default=None,
                   help='tenir cet angle au lieu de derouler le scenario')
    p.add_argument('--duree', type=float, default=5.0)
    p.add_argument('--verifier', action='store_true', help='controle hors reseau')
    args = p.parse_args()

    if args.verifier:
        return verifier()
    try:
        if args.angle is not None:
            tenir(args)
        else:
            jouer(args)
    except KeyboardInterrupt:
        print('\ninterrompu')
    return 0


if __name__ == '__main__':
    sys.exit(main())
