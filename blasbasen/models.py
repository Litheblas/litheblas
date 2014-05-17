# -*- coding: utf-8 -*-
import uuid
import datetime
from dateutil.relativedelta import relativedelta
import os.path
from django.db import models
from django.contrib.auth.models import (BaseUserManager, 
                                        PermissionsMixin, 
                                        AbstractBaseUser, 
                                        Permission, 
                                        _user_get_all_permissions)
from localflavor.se.forms import SEOrganisationNumberField
from globals import GENDERS, COUNTRIES
from blasbasen.backends import make_permission_set


def generate_avatar_filename(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    
    # Döper filen till ett UUID eftersom vi inte ännu inte sparat objektet i databasen och därmed inte fått någon PK. Tror att det här borde funka tillräckligt bra. /Olle
    return os.path.join('avatars', str(uuid.uuid1()) + extension) # Ger typ avatars/02b9672e-85f3-11e3-9e44-542696dae887.jpg

class Person(models.Model):
    """Lagrar personer (som i människor) och är den datatyp som nästan allt i Blåsbasen kopplas till."""
    first_name = models.CharField(max_length=256, verbose_name='förnamn')
    nickname = models.CharField(max_length=256, blank=True, verbose_name='blåsnamn')
    last_name = models.CharField(max_length=256, verbose_name='efternamn')
    gender = models.CharField(max_length=1, choices=GENDERS, blank=True, verbose_name='kön')
    born = models.DateField(blank=True, null=True, verbose_name='födelsedatum')
    deceased = models.DateField(blank=True, null=True, verbose_name='dödsdatum')
    personal_id_number = models.CharField(max_length=4, blank=True, verbose_name='personnummer', help_text='Sista 4 siffrorna i personnumret') #Last 4 characters in Swedish personal id number
    liu_id = models.CharField(max_length=8, blank=True, verbose_name='LiU-ID')
    
    about = models.TextField(blank=True, verbose_name='om', help_text='Godtycklig text.')
    
    special_diets = models.ManyToManyField('SpecialDiet', blank=True, null=True, verbose_name='speciella kostvanor')
    special_diets_extra = models.CharField(max_length=256, blank=True, verbose_name='kommentarer till speciella kostvanor')
    
    posts = models.ManyToManyField('Post', through='Assignment', verbose_name='poster')
    
    # Kontaktinformation
    address = models.CharField(max_length=256, blank=True, verbose_name='adress')
    postcode = models.CharField(max_length=256, blank=True, verbose_name='postnummer') #Byt namn till post_code
    city = models.CharField(max_length=256, blank=True, verbose_name='stad')
    country = models.CharField(max_length=2, choices=COUNTRIES, default='SE', blank=True, verbose_name='land')
    
    email = models.EmailField(max_length=256, blank=True, verbose_name='e-postadress')
    phone = models.CharField(max_length=256, blank=True, verbose_name=u'telefonnummer', help_text=u'Ange landskod om annat land än Sverige.')
    
    class Meta:
        ordering = ['first_name', 'last_name', 'nickname']
        verbose_name = 'person'
        verbose_name_plural = 'personer'
    
    def get_age(self):
        if not self.born:
            return None
        elif self.deceased:
            return relativedelta(self.deceased, self.born).years
        else:
            return relativedelta(datetime.date.today(), self.born).years
    
    def get_assignments(self):
        #Exkludera objekt som avslutats innan detta dygn (detta ser till att objekt utan slutdatum inte utesluts), 
        #filtrera sedan ut de objekt som påbörjats innan detta dygn
        return self.assignment_set.exclude(end_date__lt=datetime.date.today()).filter(start_date__lte=datetime.date.today())
    
    def get_primary_avatar(self):
        return self.avatar_set.get(primary=True)
    
    def get_secondary_avatars(self):
        return self.avatar_set.exclude(primary=True)
    
    #Används internt av Django
    def get_full_name(self):
        if self.nickname:
            return u'{0} "{1}" {2}'.format(self.first_name, self.nickname, self.last_name) # Leif "Pappa Blås" Holm

        return u'{0} {1}'.format(self.first_name, self.last_name) # Leif Holm
    
    #Används internt av Django
    def get_short_name(self):
        if self.nickname:
            return self.nickname # Pappa Blås

        return u'{0} {1}'.format(self.first_name, self.last_name[0]) # Leif H
    
    def get_start_date(self):
        '''Hämtar alla assignments vars poster innebär medlemsskap och som inte är provmedlemsskap, 
        sorterar stigande på startdatum, tar det första objektet och ger detta objekts startdatum'''
        return self.assignment_set.filter(post__membership=True).filter(trial=False).order_by('start_date')[0].start_date
    
    def get_end_date(self):
        a = self.assignment_set.filter(post__membership=True).filter(trial=False)
        
        #Kolla om någon assignment är pågående, bryt och returnera None i så fall
        for i in a:
            if i.ongoing:
                return None
        
        '''Hämtar alla assignments vars poster innebär medlemsskap och som inte är provmedlemsskap, 
        sorterar fallande på slutdatum, tar det första objektet och ger detta objekts slutdatum'''
        return a.order_by('-end_date')[0].end_date

    def __unicode__(self):
        return self.get_full_name()
    
    age = property(get_age)
    full_name = property(get_full_name)
    short_name = property(get_short_name)
    start_date = property(get_start_date)
    end_date = property(get_end_date)
    primary_avatar = property(get_primary_avatar)
    secondary_avatars = property(get_secondary_avatars)

class Avatar(models.Model):
    picture = models.ImageField(max_length=256, upload_to=generate_avatar_filename, verbose_name='bild')
    person = models.ForeignKey('Person', verbose_name='person')
    primary = models.BooleanField(default=True, verbose_name='standard') #TODO: Skriv nåt skript som tar bort standard på alla andra bilder tillhörande samma person
    
    class Meta:
        ordering = ['primary', 'id']
        verbose_name = 'profilbild'
        verbose_name_plural = 'profilbilder'
    
    def __unicode__(self):
        return u'{0}: {1}'.format(self.person.short_name, self.id)
    
    def get_url(self):
        '''Hämtar (publik) URL till bilden'''
        return self.picture.url
    
    def get_path(self):
        '''Hämtar sökväg (i filsystemet) till bilden'''
        return self.picture._get_path()
    
    url = property(get_url)
    path = property(get_path)

class UserManager(BaseUserManager):
    """Plankat från Djangos dokumentation. Används för Blåsbasens användarmodell."""
    def create_user(self, username, password):
        if not username:
            raise ValueError('Users must have a username')
        
        if not password:
            raise ValueError('Users must have a password')
        
        #TODO: Fixa nåt snyggare
        person = Person(first_name='first', last_name='last')
        person.save()

        user = self.model(
            person=person,
            username=username,
            password=password,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password):
        #Use the normal method for creating users
        user = self.create_user(
            username,
            password,
        )
        
        #Add superuser properties
        user.is_admin = True
        user.is_staff = True
        user.is_superuser = True

        user.save(using=self._db)
        return user

class User(AbstractBaseUser, PermissionsMixin):
    """En avskalad användarmodell vars enda uppgift i stort sett är att lagra användarnamn och lösenord. Resten lagras i datatypen Person."""
    username = models.CharField(max_length=256, unique=True, db_index=True, verbose_name='användarnamn')
    is_active = models.BooleanField(default=True, verbose_name='aktivt konto', help_text="Detta är INTE ett fält för att markera att någon blivit gamling") #Ska inte användas för att markera gamlingsskap osv.! Det görs mycket bättre på automatisk väg via posts
    is_admin = models.BooleanField(default=False, verbose_name='administratörskonto (?)', help_text='#TODO: Osäker på vad detta fält faktiskt används för. Kolla upp.')
    is_staff = models.BooleanField(default=False, verbose_name='maktkonto', help_text='Bestämmer om användaren kan logga in i admingränssnittet')
    
    person = models.OneToOneField(Person, related_name='user', verbose_name='person')
    
    objects = UserManager()
    
    USERNAME_FIELD = 'username'
    
    class Meta:
        ordering = ['person', 'username']
        verbose_name = 'användarkonto'
        verbose_name_plural = 'användarkonton'
    
    def get_assignment_permissions(self, obj=None):
        """Hämtar rättigheter från den kopplade personens poster och sektioner"""
        perms = set()
        #set(["%s.%s" % (p.content_type.app_label, p.codename) for p in user_obj.user_permissions.select_related()])
        for assignment in self.person.get_assignments():
            perms.update(assignment.post.get_all_permissions())
        return perms
    
    # Ersätter Djangos egna get_all_permissions för att få med rättigheter från poster/sektioner 
    def get_all_permissions(self, obj=None):
        perms = set()
        perms.update(_user_get_all_permissions(self, obj)) # Hämtar rättigheter på vanligt vis
        perms.update(self.get_assignment_permissions(obj))
        return perms
    
    def get_full_name(self):
        return self.person.full_name

    def get_short_name(self):
        return self.person.short_name
    
    def get_email(self):
        return self.person.email
        
    def __unicode__(self):
        return self.get_full_name()
    
    # Langar lite egenskaper som många appar förväntar sig finnas i User-modellen.
    full_name = property(get_full_name)
    short_name = property(get_short_name)
    email = property(get_email)

class Section(models.Model):
    """Exempelvis trumpet, styrelsen, kompet, funktionärer, gamlingar/hedersmedlemmar, kommittéer etc.. Denna datatyp (tillsammans med Post) styr medlemsskap i grupper."""
    name = models.CharField(max_length=256, verbose_name='namn')
    description = models.TextField(blank=True, verbose_name='beskrivning')
    
    permissions = models.ManyToManyField(Permission, blank=True, null=True, verbose_name='rättigheter')
    
    class Meta:
        ordering = ['name']
        verbose_name = 'sektion'
        verbose_name_plural = 'sektioner'
    
    def get_people(self, current=True):
        people = []
        for post in self.post_set.all():
            people.extend(post.get_people(current))
        return people
    
    def __unicode__(self):
        return self.name

class Post(models.Model):
    """Exempelvis elbas, dictator, gamling, hedersmedlem, vän till blåset, sektionschef etc.. 
    Bäst att spara gamling som en egen slags medlemstyp utan sektion eftersom systemet 
    själv kan hålla reda på vilka sektioner man tillhört."""
    
    name = models.CharField(max_length=256, verbose_name='namn')
    section = models.ForeignKey('Section', blank=True, null=True, verbose_name='sektion')
    
    permissions = models.ManyToManyField(Permission, blank=True, null=True, verbose_name='rättigheter')
    
    # Metadata
    description = models.TextField(blank=True, verbose_name='beskrivning')
    membership = models.BooleanField(default=False, verbose_name='innebär medlemsskap', help_text='Räknas man som medlem i föreningen enkom av att vara med i denna post, dvs. kan man <em>antas</em> på denna post? Det här vill vi antagligen bara använda för instrument.') #TODO: Byt namn till implies_membership
    engagement = models.BooleanField(default=False, verbose_name='uppdrag', help_text='Är denna post ett uppdrag utöver det vanliga medlemsskapet?')
    show_in_timeline = models.BooleanField(default=True, verbose_name='visa på tidslinje', help_text='Ska ett medlemskap på denna post visas i tidslinjen? (Tidslinjen som inte finns ännu)')
    
    # En egenskap för om posten är arkiverad också kanske? Typ generalbas. /Olle
    # Nej förresten, det riskerar bara en massa redundant och/eller felaktig information. 
    # En post som ingen haft på många år hör ju per definition till historien, så det behöver inte anges explicit.
    # Dessutom skulle det inte uppdateras. /Olle
    
    class Meta:
        unique_together = (('section', 'name',),)
        ordering = ['section', 'name']
        verbose_name = 'post'
        verbose_name_plural = 'poster'
    
    def get_people(self, current=True):
        #TODO: Byt ut till set()
        people=[]
        if current:
            #Att vi väljer att exkludera åtaganden med slutdatum innan idag ser till att åtaganden utan slutdatum också kommer med.
            assignments = self.assignment_set.exclude(end_date__lt=datetime.date.today()).filter(start_date__lte=datetime.date.today())
        elif not current:
            #Välj ut åtaganden med startdatum tidigare än eller lika med idag.
            assignments = self.assignment_set.filter(start_date__lte=datetime.date.today())
        
        # select_related för att minska antalet databasfrågor en aning.
        for assig in assignments.select_related('person'):
            people.append(assig.person)
        return people
    
    def get_section_permissions(self):
        return make_permission_set(self.section.permissions.all())
        #return set(["%s.%s" % (p.content_type.app_label, p.codename) for p in self.section.permissions.all()])
    
    def get_all_permissions(self):
        perms = set()
        perms.update(self.get_section_permissions())
        perms.update(make_permission_set(self.permissions.all()))
        return perms
    
    def __unicode__(self):
        if self.section:
            return u'{0} / {1}'.format(self.section.name, self.name)
        return self.name

class Assignment(models.Model):
    """Mellantabell som innehåller info om varje användares medlemsskap/uppdrag på olika poster."""
    person = models.ForeignKey(Person, verbose_name='person')
    post = models.ForeignKey(Post, verbose_name='post')
    
    start_date = models.DateField(verbose_name='startdatum')
    end_date = models.DateField(blank=True, null=True, verbose_name='slutdatum')
    
    trial = models.BooleanField(default=False, verbose_name='provantagning')
    
    class Meta:
        verbose_name = 'medlemsskap/uppdrag'
        verbose_name_plural = verbose_name
    
    def get_if_implies_membership(self):
        return self.post.membership
    
    def get_if_engagement(self):
        return self.post.engagement
    
    def get_if_on_timeline(self):
        return self.post.show_in_timeline
    
    def get_if_ongoing(self):
        #Fall 1: slutdatum är satt
        if self.end_date:
            #Är slutdatumet satt till idag eller efter?
            return self.end_date >= datetime.date.today()
        #Fall 2: inget slutdatum är satt
        else:
            #Är startdatumet satt till idag eller före?
            return self.start_date <= datetime.date.today()
    
    def __unicode__(self):
        return u'{0}: {1}'.format(self.person.get_short_name(), self.post)
    
    implies_membership = property(get_if_implies_membership)
    engagement = property(get_if_engagement)
    on_timeline = property(get_if_on_timeline)
    ongoing = property(get_if_ongoing)

class SpecialDiet(models.Model):
    name = models.CharField(max_length=256, verbose_name='beskrivning', help_text='Anges i formen "Allergisk mot...", "Nykterist" etc.')
    
    class Meta:
        ordering = ['name']
        verbose_name = 'speciell kostvana'
        verbose_name_plural = 'speciella kostvanor'

    def __unicode__(self):
        return self.name
    
class Customer(models.Model):
    name = models.CharField(max_length=256, verbose_name='namn')
    organisation_number = SEOrganisationNumberField(min_length=0) #TODO: Fixa verbose_name. Kolla om det verkligen går att lämna blankt #Accepterar även personnummer
    comments = models.TextField(blank=True, verbose_name='kommentar')
    
    contact = models.CharField(max_length=256, blank=True, verbose_name='kontaktperson')
    phone_number = models.CharField(max_length=64, blank=True, verbose_name='telefonnummer')
    
    #Address information
    address = models.CharField(max_length=256, blank=True, verbose_name='adress')
    postcode = models.CharField(max_length=256, blank=True, verbose_name='postnummer')
    city = models.CharField(max_length=256, blank=True, verbose_name='stad')
    country = models.CharField(max_length=2, choices=COUNTRIES, default='SE', blank=True, verbose_name='land')
    
    class Meta:
        ordering = ['name', 'contact']
        verbose_name = 'kund'
        verbose_name_plural = 'kunder'
    
    def __unicode__(self):
        return self.name

class Card(models.Model):
    enabled = models.BooleanField(default=True, verbose_name='aktiverat', help_text="Avmarkera om du tillfälligt vill spärra ditt kort")
    card_data = models.CharField(max_length=256, verbose_name='kortdata', help_text="Be någon kolla i loggen efter ditt kortnummer") #TODO: Kolla exakt vad av kortets data som läses av. Vad av detta skall lagras?
    person = models.ForeignKey(Person, verbose_name='person') #Kort _måste_ associeras med en person. Låt det vara så så slipper vi "temporära lösningar" och vilsna kort som ingen vet vem de tillhör.
    description = models.CharField(max_length=256, verbose_name='beskrivning', blank=True, help_text="Anges förslagsvis om du har fler än ett kort")
    
    class Meta:
        verbose_name = 'kort'
        verbose_name_plural = 'kort'
    
    def __unicode__(self):
        return u'{0} ({1})'.format(self.card_data, self.person.get_short_name())
