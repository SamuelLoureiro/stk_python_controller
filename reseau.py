#!/usr/bin/env python3
"""Utilitaires reseau pour recuperer et afficher l'IP locale pour les capteurs."""

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
    """Active les sequences d'echappement ANSI sur la console Windows."""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        mode = ctypes.c_uint32()
        h = k.GetStdHandle(-11)
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            k.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


def noms_interfaces():
    """Associe les adresses IP aux cartes reseau via ipconfig sous Windows."""
    if os.name != 'nt':
        return {}
    try:
        brut = subprocess.run(['ipconfig'], capture_output=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    # Encodage OEM de la console Windows
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
    """Recupere la liste des adresses IPv4 locales valides."""
    ips = []
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))      # utilise le routage sans emettre de paquet
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
    """Genere le texte d'aide pour configurer le telephone ou l'Arduino."""
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
