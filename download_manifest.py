#!/usr/bin/env python

# File: rhsmDownloadManifest.py
# Author: Rich Jerrido <rjerrido@outsidaz.org>
# Purpose: Given a username, password &
# 		   Subscription Management Application,
#          Download its manifest
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import json
import getpass
import urllib2
import base64
import sys
import ssl
import datetime
from optparse import OptionParser
# ggatward: Additional imports for sat6_scripts integration
import helpers
import os, shutil

parser = OptionParser()
parser.add_option("-l", "--login", dest="login", help="Login user for RHSM", metavar="LOGIN")
parser.add_option("-p", "--password", dest="password", help="Password for specified user. Will prompt if omitted",
                  metavar="PASSWORD")
parser.add_option("-d", "--debug", dest='debug', help="print more details for debugging", default=False,
                  action='store_true')
parser.add_option("-s", "--subscription-management-app", dest='sma',
                  help="Which Subscription Management Application to download manifests from", metavar="SMA")
parser.add_option("--host", dest='portal_host', help="RHSM host to use (Default subscription.rhn.redhat.com)",
                  default="subscription.rhn.redhat.com")
(options, args) = parser.parse_args()

if not (options.login):
    print "Must specify a login (will prompt for password if omitted).  See usage:"
    parser.print_help()
    print "\nExample usage: ./rhsmDownloadManifest.py -l rh_user_account -s My_Satellite"
    sys.exit(1)
else:
    login = options.login
    password = options.password
    portal_host = options.portal_host

if options.sma:
    sma = options.sma
else:
    sma = helpers.MANIFEST

if not password:
    password = getpass.getpass("%s's password:" % login)

if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# ggatward: Change timestamp format
timestamp = datetime.datetime.now().strftime("%Y%m%d")

# ggatward: Use existing sat-export directory structure
# Remove any existing manifests so we only grab the current one
EXPORTDIR = helpers.EXPORTDIR + '/manifest'
if os.path.exists(EXPORTDIR):
    shutil.rmtree(helpers.EXPORTDIR + '/manifest')
    os.makedirs(EXPORTDIR)
else:
    os.makedirs(EXPORTDIR)

# Grab the Candlepin account number
url = "https://" + portal_host + "/subscription/users/" + login + "/owners/"
try:
    if options.debug:
        print "Attempting to connect: " + url

    # Use HTTP proxy if required
    if helpers.PXYADDR:
        proxy = {"http":"http://%s" % helpers.PXYADDR}
        proxy_support = urllib2.ProxyHandler(proxy)
        opener = urllib2.build_opener(proxy_support, urllib2.HTTPHandler(debuglevel=1))
        urllib2.install_opener(opener)

    request = urllib2.Request(url)
    base64string = base64.encodestring('%s:%s' % (login, password)).strip()
    request.add_header("Authorization", "Basic %s" % base64string)
    result = urllib2.urlopen(request)
except urllib2.HTTPError, e:
    print "Error: cannot connect to the API due to HTTP Error: %s" % e.code
    sys.exit(1)
except urllib2.URLError, e:
    print "Error: cannot connect to the API: %s" % e
    print "Check your URL & try to login using the same user/pass via the WebUI and check the error!"
    sys.exit(1)

accountdata = json.load(result)
for accounts in accountdata:
    acct = accounts["key"]

# Grab a list of Consumers
url = "https://" + portal_host + "/subscription/owners/" + acct + "/consumers/"

try:
    if options.debug:
        print "Attempting to connect: " + url
    request = urllib2.Request(url)
    base64string = base64.encodestring('%s:%s' % (login, password)).strip()
    request.add_header("Authorization", "Basic %s" % base64string)
    result = urllib2.urlopen(request)
except urllib2.HTTPError, e:
    print "Error: cannot connect to the API due to HTTP Error: %s" % e.code
    sys.exit(1)
except urllib2.URLError, e:
    print "Error: cannot connect to the API: %s" % e
    print "Check your URL & try to login using the same user/pass via the WebUI and check the error!"
    sys.exit(1)

consumerdata = json.load(result)

# Now that we have a list of Consumers, loop through them and
# see if one matches our

for consumer in consumerdata:
    consumerType = consumer["type"]["label"]
    uuid = consumer["uuid"]
    consumerName = consumer["name"]
    if consumerType in ['satellite', 'sam']:
        if sma == consumerName:
            url = "https://" + portal_host + "/subscription/consumers/" + uuid + "/export/"
            if options.debug:
                print "\tAttempting to connect: " + url
                print "\tSubscription Management Application %s matches parameters. Exporting..." % sma
            try:
                request = urllib2.Request(url)
                base64string = base64.encodestring('%s:%s' % (login, password)).strip()
                request.add_header("Authorization", "Basic %s" % base64string)
                result = urllib2.urlopen(request)
                # ggatward: Updated export location and name formatting
                manifest_file = EXPORTDIR + "/manifest_%s_%s.zip" % (consumerName, timestamp)
                if options.debug:
                    print "\tWriting Manifest to %s" % manifest_file
                with open(manifest_file, "wb") as manifest:
                    manifest.write(result.read())
                sys.exit(0)
            except urllib2.HTTPError, e:
                print "Error: cannot connect to the API due to HTTP Error: %s" % e.code
                sys.exit(1)
            except urllib2.URLError, e:
                print "Error: cannot connect to the API: %s" % e
                print "Check your URL & try to login using the same user/pass via the WebUI and check the error!"
                sys.exit(1)

print "The Subscription Management Application %s could not be found" % sma
print "Reminder: names are case-sensitive"
sys.exit(0)
