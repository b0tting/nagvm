# NAGVM - comparing VCenter and Nagios host names
This small web application was written to compare the contents of one or more VCenter servers and see what hosts were not yet configured for monitoring in Nagios. 

* The application is in Dutch at the moment. Feel free to ask for an English translation *

## Features
- See what hosts are missing in Nagios
- Add exceptions to keep them out of the list
- Send a daily nag-mail to a given mail address with all of the missing hosts

## Requirements
This app is based on a number of python libraries, which in turn require system libraries to be installed:

To connect to the Oracle database used by VCenter you will need to install the instantclient:
- oracle-instantclient11.2-devel-11.2.0.3.0-1.x86_64
- oracle-instantclient11.2-basic-11.2.0.3.0-1.x86_64
- cx_Oracle-5.1.2-11g-py26-1.x86_64.rpm
These need the LD_LIBRARY_PATH and ORACLE_HOME environment variables to be set, but I add those in the nagvmd.py script myself with a hack. 

- mysql-connector-python-1.2.3-1.el6.noarch.rpm

-  python-flask
-  python-flask-sqlalchemy
-  schedule (installed from pip, ie. pip install schedule)

## Installation
I assume nagvm is installed in /usr/local/nagvm and runs on port 5000 (see the .conf file). You can find an Apache config in the /etc folder. 

Either start navmd.py from the command line, or use the init.d script in /init.d.

