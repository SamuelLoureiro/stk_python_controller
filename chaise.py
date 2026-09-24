#!/usr/bin/env python3
"""Le telephone sous la chaise : de combien l'aveugle a-t-il pivote ?

Pourquoi pas l'angle de volant du TP1
-------------------------------------
L'angle de volant du TP1 mesure la gravite projetee dans le plan de l'ecran. Sous
une chaise, le telephone tourne autour de la VERTICALE -- et une rotation
autour de la verticale ne change rien a la gravite. L'angle de volant reste
fige quoi que fasse l'aveugle. Il faut un cap (un lacet), pas une inclinaison.

Deux facons de l'obtenir, codees toutes les deux (config_trio.METHODE_CHAISE)
------------------------------------------------------------------------------
'cap'  : l'orientation absolue du telephone.
         ZIG SIM : on calcule la rotation qui fait passer du quaternion de
         reference q0 au quaternion courant q, soit r = q * conj(q0), et on en
         garde l'angle autour de la verticale : 2 * atan2(r.z, r.w).
         Si la chaise a tourne de theta, q = Rz(theta) * q0, donc r = Rz(theta)
         exactement : l'angle est juste quelle que soit la facon dont le
         telephone est fixe (ecran dessus, dessous, incline), sans angle
         d'Euler, donc sans blocage de cardan.
         Il faut bien la rotation RELATIVE : sur le quaternion absolu, un
         telephone ecran vers le bas donne z = w = 0 et l'angle n'est plus
         defini (verifie par faux_chaise.py --verifier).
         MultiSense : /multisense/orientation/yaw, ecart au neutre. Telephone a
         plat = loin du blocage de cardan, le yaw d'Euler y est sain.
'gyro' : la vitesse de rotation autour de la verticale, integree. Insensible
         au magnetometre -- donc a l'acier du verin de la chaise -- mais
         derive lentement.

Dans les deux cas, les ecarts passent par ecart_angulaire : l'exemple du sujet
du TP1 donne un yaw de -176,49, a trois degres de la coupure a 180.

Utilisation
-----------
    python chaise.py                  outil de mesure en direct
    python chaise.py --profil zigsim  forcer l'appli si la detection hesite

C'est l'outil qui sert a regler SIGNE_*, UNITE_GYRO, METHODE_CHAISE et
ANGLE_MAXI dans config_trio.py. Protocole dans GUIDE.md, section 5.
"""

import argparse
import collections
import math
import sys
import threading
import time
from dataclasses import dataclass, field

import config_trio as cfg

AXES = 'xyz'

# ZIG SIM envoie le quaternion dans l'ordre x, y, z, w : au repos a plat on lit
# une derniere composante proche de 1, ce qui identifie w sans ambiguite
# (mesure du 2026-09-08, iPhone 14 Pro).
ORDRE_QUATERNION = 'xyzw'


def ecart_angulaire(a, b):
    """a - b ramene dans -180..+180, pour que le passage par 180 ne saute pas."""
    return (a - b + 180) % 360 - 180


def gravite_telephone(q):
    """Direction de la gravite, exprimee dans le repere du telephone.

    C'est la troisieme ligne de la matrice de rotation, changee de signe : le
    quaternion de ZIG SIM va du repere du telephone vers celui du monde, z
    vers le haut (convention validee par le volant du TP1, qui s'en sert).
    """
    x, y, z, w = (q[1], q[2], q[3], q[0]) if ORDRE_QUATERNION == 'wxyz' else q
    return (-2 * (x * z - w * y), -2 * (y * z + w * x), -(1 - 2 * (x * x + y * y)))


# ------------------------------------------------------------------ quaternions

def _en_xyzw(q):
    """Remet un quaternion dans l'ordre x, y, z, w, quel que soit l'emetteur."""
    if ORDRE_QUATERNION == 'wxyz':
        w, x, y, z = q
        return (x, y, z, w)
    return tuple(q)


def _produit(a, b):
    """Produit de deux quaternions, ordre x, y, z, w."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def _conjugue(q):
    x, y, z, w = q
    return (-x, -y, -z, w)


def rotation_verticale(q, q0):
    """Degres dont le telephone a tourne autour de la verticale depuis q0.

    Sens direct positif : inverse des aiguilles d'une montre vu de dessus,
    regle de la main droite avec z vers le haut (convention de CoreMotion).
    Les quaternions sont ceux de ZIG SIM, dans l'ordre de ORDRE_QUATERNION.
    """
    x, y, z, w = _produit(_en_xyzw(q), _conjugue(_en_xyzw(q0)))
    return ecart_angulaire(math.degrees(2 * math.atan2(z, w)), 0.0)


def _agitation(vitesses):
    """Moyenne quadratique des vitesses : nulle seulement si rien ne bouge.

    Pas l'ecart-type : une rotation reguliere pendant la calibration a un
    ecart-type nul, et passerait pour de l'immobilite.
    """
    if not vitesses:
        return 0.0
    return math.sqrt(sum(v * v for v in vitesses) / len(vitesses))


# ------------------------------------------------------------------------ etat

@dataclass
class EtatChaise:
    """Instantane de la chaise. Angles en degres, > 0 = l'aveugle tourne a SA droite."""
    profil: str = 'auto'
    appareil: str = None
    recu: bool = False          # au moins un message utile depuis le demarrage
    frais: bool = False         # dernier message plus recent que SILENCE_MAX
    age: float = None           # s depuis le dernier message de la methode retenue
    calibre: bool = False
    angle: float = None         # LA mesure a utiliser (methode retenue)
    methode: str = ''           # methode effectivement utilisee
    angle_cap: float = None
    angle_gyro: float = None
    vitesse: float = 0.0        # deg/s autour de la verticale, biais retire
    hz_orientation: float = 0.0
    hz_gyro: float = 0.0
    inclinaison: float = None   # deg entre le telephone et l'horizontale (ZIG SIM)
    pitch: float = None         # MultiSense, pour information
    roll: float = None
    gyro_brut: tuple = (0.0, 0.0, 0.0)
    par_axe: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    par_axe_total: list = field(default_factory=lambda: [0.0, 0.0, 0.0])


class CapteurChaise:
    """Ecoute le telephone fixe sous la chaise et tient l'angle a jour.

    L'appli ('zigsim' ou 'multisense') est reconnue au premier message.
    Thread-safe : oscpy appelle _sur_message depuis son propre thread, et la
    voix peut demander un recentrage depuis le sien.
    """

    def __init__(self, port=None, profil='auto', methode=None):
        self.port = port if port is not None else cfg.PORT_OSC_CHAISE
        self.profil = profil
        self.methode = methode or cfg.METHODE_CHAISE
        self.appareil = None
        self.calibre = False
        self.n_messages = 0

        self._verrou = threading.RLock()
        self._osc = None

        # Orientation. Les references (q0, yaw0) prennent la premiere valeur
        # recue, pour que l'outil de mesure affiche quelque chose avant toute
        # calibration ; calibrer() les remplace.
        self._q = None
        self._q0 = None
        self._yaw = None
        self._yaw0 = None
        self._pitch = None
        self._roll = None

        # Gyroscope
        self._gyro = [0.0, 0.0, 0.0]
        self._biais = [0.0, 0.0, 0.0]
        self._t_gyro = None
        self._integre = 0.0         # deg, convention interne (droite +)
        self._integre0 = 0.0
        self._vitesse = 0.0
        self._par_axe = [0.0, 0.0, 0.0]   # rotation par axe brut depuis le neutre
        # Meme chose SANS signe : c'est elle qui designe l'axe de la chaise. Le
        # cumul signe s'annule a chaque aller-retour, alors que les petits
        # basculements de l'assise s'accumulent. Mesure du 2026-09-24 : apres
        # +-66 deg de rotation, le cumul signe designait y (un basculement)
        # au lieu de z.
        self._par_axe_total = [0.0, 0.0, 0.0]

        # Calibration en cours : None, ou la liste des echantillons collectes
        self._collecte = None
        self._cap_debut_calibration = None

        self._dates_orientation = collections.deque(maxlen=200)
        self._dates_gyro = collections.deque(maxlen=200)
        self._dernier_orientation = 0.0
        self._dernier_gyro = 0.0

    # ------------------------------------------------------------ reception

    def _sur_message(self, adresse, *valeurs):
        self._recevoir(adresse, valeurs, time.time())

    def _recevoir(self, adresse, valeurs, t):
        """Traite un message. Separe de _sur_message pour pouvoir rejouer des
        messages dates hors reseau (faux_chaise.py --verifier)."""
        if isinstance(adresse, bytes):
            adresse = adresse.decode('utf8', 'replace')
        segments = adresse.strip('/').split('/')
        if not segments or not valeurs:
            return
        feuille = segments[-1]

        # ZIG SIM prefixe tout par /ZIGSIM/<uuid>/, sauf deviceinfo qui sort
        # sur /<uuid>/deviceinfo : on reconnait les deux.
        if self.profil == 'auto':
            if segments[0] == 'ZIGSIM' or feuille == 'deviceinfo':
                self.profil = 'zigsim'
            elif segments[0] == 'multisense':
                self.profil = 'multisense'
            else:
                return

        with self._verrou:
            self.n_messages += 1
            if self.profil == 'zigsim':
                self._message_zigsim(feuille, valeurs, t)
            else:
                self._message_multisense(segments, feuille, valeurs, t)

    def _message_zigsim(self, feuille, valeurs, t):
        if feuille == 'deviceinfo':
            if isinstance(valeurs[0], bytes):
                self.appareil = valeurs[0].decode('utf8', 'replace')
            return
        try:
            nombres = [float(v) for v in valeurs]
        except (TypeError, ValueError):
            return
        if feuille == 'quaternion' and len(nombres) >= 4:
            self._q = tuple(nombres[:4])
            if self._q0 is None:
                self._q0 = self._q
            self._dates_orientation.append(t)
            self._dernier_orientation = t
        elif feuille in ('gyro', 'gyroscope') and len(nombres) >= 3:
            self._integrer(nombres[:3], t)

    def _message_multisense(self, segments, feuille, valeurs, t):
        parent = segments[-2] if len(segments) >= 2 else ''
        try:
            v = float(valeurs[0])
        except (TypeError, ValueError):
            return
        if parent == 'orientation':
            if feuille == 'yaw':
                self._yaw = v
                if self._yaw0 is None:
                    self._yaw0 = v
                self._dates_orientation.append(t)
                self._dernier_orientation = t
            elif feuille == 'pitch':
                self._pitch = v
            elif feuille == 'roll':
                self._roll = v
        elif parent in ('gyroscope', 'gyro') and feuille in AXES:
            # MultiSense envoie une adresse par axe. Le vecteur est reconstitue
            # et on integre a l'arrivee de l'axe qui porte la chaise.
            self._gyro[AXES.index(feuille)] = v
            if feuille == cfg.AXE_GYRO_MULTISENSE:
                self._integrer(list(self._gyro), t)

    # ------------------------------------------------------------- gyroscope

    def _facteur_gyro(self):
        """Unite brute -> deg/s."""
        return math.degrees(1.0) if cfg.UNITE_GYRO.get(self.profil) == 'rad' else 1.0

    def _vitesse_verticale(self, w, biais):
        """deg/s autour de la verticale, dans la convention interne (droite +)."""
        d = [w[i] - biais[i] for i in range(3)]
        if self.profil == 'zigsim' and self._q is not None:
            # Projection sur la verticale montante, exprimee dans le repere du
            # telephone : le montage (ecran dessus, dessous...) n'importe pas.
            gx, gy, gz = gravite_telephone(self._q)
            brut = -(d[0] * gx + d[1] * gy + d[2] * gz)
        elif self.profil == 'zigsim':
            brut = d[2]         # pas de quaternion : on suppose le telephone a plat
        else:
            brut = d[AXES.index(cfg.AXE_GYRO_MULTISENSE)]
        return cfg.SIGNE_GYRO.get(self.profil, 1) * brut * self._facteur_gyro()

    def _integrer(self, w, t):
        self._gyro = list(w)
        self._dates_gyro.append(t)
        if self._collecte is not None:
            self._collecte.append((list(w), self._vitesse_verticale(w, (0.0, 0.0, 0.0))))

        v = self._vitesse_verticale(w, self._biais)
        if self._t_gyro is not None:
            dt = t - self._t_gyro
            # Au-dela de 0,2 s, c'est un trou dans le flux : integrer a travers
            # inventerait une rotation. On reprend simplement a partir d'ici.
            if 0.0 < dt < 0.2:
                self._integre += v * dt
                facteur = self._facteur_gyro()
                for i in range(3):
                    rotation = (w[i] - self._biais[i]) * facteur * dt
                    self._par_axe[i] += rotation
                    self._par_axe_total[i] += abs(rotation)
        self._t_gyro = t
        self._dernier_gyro = t
        self._vitesse = v

    # ---------------------------------------------------------------- angles

    def _angle_cap(self):
        if self.profil == 'zigsim':
            if self._q is None or self._q0 is None:
                return None
            brut = rotation_verticale(self._q, self._q0)
        elif self.profil == 'multisense':
            if self._yaw is None or self._yaw0 is None:
                return None
            brut = ecart_angulaire(self._yaw, self._yaw0)
        else:
            return None
        return cfg.SIGNE_CAP.get(self.profil, 1) * brut

    def _angle_gyro(self):
        if self._t_gyro is None:
            return None
        return ecart_angulaire(self._integre - self._integre0, 0.0)

    # ----------------------------------------------------------- calibration

    def debut_calibration(self):
        """Commence a collecter : la chaise doit rester immobile jusqu'a fin_calibration()."""
        with self._verrou:
            self._collecte = []
            self._cap_debut_calibration = self._angle_cap()

    def fin_calibration(self):
        """Retient la position actuelle comme neutre et estime le biais du gyro.

        Renvoie (reussi, explication). Refuse si la chaise a bouge : un biais
        estime sur un mouvement ferait deriver l'angle a vitesse constante, et
        le kart braquerait de plus en plus sans que personne ne bouge.
        """
        with self._verrou:
            echantillons, self._collecte = self._collecte or [], None
            if self._q is None and self._yaw is None and not echantillons:
                return False, 'aucune donnee du telephone'

            cap = self._angle_cap()
            if cap is not None and self._cap_debut_calibration is not None:
                bouge = abs(ecart_angulaire(cap, self._cap_debut_calibration))
                if bouge > 2.0:
                    return False, 'la chaise a tourne de %.1f deg pendant la calibration' % bouge

            if len(echantillons) >= 5:
                agitation = _agitation([v for _, v in echantillons])
                if agitation > cfg.AGITATION_MAX:
                    return False, ('la chaise a bouge pendant la calibration '
                                   '(%.1f deg/s, maxi %.1f)' % (agitation, cfg.AGITATION_MAX))
            if echantillons:
                n = len(echantillons)
                self._biais = [sum(w[i] for w, _ in echantillons) / n for i in range(3)]

            self._fixer_neutre()
            self.calibre = True
            return True, 'neutre fixe' + (', biais du gyro retire (%d mesures)'
                                          % len(echantillons) if echantillons else '')

    def calibrer(self, duree=None):
        """Calibration complete, bloquante. Pour le demarrage."""
        self.debut_calibration()
        time.sleep(duree if duree is not None else cfg.DUREE_CALIBRATION)
        return self.fin_calibration()

    def _fixer_neutre(self):
        self._q0 = self._q
        self._yaw0 = self._yaw
        self._integre0 = self._integre
        self._par_axe = [0.0, 0.0, 0.0]
        self._par_axe_total = [0.0, 0.0, 0.0]

    def recentrer(self):
        """Instantane : la position actuelle devient le neutre, biais inchange.

        C'est ce que declenchent la touche C et le mot "center" en pleine
        course. Pas de collecte ici : on ne peut pas figer la direction une
        seconde et demie pendant que le kart roule.
        """
        with self._verrou:
            if self._q is None and self._yaw is None and self._t_gyro is None:
                return False
            self._fixer_neutre()
            return True

    # ------------------------------------------------------------ API publique

    def demarrer(self):
        from oscpy.server import OSCThreadServer
        self._osc = OSCThreadServer(default_handler=self._sur_message)
        self._osc.listen(address='0.0.0.0', port=self.port, default=True)
        return self

    def arreter(self):
        # Ordre impose par oscpy : sortir le thread de sa boucle AVANT
        # de fermer la socket, sinon WinError 10038 au Ctrl+C.
        if self._osc:
            self._osc.terminate_server()
            self._osc.join_server(timeout=1.0)
            try:
                self._osc.stop_all()
            except (RuntimeError, OSError):
                pass
            self._osc = None

    def attendre_donnees(self, delai=30.0):
        """True des qu'un message utile arrive, False au bout de <delai> s."""
        fin = time.time() + delai
        while time.time() < fin:
            if self._dernier_orientation or self._dernier_gyro:
                return True
            time.sleep(0.1)
        return False

    def etat(self, maintenant=None):
        t = time.time() if maintenant is None else maintenant
        with self._verrou:
            cap = self._angle_cap()
            gyro = self._angle_gyro()

            # La methode choisie n'a pas de donnees (capteur pas active dans
            # l'appli) : on prend l'autre plutot que de ne rien piloter. Le
            # champ methode le dit, et la ligne d'etat l'affiche.
            methode = self.methode
            angle = cap if methode == 'cap' else gyro
            if angle is None:
                autre = 'gyro' if methode == 'cap' else 'cap'
                angle = gyro if autre == 'gyro' else cap
                if angle is not None:
                    methode = autre

            dernier = self._dernier_orientation if methode == 'cap' else self._dernier_gyro
            age = (t - dernier) if dernier else None

            inclinaison = None
            if self.profil == 'zigsim' and self._q is not None:
                gz = gravite_telephone(self._q)[2]
                inclinaison = math.degrees(math.acos(min(1.0, abs(gz))))

            return EtatChaise(
                profil=self.profil, appareil=self.appareil,
                recu=bool(self._dernier_orientation or self._dernier_gyro),
                frais=age is not None and age < cfg.SILENCE_MAX,
                age=age, calibre=self.calibre,
                angle=angle, methode=methode if angle is not None else '',
                angle_cap=cap, angle_gyro=gyro, vitesse=self._vitesse,
                hz_orientation=sum(1 for d in self._dates_orientation if t - d < 1.0),
                hz_gyro=sum(1 for d in self._dates_gyro if t - d < 1.0),
                inclinaison=inclinaison, pitch=self._pitch, roll=self._roll,
                gyro_brut=tuple(self._gyro), par_axe=list(self._par_axe),
                par_axe_total=list(self._par_axe_total))


# ----------------------------------------------------------- outil de mesure

def _barre(valeur, largeur=31):
    """Curseur -1..+1 sur une echelle en texte."""
    pos = int((max(-1.0, min(1.0, valeur)) + 1) / 2 * (largeur - 1))
    ligne = ['-'] * largeur
    ligne[largeur // 2] = '|'
    ligne[pos] = '#'
    return ''.join(ligne)


def _fmt(angle):
    if angle is None:
        return '   -   '
    return '%+7.1f' % (angle if abs(angle) >= 0.05 else 0.0)   # pas de -0.0


def _touche():
    """Touche pressee dans la console, ou None. Windows seulement."""
    try:
        import msvcrt
    except ImportError:
        return None
    if msvcrt.kbhit():
        return msvcrt.getwch().lower()
    return None


def _mesurer(port, profil, methode):
    from reseau import activer_ansi, bandeau_reseau, ips_locales
    activer_ansi()

    capteur = CapteurChaise(port=port, profil=profil, methode=methode)
    try:
        capteur.demarrer()
    except OSError as erreur:
        print('Port %d occupe : %s' % (port, erreur), file=sys.stderr)
        print('Fermer trio.py (ou une autre fenetre chaise.py) avant.', file=sys.stderr)
        return 1

    reseau = bandeau_reseau(ips_locales(), port)
    points = []
    message = ('Position neutre (face au muet, ou face a l ecran en solo), '
               'immobile, puis C pour calibrer.')
    try:
        while True:
            touche = _touche()
            if touche == 'q':
                break
            if touche == 'c':
                print('\n  calibration : NE BOUGE PLUS (%.1f s)...' % cfg.DUREE_CALIBRATION,
                      flush=True)
                ok, explication = capteur.calibrer()
                message = ('calibre : ' if ok else 'REFUSE : ') + explication
            elif touche == 'r':
                capteur.recentrer()
                message = 'neutre deplace ici (biais inchange)'
            elif touche in ('\r', '\n'):
                e = capteur.etat()
                points.append((len(points) + 1, e.angle_cap, e.angle_gyro))
                message = 'point %d note' % len(points)

            e = capteur.etat()
            if not e.recu:
                print('\033[H\033[J'
                      'chaise.py -- en attente du telephone sur le port %d\n\n%s\n\n'
                      '  ZIG SIM    : capteurs QUATERNION + GYRO, OSC/UDP, verrouillage auto "Jamais"\n'
                      '  MultiSense : Orientation + Gyroscope\n\n'
                      '  q : quitter' % (port, reseau), flush=True)
                time.sleep(0.2)
                continue

            ratio = ''
            if e.angle_cap is not None and e.angle_gyro is not None and abs(e.angle_cap) > 20:
                r = e.angle_gyro / e.angle_cap
                ratio = 'gyro / cap = %.2f' % r
                if 40 < abs(r) < 80:
                    ratio += '   <-- le gyro est en deg/s : UNITE_GYRO[%r] = "deg"' % e.profil
                elif 0.005 < abs(r) < 0.03:
                    ratio += '   <-- le gyro est en rad/s : UNITE_GYRO[%r] = "rad"' % e.profil
                elif r < 0:
                    ratio += '   <-- signes opposes : un des deux SIGNE_* est faux'
            else:
                ratio = '(tourne de plus de 20 deg pour comparer gyro et cap)'

            ecart = ''
            if e.angle_cap is not None and e.angle_gyro is not None:
                ecart = 'ecart cap - gyro : %+.1f deg' % ecart_angulaire(e.angle_cap, e.angle_gyro)

            dominant = max(range(3), key=lambda i: e.par_axe_total[i])
            if e.inclinaison is not None:
                pose = 'inclinaison du telephone : %.0f deg%s' % (
                    e.inclinaison, '  (a plat)' if e.inclinaison < 15 else '')
            elif e.pitch is not None or e.roll is not None:
                pose = 'pitch %s  roll %s  (MultiSense, pour information)' % (
                    _fmt(e.pitch), _fmt(e.roll))
            else:
                pose = ''

            lignes_points = '\n'.join('    #%-2d  cap %s   gyro %s' % (n, _fmt(c), _fmt(g))
                                      for n, c, g in points[-8:]) or '    (aucun)'
            print('\033[H\033[J'
                  'chaise.py   profil=%s   %s\n'
                  '  orientation %2d Hz   gyro %2d Hz   %s\n\n'
                  '  Assis sur la chaise, tourne vers TA droite : les deux angles\n'
                  '  doivent devenir POSITIFS. Sinon : SIGNE_CAP / SIGNE_GYRO.\n\n'
                  '  CAP  %s deg  %s%s\n'
                  '  GYRO %s deg  %s%s\n'
                  '  %s\n  %s\n\n'
                  '  vitesse verticale %+6.1f deg/s\n'
                  '  gyro brut  x %+.3f  y %+.3f  z %+.3f\n'
                  '  rotation par axe depuis le neutre : x %+6.1f  y %+6.1f  z %+6.1f deg\n'
                  '  axe de la chaise (celui qui a le plus tourne, sans signe) : %s\n'
                  '  %s\n\n'
                  '  %s\n\n'
                  '  Entree : noter un point   C : calibrer (immobile)   R : neutre ici'
                  '   Q : quitter\n'
                  '  points notes (reperes au sol a 0, +45, -45, +90...) :\n%s'
                  % (e.profil, e.appareil or '', e.hz_orientation, e.hz_gyro,
                     'CALIBRE' if e.calibre else 'reference = premier message recu',
                     _fmt(e.angle_cap), _barre((e.angle_cap or 0) / 90),
                     '   <- retenue' if capteur.methode == 'cap' else '',
                     _fmt(e.angle_gyro), _barre((e.angle_gyro or 0) / 90),
                     '   <- retenue' if capteur.methode == 'gyro' else '',
                     ecart, ratio, e.vitesse, *e.gyro_brut, *e.par_axe,
                     AXES[dominant], pose, message, lignes_points),
                  flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        capteur.arreter()
    print('\nArrete.')
    if points:
        print('Points notes :')
        for n, c, g in points:
            print('  #%-2d  cap %s   gyro %s' % (n, _fmt(c), _fmt(g)))
    return 0


def main():
    p = argparse.ArgumentParser(description='Outil de mesure du telephone sous la chaise.')
    p.add_argument('-p', '--port', type=int, default=cfg.PORT_OSC_CHAISE)
    p.add_argument('--profil', choices=['auto', 'zigsim', 'multisense'], default='auto')
    p.add_argument('--methode', choices=['cap', 'gyro'], default=None,
                   help='methode mise en avant (defaut : config_trio.METHODE_CHAISE)')
    args = p.parse_args()
    return _mesurer(args.port, args.profil, args.methode)


if __name__ == '__main__':
    sys.exit(main())
