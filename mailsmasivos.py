#!/usr/bin/env python
#-*- coding: UTF-8 -*-

from debug import debug
from decoradores import Verbose, Async
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itertools import islice
import random
import re
import smtplib
import socket
import sys
import time


VERBOSE = 2

"""
Los archivos direcciones.txt y omitir.txt son listas de direcciones de mail
separados por enter. Ambos deben existir.

Los archivos accounts.txt y noaccounts.txt son listas de pares
servidor;usuario;contraseña. Ambos deben existir.

El fichero mensaje.txt es el mensaje que se enviará.

Si existe el fichero mensaje.html se enviará un body multipart html con texto
plano alternativo.

El titulo del mensaje es el titulo más relevante encontrado en mensaje.html.
"""

#FIXME: Salir cuando no queden cuentas disponibles

def write(text, destination):
    f = open(destination, "a")
    f.write("%s\n" % text)
    f.close()


@Async
@Verbose(VERBOSE)
def enviar(destinos, server=None):
    if server is None:
        while not server:
            account = random.choice(get_accounts())
            smtp, user, password = account.strip().split(";")
            server = get_server(smtp, user, password)

    for destino in destinos:

        msg = get_msg(user, destino)

        try:
            server.sendmail(user, destino, msg.as_string())
            write(destino, "omitir.txt")
            debug("   %40s > %s" % (user, destino))
        except smtplib.SMTPDataError, e:
            debug("Calmandome un poco... %s" % e)
            raise
        except smtplib.SMTPServerDisconnected, e:
            debug("¡¡ %s nos patea !! (error recuperado)" % smtp)
        except socket.sslerror:
            pass

    server.close()


def get_server(url, user, password):
    server = smtplib.SMTP(url, 587)
    server.ehlo()

    if url not in ("smtp.mail.yahoo.com",):
        try:
            server.starttls()
        except smtplib.SMTPException, error:
            debug("SMTPException %s: %s" %(error, url))

    try:
        server.login(user, password)
    except smtplib.SMTPAuthenticationError or socket.sslerror:
        write("%s;%s;%s" % (url, user, password), "noaccounts.txt")
        return
    except smtplib.SMTPException, error:
        debug("SMTPException %s: %s" % (error, url))
        return
    except smtplib.SMTPServerDisconnected, error:
        debug("¿Timeout? %s: %s" % (error, url))
        return
    except socket.sslerror:
        return

    return server


def get_accounts():
    accounts = set(open("accounts.txt").readlines())
    try:
        noaccounts = set(open("noaccounts.txt").readlines())
    except IOError:
        debug("W: No existe el fichero noaccounts.txt")
        noaccounts = set()
    return list(accounts - noaccounts)


def partition(iter, partsize):
    return (islice(iter, npart * partsize, npart * partsize + partsize)
        for npart in xrange(len(iter) / partsize + 1))


def get_dirs():
    dirs = set((s.lower().strip()
        for s in open("direcciones.txt").readlines()))
    omitir = set((s.strip()
        for s in open("omitir.txt").readlines()))

    return sorted(dirs - omitir)


def get_title(text, html=None):
    title = ""
    if html:
        regexs = [
            r'<title>(.*?)</title>',
            r'<h\d>(.*?)</h\d>',
        ]
        while not title and regexs:
            match = re.search(regexs.pop(0), html)
            if match:
                title = match.group(1)
    return title

def softread(filename):
    try:
        text = open(filename).read()
    except IOError:
        text = ""
    return text

def get_msg(from_addrs, to_addrs):
    text = softread("mensaje.txt")
    html = softread("mensaje.html")
    match = re.search(r"<body.*?>.*?</body.*?>", html)
    html = match.group(1) if match else ""
    info = softread("info.txt")
    match = re.search(r"fromstr\s*=\s*(.*?)\s*$", info)
    from_str = match.group(1) if match else ""

    subject = get_title(text, html)
    charset = "iso-8859-15"

    msg = MIMEMultipart('alternative')

    msg['From'] = "%s <%s>" % (from_str, from_addrs)
    msg['To'] = to_addrs
    msg['Subject'] = subject

    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')

    msg.attach(part1)
    msg.attach(part2)

    return msg


if __name__ == "__main__":
    dirs = get_dirs()
    while dirs:

        debug("Enviando a %d destinatarios. Usando %d cuentas.\n" %
            (len(dirs), len(get_accounts())))

        partsize = 10
        threads = 20
        slots = [None] * threads

        for part in partition(dirs, partsize):
            passed = False
            while not passed:
                for pos in xrange(len(slots)):
                    if slots[pos] is None or not slots[pos].is_alive():
                        slots[pos] = enviar(part)
                        passed = True
                        break
                time.sleep(1)

        for slot in slots:
            if slot is not None:
                slot.get_result()

        dirs = get_dirs()

    debug("EOF!!")
