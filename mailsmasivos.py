#!/usr/bin/env python
#-*- coding: UTF-8 -*-

from debug import debug
from decoradores import Verbose, Async
from email.Header import Header
from email.MIMEText import MIMEText
import random
import smtplib
import sys
import time
import socket
from itertools import islice

VERBOSE = 2

"""
Los archivos direcciones.txt y omitir.txt son listas de direcciones de mail
separados por enter. Ambos deben existir.

Los archivos accounts.txt y noaccounts.txt son listas de pares
usuario;contraseña. Ambos deben existir.

El fichero mensaje.txt es el mensaje que se enviará. La primera linea de este
archivo será usada como titulo del mensaje.

Se debe modificar la dirección de remitente en la linea 60.
"""


def write(text, destination):
    f = open(destination, "a")
    f.write("%s\n" % text)
    f.close()


@Async
@Verbose(VERBOSE)
def enviar(destinos, titulo, cuerpo, server=None):
    coding = 'utf8'

    if server is None:
        while not server:
            account = random.choice(get_accounts())
            smtp, user, password = account.strip().split(";")
            server = get_server(smtp, user, password)

    for destino in destinos:
        msg = MIMEText(cuerpo.encode(coding), 'plain', coding)
        msg["From"] = user
        msg["Subject"] = Header(titulo, coding)
        msg["To"] = destino
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
    server = smtplib.SMTP()
    server.connect(url)
    server.ehlo()
    server.starttls()

    try:
        server.login(user, password)
    except smtplib.SMTPAuthenticationError or socket.sslerror:
        write("%s;%s;%s" % (url, user, password), "noaccounts.txt")
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


if __name__ == "__main__":

    mensaje = open("mensaje.txt").readlines()
    titulo = unicode(mensaje[0].strip(), "UTF8")
    cuerpo = unicode("".join(mensaje[1:]).strip(), "UTF8")

    dirs = set((s.lower().strip()
        for s in open("direcciones.txt").readlines()))
    omitir = set((s.strip() for s in open("omitir.txt").readlines()))

    dirs = sorted(dirs - omitir)

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
                    slots[pos] = enviar(part, titulo, cuerpo)
                    passed = True
                    break
            time.sleep(1)

    for slot in slots:
        if slot is not None:
            slot.get_result()

    debug("EOF!!")
