#!/usr/bin/env python
## These two lines are needed to run on EL6
__requires__ = ['SQLAlchemy >= 0.7', 'jinja2 >= 2.4']
import pkg_resources

from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from werkzeug import SharedDataMiddleware
import ConfigParser
import sys
import os
from threading import Thread
from time import sleep
import smtplib
import schedule
from email.mime.text import MIMEText

## Hack!
## Zet environment vars voordat we starten
## Als alternatief voor het zetten van env variabelen.
## Herstart met deze environ het proces
if not 'ORACLE_HOME' in os.environ:
    os.environ['ORACLE_HOME'] = '/usr/lib/oracle/11.2/client64'
    ldpath = ':'+ os.environ['ORACLE_HOME'] + '/lib'
    if 'LD_LIBRARY_PATH' in os.environ:
        ldpath = os.environ['LD_LIBRARY_PATH'] +':'+ ldpath
    os.environ['LD_LIBRARY_PATH'] = ldpath
    os.execve(os.path.realpath(__file__), sys.argv, os.environ)  
    ## Oorspronkelijk proces is nu al dood, maar alsnog, als bonus
    sys.exit()

## Nu pas importeren, omdat deze de bovenstaande ORACLE_HOME hack nodig heeft
from nagvmlib import NagVMCompare
from nagvmlib import Exceptions


def getConfig(filename):
    config = ConfigParser.RawConfigParser()
    try:
        config.read(filename)
    except:
        print("Probleem met inlezen van configuratiefile " + filename);
        raise
    return config

global config
config = getConfig('nagvm.conf');
app = Flask(__name__)


## Alle routing
@app.route('/')
def index():
    compare = NagVMCompare(config);
    exceptions = Exceptions(config.get('generic', 'exceptions'))
    print exceptions
    return render_template('index.html', fixMe=compare.getFixMe(), exceptions=exceptions.getExceptionList(), bad=compare.getBad(), config = config, exceptime = exceptions.getLastChangeTime())

@app.route('/saveExceptions', methods=['POST'])
def saveExceps():
    exceptions = Exceptions(config.get('generic', 'exceptions'))
    newExceptions = request.form['exceptions']
    newExceptions = newExceptions.split('\r\n');
    exceptions.replaceExceptions(newExceptions);
    return redirect("/nagvm")

@app.route('/addException/<exc>')
def addExcep(exc):
    exceptions = Exceptions(config.get('generic', 'exceptions'))
    exceptions.addException(exc)
    return redirect('/nagvm')
####


## Alle mail zaken
def runMail():
    compare = NagVMCompare(config);
    vGood = compare.getFixMe();

    if(True or len(vGood) > 0):
        mailAddress = config.get('generic', 'mailto')
        server = smtplib.SMTP('smtp.eur.nl')
        templatefile = open(config.get('generic', 'mailtemplate'))
        template = templatefile.read()
        replace = ''
        templatefile.close()
        for v in vGood:
            replace = replace + v['VM'] + '\r\n'
        template = template.replace('__list__', replace)
        template = MIMEText(template)
        template['Subject'] = "NAGVM Dagelijkse rapportage"
        template['From'] = mailAddress
        template['To'] = mailAddress

        server.sendmail(mailAddress,mailAddress, template.as_string())
    

def scheduleMail(arg):
    schedule.every().day.at(config.get('generic', 'mailtime')).do(runMail)
    while True:
        schedule.run_pending()
        sleep(5)
####


## Main program
if __name__ == '__main__':
    app.debug = config.get('generic', 'debug')
    if config.has_option('generic', 'mailtime'):
        thread = Thread(target = scheduleMail, args = [config])
        thread.daemon = True
        thread.start()
    app.run(host=config.get('generic', 'host'), port=config.getint('generic', 'port'))
