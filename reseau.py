#!/usr/bin/env python3
"""L'IP du PC a saisir dans l'appli du telephone, avec le nom de la carte reseau
(les cartes virtuelles VMware / VirtualBox ne recoivent rien du telephone)."""

import locale
import os
import re
import socket
import subprocess

JAUNE = '\033[93m'
ROUGE = '\033[91m'
GRIS = '\033[90m'
BLANC = '\x1b[0m'


def activer_ansi():
    try:
        import ctypes
        k = ctypes.windll.kernel32   # AttributeError hors Windows : sans objet
        mode = ctypes.c_uint32()
        h = k.GetStdHandle(-11)
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            k.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


def noms_interfaces():
    """ip -> nom de la carte reseau, lu dans ipconfig. {} si indisponible."""
    if os.name != 'nt':
        return {}
    try:
        brut = subprocess.run(['ipconfig'], capture_output=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    # ipconfig ecrit en page de codes OEM (cp850), pas en ANSI
    try:
        texte = brut.decode('oem', 'replace')
    except LookupError:
        texte = brut.decode(locale.getpreferredencoding(False), 'replace')
    noms, carte = {}, None
    for ligne in texte.splitlines():
        if ligne and not ligne[0].isspace():
            carte = ligne.strip().rstrip(':').strip('  \t')
            for prefixe in (r'Carte r.seau sans fil', r'Carte Ethernet', r'Carte',
                            r'Wireless LAN adapter', r'Ethernet adapter',
                            r'Unknown adapter'):
                m = re.match(prefixe + r'\s*', carte, re.IGNORECASE)
                if m:
                    carte = carte[m.end():].strip('  \t') or carte
                    break
        elif carte and 'IPv4' in ligne and ':' in ligne:
            ip = ligne.rsplit(':', 1)[1].strip().rstrip('(Preferred)').strip()
            ip = ip.split('(')[0].strip()
            if ip:
                noms[ip] = carte
    return noms


def ips_locales():
    """Les IPv4 de ce PC, celle qui sert a sortir en premier."""
    ips = []
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))      # aucun paquet emis, juste le routage
        ips.append(s.getsockname()[0])
    except OSError:
        pass
    finally:
        s.close()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except socket.gaierror:
        pass
    noms = noms_interfaces()
    return [(ip, noms.get(ip, '?')) for ip in ips]


def bandeau_reseau(ips, port):
    if not ips:
        return ("%sIP du PC introuvable%s - la relever avec : ipconfig\n"
                "  Port a saisir dans l'application : %s%d%s"
                % (ROUGE, BLANC, JAUNE, port, BLANC))
    ip, carte = ips[0]
    lignes = ["  IP a saisir dans l'application   : %s%s%s  (%s)" % (JAUNE, ip, BLANC, carte),
              "  Port a saisir dans l'application : %s%d%s" % (JAUNE, port, BLANC)]
    if len(ips) > 1:
        autres = ', '.join('%s (%s)' % (i, c) for i, c in ips[1:])
        lignes.append('%s  autres cartes : %s%s' % (GRIS, autres, BLANC))
    return '\n'.join(lignes)
