# -*- coding: utf-8 -*-

import requests
import pymorphy2
from time import sleep
from random import randrange

# including file with our credentials.
from settings import *


# TODO
# random posting interval for each chat.

def get_updates(offset):
    """
    Getting updates from TG.
    :param offset: offset for longpolling from TG API.
    :return: Will return None if there are no updates for the bot at the TG servers. Else
    will return json with response.
    """
    url = '{api}/{token}/getUpdates'.format(api=api, token=token)
    params = {'timeout': api_timeout, 'offset': offset}

    try:
        response = requests.get(url, timeout=api_timeout, data=params)
        response = response.json()
    except KeyboardInterrupt:
        exit()
    except:
        return None
    return response


def get_send_params(response, schedule, interval, phrase_tmpl, stop_list, presets_phrases):
    """
    Parsing the response. Managing the schedule.
    :param presets_phrases: Presets of phrases bot should catch and answer.
    :param stop_list: Words bot should ignore. For example 'быть' - looks ugly in end phrase.
    :param phrase_tmpl: phrase templates for sending. Defined in settings.py
    :param response: Response we've got from getUpdates()
    :param schedule: Json with by chat message counter.
    :param interval: frequency of the posting messages.
    :return: Will return json with schedule(updated or not), params for sending message to TG API.
    Or will return json with chat_id == None if we should not post a message.
    """
    # simple parsing of the response. To answer we need message and text in it
    # TG API can return edited_message, or sticker instead of text. Not interesting for us.

    try:
        if u'message' not in response['result'][-1]:
            params = {'chat_id': None, 'schedule': schedule}
            return params
        elif u'text' not in response['result'][-1]['message']:
            params = {'chat_id': None, 'schedule': schedule}
            return params
    except KeyError:
        return {'chat_id': None, 'schedule': schedule}

    # "Cutting" the result.
    last_message = response['result'][-1]['message']
    reply_chat_id = last_message['chat']['id']

    # backup :)
    old_schedule = dict(schedule)

    chat_id = reply_chat_id

    reply_to = last_message['message_id']

    text = last_message['text'].lower()
    text = text.split(' ')

    interrupt = check_for_target_phrase(text, presets_phrases)
    if interrupt is not None:
        params = {'chat_id': chat_id, 'text': interrupt, 'schedule': schedule, 'reply_to_message_id': reply_to}
        return params

    # Should we post a message and void the counter for this chat_id
    # or we just need to increment a counter for this chat. Or add a new counter for the new chat.

    if reply_chat_id in schedule:
        if schedule[reply_chat_id] >= interval:
            schedule[reply_chat_id] = 1
        else:
            schedule[reply_chat_id] += 1
            params = {'chat_id': None, 'schedule': schedule}
            print schedule
            return params
    else:
        schedule[reply_chat_id] = 1
        params = {'chat_id': None, 'schedule': schedule}
        print schedule
        return params

    final = do_magic(text, phrase_tmpl, stop_list)

    # if we did not got prepared text for sending, we should fallback to old schedule
    # new schedule may be a problem with avoiding of a counter without a final var on this stage.
    # we will wait wait_posts again, but without message after first interval.

    if final is None:
        # fallback
        params = {'chat_id': None, 'schedule': old_schedule}
    else:
        params = {'chat_id': chat_id, 'text': final, 'schedule': schedule, 'reply_to_message_id': reply_to}
    print params['schedule']
    return params


def get_new_offset(response):
    """
    Just incrementing offset by 1
    :param response: response from getUpdates()
    :return: new offset. Actually I'm waiting for exception here :)
    """
    try:
        offset = response['result'][-1]['update_id'] + 1
        return offset
    except (KeyError, IndexError):
        print u'Some problems with getting new offset. Is the response full?'
        pass


def check_for_target_phrase(text, presets_phrases):
    """
    Checking message from update for our trigger-phrases. You can define this phrase in
    settings file. It should be set of 'trigger phrase': ['list of', 'answers'].
    Answer will be select by random.
    :param text: text(list of words, yep..) from chat.
    :param presets_phrases: presets from settings.
    :return: None or random phrase from presets.
    """
    # we shoild joing the list into the string and remove all punctuation marks.
    text = u' '.join(text)
    del_chars = u'.,?!:;)(\\«»/#"\''
    del_map = dict((ord(char), None) for char in del_chars)
    text = text.translate(del_map)

    for target_phrase in presets_phrases:
        if target_phrase.lower() in text:
            phrase_index = randrange(0, len(presets_phrases[target_phrase]), 1)
            end_phrase = presets_phrases[target_phrase][phrase_index]
            return end_phrase
    return None


def do_magic(text, phrase_tmpl, stop_list):
    """
    Getting a message from user, parsing it with pymorphy2.
    :param stop_list:
    :param phrase_tmpl: phrase template for sending. defined in settings.py.
    :param text: just message from chat.
    :return: end phrase for sending, with random verb(all forms) from text but in infinitive form.
    """
    morph = pymorphy2.MorphAnalyzer()
    vocabulary = []

    phrase = phrase_tmpl[randrange(0, len(phrase_tmpl), 1)]

    for word in text:
        if len(word) < 3:
            continue
        # ugly string...
        del_chars = u'.,?!:;)«»(\\/#"\''
        del_map = dict((ord(char), None) for char in del_chars)
        word = word.translate(del_map)
        parse = morph.parse(word)[0]

        if parse.tag.POS in {u'VERB', u'INFN', u'PRTF', u'PRTS', u'GRND'}:
            word = parse.normal_form
            if word not in stop_list:
                vocabulary.append(unicode(word))
    try:
        index = randrange(0, len(vocabulary), 1)
        word = vocabulary[index]
    except ValueError:
        return None
    end_phrase = phrase.format(word=word)
    return end_phrase


def send_message(params):
    """
    send a message to TG
    :param params: json with params to send. But without a schedule
    :return: Nothing.

    """
    url = '{api}/{token}/sendMessage'.format(api=api, token=token)
    try:
        requests.post(url, data=params)
    except Exception as exc:
        print 'Cannot send the message. Check it. sendMessage func.{exc}'.format(exc=str(exc))


def initial_run():
    """
    For wright polling we need to get first offset. It matter!
    This cod should run just once.
    :return: offset for polling.
    """
    url = '{api}/{token}/getUpdates'.format(api=api, token=token)
    params = {'timeout': api_timeout, 'offset': None}

    while True:
        try:
            sleep(2)
            response = requests.get(url, timeout=api_timeout, data=params)
            response = response.json()
            if not response['result']:
                continue
            else:
                offset = response['result'][-1]['update_id'] + 1
                return offset
        except Exception as exc:
            print 'Cannot finish initial_run. Check it. {exc}'.format(exc=str(exc))
            continue
        except KeyboardInterrupt:
            exit()


def main():
    # init variables we need for correct working.
    schedule = {}
    offset = initial_run()

    while True:

        response = get_updates(offset)

        # Go to new iteration of `while True` if response is not valid
        if response is None:
            continue

        offset = get_new_offset(response)

        # phrase and wait_posts are variables from the settings.
        params = get_send_params(response, schedule, wait_posts, phrases, bad_words, presets)

        schedule = params.pop('schedule')

        if params['chat_id'] is None:
            continue

        send_message(params)

        # if something goes wrong we should not bombing the API, so sleep one second
        sleep(1)


if __name__ == '__main__':
    try:
        main()

    except KeyboardInterrupt:
        exit()
