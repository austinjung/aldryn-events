# -*- coding: utf-8 -*-
import datetime

from django.contrib.sites.models import Site
from django.core.mail import send_mail, mail_managers
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.datastructures import SortedDict
from django.conf import settings

from cms.utils.i18n import get_current_language as get_language


def build_months(year, is_archive_view=False):
    months = SortedDict()
    month_numbers = range(1,12+1)
    if is_archive_view:
        month_numbers = list(reversed(month_numbers))

    for month in month_numbers:
        months[month] = {'year': year, 'month': month, 'date': datetime.date(year, month, 1), 'events':[]}
    return months


def group_events_by_year(events):
    """
    Given a queryset of event objects,
    returns a sorted dictionary mapping years to event objects.
    """
    years = SortedDict()
    for event in events:
        year = event.start_at.year
        if not year in years:
            years[year] = [event]
        else:
            years[year].append(event)
    return years


def build_events_by_year(events, **config):
    display_months_without_events = config.get('display_months_without_events', True)
    # archive view means time runs in reverse. of the current year in a other order
    is_archive_view = config.get('is_archive_view', False)
    now = timezone.now()

    events_by_year = SortedDict()
    for event in events:
        year = event.start_at.year
        if not year in events_by_year:
            events_by_year[year] = {
                'year': year,
                'date': datetime.date(year, 1, 1),
                'months': build_months(year=year, is_archive_view=is_archive_view)
            }
        events_by_year[year]['months'][event.start_at.month]['events'].append(event)
    flattened_events_by_year = events_by_year.values()
    for year in flattened_events_by_year:
        year['months'] = year['months'].values()
        year['event_count'] = 0
        for month in year['months']:
            month['event_count'] = len(month['events'])
            year['event_count'] += month['event_count']
            month['has_events'] = bool(month['event_count'])
            month['display_in_navigation'] = (not display_months_without_events and month['has_events']) or \
                                             display_months_without_events
        # if this is the current year, hide months before this month (or after this month if we're in archive view)
        if year['year'] == now.year:
            if is_archive_view:
                # don't display any months after the current month
                for month in year['months']:
                    if month['month'] > now.month:
                        month['display_in_navigation'] = False
            else:
                # don't display any months before the current month
                for month in year['months']:
                    if month['month'] < now.month:
                        month['display_in_navigation'] = False
    return flattened_events_by_year


def fallback_priority():
    languages = [lang for lang, langtxt in settings.LANGUAGES]
    current_lang = get_language()
    if current_lang in languages:
        languages.remove(current_lang)
    fallback_languages = [get_language()] + languages
    return fallback_languages


def send_user_confirmation_email(registration, language):
    event = registration.event
    context = {
        'event_name': event.title,
        'first_name': registration.first_name,
        'event_url': u"http://%s%s" % (Site.objects.get_current(), event.get_absolute_url()),
    }
    subject = render_to_string(template_name='aldryn_events/emails/registrant_confirmation.subject.txt', dictionary=context)
    body = render_to_string(template_name='aldryn_events/emails/registrant_confirmation.body.txt', dictionary=context)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipient_list=[registration.email])

def send_manager_confirmation_email(registration, language, emails):
    event = registration.event
    context = {
        'event_name': event.title,
        'first_name': registration.first_name,
        'event_url': u"http://%s%s" % (Site.objects.get_current(), event.get_absolute_url()),
        'registration_admin_url': u"http://%s%s" % (
            Site.objects.get_current(),
            reverse('admin:aldryn_events_registration_change', args=[str(registration.pk)])
        ),
    }
    subject = render_to_string(template_name='aldryn_events/emails/manager_confirmation.subject.txt', dictionary=context)
    body = render_to_string(template_name='aldryn_events/emails/manager_confirmation.body.txt', dictionary=context)
    if settings.ALDRYN_EVENTS_MANAGERS:  # don't try to send if the list is empty
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, emails)