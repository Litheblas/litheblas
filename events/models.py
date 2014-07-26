# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import Group
from django.db.models.query import QuerySet
from datetime import datetime


answers = (
    ('No', 'Nej'),
    ('Maybe', 'Kanske'), # TODO: Ska vi ha ett sånt här alternativ?
    ('Yes', 'Ja'),
)


class EventType(models.Model):
    name = models.CharField(max_length=256)

    def __unicode__(self):
        return self.name


class Attendance(models.Model):
    #Skapas när användaren bjuds in till eller själv går med i ett evenemang
    event = models.ForeignKey('Event')
    person = models.ForeignKey('blasbase.Person')
    answer = models.CharField(max_length=8, choices=answers, blank=True) # Blank = inget svar


# Funktioner för att filtrera events
class EventQuerySetMixin(object):
    # Kommande event
    def future(self):
        return self.filter(start__gte=datetime.now()).order_by('start')

    # Tidigare event
    def past(self):
        return self.filter(end__lte=datetime.now()).order_by('end')

    # Enbart publika event. För att visa på publika sidan utan inloggning.
    def public(self):
        return self.filter(public=True)


# Magi som används för att kunna anropa flera av sina egna funktioner på varandra
class EventQuerySet(QuerySet, EventQuerySetMixin):
    pass


class EventManager(models.Manager, EventQuerySetMixin):
    def get_queryset(self):
        return EventQuerySet(model=self.model, using=self._db)


class Event(models.Model):
    name = models.CharField(max_length=256)
    description = models.TextField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    location = models.ForeignKey('locations.Location', null=True, blank=True)
    type = models.ForeignKey(EventType)
    public = models.BooleanField(default=True)
    attendees = models.ManyToManyField('blasbase.Person', through=Attendance)

    customer = models.ForeignKey('blasbase.Customer')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    objects = EventManager()

    def __unicode__(self):
        return self.name
    
class TargetedInfo(models.Model):
    event = models.ForeignKey(Event)
    group = models.ForeignKey(Group)
    content = models.TextField()