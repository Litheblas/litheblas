#added requirement to BeautifulSoup
from django.test import TestCase
from requests.auth import HTTPBasicAuth
import requests
from BeautifulSoup import BeautifulSoup
from blasbase.models import Person
from blasbassync.management.commands.syncpersons import Command
from django.conf import settings
from sys import stdout
from time import sleep

# Create your tests here.


class PersonMethodsTestCase(TestCase):
    @classmethod
    def setUpClass(self):
        c = Command()
        c.handle()
        print "Collecting pages from litheblas.org"
        total = Person.objects.all().count()
        count = 1
        self.siteList = {}
        for p in Person.objects.all():
            stdout.write("Downloading page %d/%d   \r" % (count, total) )
            stdout.flush()
            count+=1
            r=requests.get('http://www.litheblas.org/internt/blasbas/person.php?id=%s' % p.old_database_id,auth=HTTPBasicAuth(settings.OLD_SITE_USER, settings.OLD_SITE_PASSWORD))
            while r.status_code!=200:
                sleep(1)
                r=requests.get('http://www.litheblas.org/internt/blasbas/person.php?id=%s' % p.old_database_id,auth=HTTPBasicAuth(settings.OLD_SITE_USER, settings.OLD_SITE_PASSWORD))
            self.siteList[p.old_database_id] =r
    def setUp(self):
        pass
    def test_person_memberships(self):
        for p in Person.objects.all():
            soup = BeautifulSoup(self.siteList[p.old_database_id].text)
            try:
                current = soup.find(text="Medlemskap").findNext('td')
            except:
                print soup.text


            memberships = []
            while current.text != "":
                #print current.text
                temp = current.text.split( )
                membership = {}
                membership['datum'] = temp[0]
                membership['typ'] = temp[1]
                if len(temp) == 3:
                    membership['instrument'] = temp[2]
                memberships.append(membership)
                current = current.findNext('td').findNext('td')
            new_memberships = p.assignments.filter(function__membership=True).order_by('start')
            for m in memberships:
                if m['typ'] == 'gamling':
                    self.assertTrue(self.contains(new_memberships, lambda x: str(x.end) == m['datum']),msg=p.old_database_id)




    def contains(self,list, filter):
        for x in list:
            if filter(x):
                return True
        return False



