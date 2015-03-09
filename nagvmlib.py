#!/usr/bin/env python
import ConfigParser
import cx_Oracle
import mysql.connector
import re
import os
import time
import socket

class NagVMCompare:
    ## Resolve alle hostnames in een gegeven lijst
    def resolveHostNames(self, nagiosResult):
        reg = re.compile('^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$')
        nGood, nBad = [], []
        for result in nagiosResult:
            val = result[1];
            if(not reg.match(val)):
                try:
                    val = socket.gethostbyname(val)
                except socket.gaierror:
                    nBad.append({'Alias' : result[0], 'Reason': 'Lookup for ' + val + ' failed', 'Source':'Nagios'})
            nGood.append({'Alias':result[0], 'IP': val})
        return nGood, nBad
    
    ## Haal de lijst met nagios hosts op uit Nagios
    def getNagiosList(self, config):
        con = mysql.connector.connect(user=config.get('nagios', 'user'), password=config.get('nagios', 'password'), host=config.get('nagios', 'host'), database=config.get('nagios', 'nagiosdb'))
        try:
            cur = con.cursor()
            cur.execute("select display_name, address from nagios_hosts;")
            result = cur.fetchall()
            nGood, nBad = self.resolveHostNames(result);
        finally:
            con.close()
        return nGood, nBad
    
    
    ## Gegeven een database verbinding, lees alles uit de VCenter vm views. Geef de correcte of juist de incorrecte
    ## vms terug afhankelijk van de 'bad' operator
    def getVCenterQuery(self, con, bad):
        vGoodQuery = 'select vms.name as "VM Alias", dns_name as "DNS", ip_address as "IP" from VPXV_VMS vms where vms.POWER_STATE = \'On\' and ip_address is not null'
        vBadQuery = 'select vms.name, vms.vmmware_tool from VPXV_VMS vms where vms.POWER_STATE = \'On\' and ip_address is null'
        cur = con.cursor()
        vList = []
        if(bad):
            cur.execute(vBadQuery);
            for result in cur:
                vList.append({'Alias': result[0].lower(), 'Reason': 'VM is on but has no IP. VMTools status is ' + result[1].lower(), 'Source':'VM'})
        else:
            cur.execute(vGoodQuery)
            for result in cur:
                vList.append({'VM' : result[0].lower(), 'IP': result[2]})
    
        return vList
    
    
    def getMergedVCenter(self, config):
        i = 1;
        vGood, vBad = [], [] 
    
        while(i): 
            if(config.has_section('vcenter' + str(i))):
                ## String opgebouwd als 'user/pass@host:port/sid'
                connectString = config.get('vcenter' + str(i), 'user')
                connectString = connectString + "/" + config.get('vcenter' + str(i), 'password')
                connectString = connectString + "@" + config.get('vcenter' + str(i), 'host')
                connectString = connectString + ":" + config.get('vcenter' + str(i), 'port')
                connectString = connectString + "/" + config.get('vcenter' + str(i), 'oraclesid')
            
                ## Hier moet nog een try/except omheen
                con = cx_Oracle.connect(connectString)
                vGood.extend(self.getVCenterQuery(con, bad=False)); 
                vBad.extend(self.getVCenterQuery(con, bad=True));
                con.close;
    
                i = i + 1
            else:
                i = False;
    
        return vGood, vBad
    
    def dropExceptions(self, vGood, vBad, exceptions):
        ## List comprehensions.. moeilijk!
        vGood = [elem for elem in vGood if elem['VM'] not in exceptions]
        vBad = [elem for elem in vBad if elem['Alias'] not in exceptions]
        return vGood, vBad
    
    def filterNagiosFromVM(self, nGood, vGood):
    
        ## Oei, een n x n, dat moet beter kunnen!
        vNotFound  = []
        for vGoodItem in vGood:
            found = False;
            for nGoodItem in nGood:
                if(vGoodItem['IP'] == nGoodItem['IP']):
                    found = True; 
                    break;
            if(not found):
                vNotFound.append(vGoodItem);
        return vNotFound
        
    def enrichWithDN(self, nFixMe):
        for fix in nFixMe:
            try:
                fix["DNS"] = socket.gethostbyaddr(fix["IP"])[0]
            except:
                ## SLECHT! HTLM IN MODEL!
                fix["DNS"] = ""
        return nFixMe
    
    def __init__(self, config):
        ## Verzamel VCenter systemen
        self.vGood, self.vBad = self.getMergedVCenter(config)
    
        ## Gooi alles uit de lijst dat in de exceptie lijst staat
        exceptionFile = config.get('generic', 'exceptions')
        exceptions = Exceptions(exceptionFile)
        self.vGood, self.vBad = self.dropExceptions(self.vGood, self.vBad, exceptions.getExceptionList())
    
        ## Haal de Nagios host lijst op (en transformeer FQNDs via lookups naar IPs)
        self.nGood, self.nBad = self.getNagiosList(config)
    
        ## Haal alle goede VM machines door de Nagios lijst en geef terug wat er niet bestaat
        self.nFixMe = self.filterNagiosFromVM(self.nGood, self.vGood)

        ## Breid resultaat uit met reverse lookups
        self.nFixMe = self.enrichWithDN(self.nFixMe)
   
    def getFixMe(self):
        return self.nFixMe
    
    def getBad(self):
        bad = self.vBad[:]
        bad.extend(self.nBad)
        return bad


class Exceptions:
    def __init__(self, filename):
        self.exceptions = set()
        self.filename = filename
        try:
            f = open(filename)
            self.lastChangeTime = time.ctime(os.path.getmtime(filename))
            lines = f.readlines()
            for line in lines:
                stripped = line.strip()
                if(len(stripped) > 0 and stripped[0] is not '#'):
                    self.exceptions.add(line.strip().lower());
            f.close
        except:
            print("Probleem met uitlezen exceptie bestand (zie 'exceptions' in de config file)")
            raise

    def getLastChangeTime(self):
        return self.lastChangeTime

    def getExceptionList(self):
        return self.exceptions

    def addException(self, newExc):
        self.exceptions.add(newExc)
        self.replaceExceptions(self.exceptions)

    def replaceExceptions(self, exclist):
        file = """# Automatisch gegenereerd bestand!
#
# Nagvm ignore list
#
# Geef hier enter gescheiden een lijst met alle VMs die genegeerd mogen worden
# als nagvm de aanwezigheid in Nagios controleert. Hoofdletter gebruik wordt
# genegeerd.
#
# Nota bene: dit zijn dus VM aliassen, ie. de namen zoals die in vcenter worden
# getoond.
#
#
"""
        exclist = set(exclist)
        self.exceptions = exclist
        for exc in exclist:
            file = file + exc.lower().strip() + "\n"
        newFile = open(self.filename, 'w')
        newFile.write(file)
        newFile.close();


       
