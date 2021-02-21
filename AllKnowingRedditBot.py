#!/usr/bin/python3
# ^ This line tells my computer to execute this file as python3
# Imports
import re
import sys
import praw
import time
import tswift
import random
import datetime
import requests
import traceback
import configparser
import mysql.connector
from zalgo_text import zalgo
from nltk.tokenize import word_tokenize

# Config and global variables
# These 2 lines are for getting persistant variables from config.ini (not on GitHub)
config = configparser.ConfigParser()
config.read('config.ini')
# If DEBUG is True, print debug info, only scan one subreddit, and force the script to crash on Exceptions
DEBUG = False
# These are the persistant variables stored in config.ini
good_bot_count = int(config['Bot Persistant Storage']['good_bot'])
bad_bot_count = int(config['Bot Persistant Storage']['bad_bot'])
# These keys provide authentication to prove that it's me when I query these respective web services
API_KEYS = {
    'GIPHY': config['Authentication']['GIPHY'],  # To get gifs
    'YOUTUBE': config['Authentication']['YOUTUBE'],  # To search YouTube
    # To get lyrics of songs
    'MUSIXMATCH': config['Authentication']['musixmatch'],
    'IBM': config['Authentication']['ibm translation'],  # To translate things
}
# Log in to Reddit
reddit = praw.Reddit("akrb")
# This forces the script to conform to reddit's new standards when it comes to editing and submitting posts via the API
# Basically, it just shuts up the warning that happens when I don't use this.
reddit.validate_on_submit = True
# Debug settings...
if DEBUG:
    # If DEBUG, to help create a controlled environment, only moniter one subreddit
    subreddit = 'testingground4bots'
    # Run background_tasks() every 30 seconds so we don't have to wait so long
    time_interval = 30
else:
    # Otherwise, operate as usual and watch r/all
    subreddit = 'all'
    # And run background_tasks() only once every 2 minutes
    time_interval = 120

# Get an instance of an authenticated MySQL session
# So I can store things in a data persistant method accessable anywhere on my computer (MySQL)
mydb = mysql.connector.connect(
    host=config['Authentication']['database host'],
    user=config['Authentication']['database username'],
    password=config['Authentication']['database password'],
    database="reddit"
)
# This allows us to re-use the cursor without being forced to read from it.
# Honestly, I don't 100% understand, but it works ¯\_(ツ)_/¯
db = mydb.cursor(buffered=True)
# Initialize the table if it does not yet exist in this format:
# +-----------------+------------+
# | username (text) | value (int)|
# +-----------------+------------+
# | NormativeNomad  |          2 |
# | jperez81805     |         10 |
# | Matthew_Quigley |         13 |
# | Chuturmaat      |        149 |
# +-----------------+------------+
db.execute('CREATE TABLE IF NOT EXISTS nicecount (username TEXT, value INTEGER)')
# This is sort of a stopwatch to keep track of when the last time we ran background_tasks()
background_tasks_stopwatch = time.time()

# Load blacklisted_subreddits to ignore
with open('blacklisted_subreddits.txt') as file:
    blacklisted_subreddits = file.read()
    blacklisted_subreddits = blacklisted_subreddits.split('\n')
    blacklisted_subreddits = list(filter(None, blacklisted_subreddits))

# Load blacklisted_users to ignore
with open('blacklisted_users.txt') as file:
    blacklisted_users = file.read()
    blacklisted_users = blacklisted_users.split('\n')
    blacklisted_users = list(filter(None, blacklisted_users))

# Load auto_generated_replies (so we won't auto reply to ourself)
with open('auto_generated_replies.txt') as file:
    auto_generated_replies = file.read()
    auto_generated_replies = auto_generated_replies.split('\n')
    auto_generated_replies = list(filter(None, auto_generated_replies))

# Print the starting paramaters to the console
print(f'''Initializing bot with the following paramaters:
DEBUG: {DEBUG}
Subreddit: {subreddit}
good_bot_count: {good_bot_count}
bad_bot_count: {bad_bot_count}
Reddit Login: {reddit.user.me().name}
Scanned 0 comments...''')


# Allows us to modify any blacklist without stopping and restarting the script
# Basically it appends the username/subreddit to the blacklist array[], and adds it to the file for persistant storage
# If list isn't specified, assume 'subreddit'
def add_to_blacklist(value, list='subreddit'):
    if list == 'user':
        # set the filename
        blacklist = 'blacklisted_users.txt'
        # append to blacklisted_users[]
        blacklisted_users.append(value)
    if list == 'subreddit':
        # set the filename
        blacklist = 'blacklisted_subreddits.txt'
        # append to blacklisted_subreddits[]
        blacklisted_subreddits.append(value)
    with open(blacklist, 'a') as file:  # open the specified files
        file.write(f'{value}\n')  # add `value` to the end


# This function runs whenever the background_tasks_stopwatch timestamp
# is greater than 30 or 120 seconds ago, depending on the debugging mode.
def background_tasks():
    # Delete comments with a score of -1 or lower
    delete_negative_comments()
    # Check Reddit Inbox for messages to reply to
    interact_with_replies()
    # Save the niceount, good and bad bot count to persistant storage
    save_variables()


# ERASE PREVIOUS LINE IN TERMINAL
def delete_last_line(n=1):
    for _ in range(n):  # do this `n` times (_ is a throwaway variable, like a throwaway reddit account)
        sys.stdout.write('\x1b[1A')  # CURSOR UP ONE LINE
        sys.stdout.write('\x1b[2K')  # REMOVE CONTENTS OF CURRENT LINE


# Delete my comments that are being downvoted to avoid karma loss
def delete_negative_comments():
    # Get the last comments I made (max 1000 comments) sorted by date commented
    for c in reddit.user.me().comments.new():
        # Check the karma of that specific comment
        if c.score <= -1:
            # delete if -1 or less
            c.delete()


def escape_json(data):
    data = data.replace('\n', '\\n')
    data = data.replace('\"', '\\\"')
    return data

# Take a YouTube timestamp and turn it into DOW MON DOM 24HR YYYY format


def format_timestamp(ts):
    return time.ctime(datetime.datetime.strptime(
        ts, "%Y-%m-%dT%H:%M:%SZ").timestamp())
    # EXAMPLE RETURN VALUE: Thu Feb 11 19:31:40 2021


# Query the adviceslip API and return the advice
def get_advice():
    # Query the API
    response = requests.get('https://api.adviceslip.com/advice')
    # Get the JSON data
    response_json = response.json()
    # EXPAMPLE RESPONSE DATA
    # {
    # "slip": {
    #         "id": 212,
    #         "advice": "The hardest things to say are usually the most important."
    #     }
    # }
    advice = response_json['slip']['advice']  # Get just the advice portion
    return advice


# Take the body of a Reddit comment and seperate the command from the arguments
def get_arguments(command, body):  # command is the !command to strip from the body
    # get the starting point of the !command
    command_index = body.index(command)
    # get the length of the command
    command_length = len(command)
    # The starting value plus the length equals the ending value
    # for example, lets say the !command starts 100 charaters into the comment,
    # and `!command` is 8 charaters long, return text starting 108 charaters into the body
    words_after_command_index = command_index + command_length
    # This syntax, array[value:] means the array, from `value` to the end of the array
    # This syntax, array[value_1:value_2], means the array, starting at `value_1`, going until `value_2`
    # This syntax, array[:value], means the array, starting at the beginning, going unti `value`
    # P.S. all strings can be used as arrays in python
    words_after_command = body[words_after_command_index:]
    # If there are no words after the !command
    if len(words_after_command) == 0:
        return False
    # an else statement is not required, becuase if the above is true, we would have already returned a value.
    # We could have ONLY reached this point in the function IF the above statement didn't execute
    # meaning that the IF statement MUST have been false
    return words_after_command


# Query the icanhazdadjoke API and return the dadjoke
def get_dadjoke():
    # Query the API
    response = requests.get('https://icanhazdadjoke.com',
                            headers={'accept': 'application/json'})
    # Get the JSON data
    response_json = response.json()
    # Get the joke from the data
    joke = response_json['joke']
    # returnt the joke
    return joke


# oh boy... this one is crazy
# I'll add comments to it later...
# No really, I will.
def get_definition(word='null'):
    url = f'https://api.dictionaryapi.dev/api/v2/entries/en/{word}'
    data = requests.get(url).json()
    if 'title' in data:
        return f'''\> Be me

\> Gets asked to look up the definition of the word {word}

\> Whips out Merriam-Webster Dictionary™

\> Can't find the word

\> Panik.jpg'''
    formatted_response = ''
    item = data[0]
    formatted_response += f"\n\n#{item['word'].title()}\n"
    formatted_response += '---\n'
    formatted_response += '##Pronunciation:\n\n'
    for pronunciation in item['phonetics']:
        formatted_response += f"\n[{pronunciation['text']}]({pronunciation['audio']})  <-- click here for audio\n\n"
    for item in data:
        for group in item['meanings']:
            # add the partOfSpeech
            formatted_response += f'\n\n###{group["partOfSpeech"].title()}\n\n'
            for d in group['definitions']:
                formatted_response += f'* {d["definition"]}\n'
                if 'example' in d:
                    formatted_response += f'    * Example: {d["example"]}\n'
                if 'synonyms' in d:
                    formatted_response += '    * Synonyms:\n'
                    for synonym in d['synonyms']:
                        formatted_response += f'        * {synonym}\n'
        if 'origin' in item:
            formatted_response += f'\n\n##Origin:\n{item["origin"]}\n\n'
        formatted_response += '\n\n---\n\n'
    return(formatted_response)


# Get the default footnote that gets appended to most replies
def get_footer():
    # Literally just return this string:
    # and include whatever get_advice() gives us at the end.
    # thats it.
    return f'''

---

^(Hey, I'm looking for people to [collaborate](https://github.com/benjitusk/AllKnowingRedditBot) with on this bot, if you're intersted, send me a DM [not a PM, use the chat please]!)

^(For a quick overview of what I can do, comment "!features" for a list.)

^(Sick of this bot? Have a moderator comment "!blacklist subreddit" to this comment, or just reply "!blacklist" to blacklist just your account.)

^({get_advice()})'''


# Query the GIPHY API and return the gif URL
def get_gif(search_term=''):
    url = f'https://api.giphy.com/v1/gifs/random?api_key={API_KEYS["GIPHY"]}&tag={search_term}&rating=pg-13'
    response = requests.get(url).json()
    return f'![Here\'s your {search_term} gif!](https://giphy.com/gifs/{response["data"]["id"]})'


def get_insult():
    response = requests.get(
        'https://evilinsult.com/generate_insult.php?lang=en&type=json').json()
    insult = response['insult']
    return insult


def get_joke():
    url = 'https://icanhazdadjoke.com/'
    response = requests.get(url, headers={'Accept': 'application/json'}).json()
    if response['status'] == 200:
        joke = response["joke"]
    else:
        joke = 'Huh, there seems to be an error getting a joke for you... please look into this, u/benjixinator.'
    return joke


def get_lyrics(body):
    song_data = body[(body.index('!lyrics') + len('!lyrics')):].strip()
    if len(song_data) == 0:
        return 'You need to format your comment as such:\n\n!lyrics <title> / <artist>'
    song_data = song_data.split('/')
    if len(song_data) == 1:
        lyrics_snippet = song_data[1]
        song = tswift.Song.find_song(lyrics_snippet)
        full_lyrics = song.lyrics
        song_name = song.title
        song_artist = song.artist
        # Double the newline chars, because markdown
        full_lyrics = full_lyrics.replace('\n', '\n\n')
        return f'The top result for lyrics snippet `{lyrics_snippet}` is {song_name} by {song_artist}:\n\n---\n\n{full_lyrics}\n\n---\n\nLyrics by MetroLyrics + {get_footer()}'
        tswift
    if len(song_data) == 2:
        title = song_data[0]
        artist = song_data[1]
        song = tswift.Song(title, artist)
        try:
            # Double the newline chars because markdown
            full_lyrics = song.lyrics.replace('\n', '\n\n')
        except tswift.TswiftError:
            return f'Hmm, no results turned up for `{title}` by `{artist}`... maybe you spelled something wrong, or maybe the lyrics are not in the database.{get_footer()}'
        else:
            return f'Here are the lyrics for {song_name} by {song_artist}:\n\n---\n\n{full_lyrics}\n\n---\n\nLyrics by MetroLyrics + {get_footer()}'
    if len(song_data) > 2:
        return 'You need to format your comment as such:\n\n!lyrics (<title> / <artist>) | (<lyrics snippet>)'


def get_random_fact():
    response = requests.get(
        "https://snapplefacts.herokuapp.com/random").json()[0]
    fact = response['fact']
    fact = re.sub('[(`)]', '', fact)
    fact_id = response['id']
    response = f'Snapple fact #{fact_id}: {fact}'
    if (fact_id >= 495 and fact_id <= 650) or fact == 'Missing':
        response = requests.get(
            "https://uselessfacts.jsph.pl/random.txt?language=en").text
        response = response[2:response.find('\n')]
        fact = re.sub('[(`)]', '', response)
        response = f'Random fact: {fact}'
    return response


# def get_translation(comment):
def get_translation(comment):
    # Step one: get the text to translate
    parent = comment.parent()
    try:
        to_translate = parent.body
    except AttributeError:
        to_translate = parent.title + '\n\n' + parent.selftext
    # For some reason, the api breaks on multi-line comments, so for now, we're just replacing all the newlines with a series of charaters that no one would ever put in the comment.
    # This is a very hacky and crappy solution, but this is what i'm doing for now.
    # its all numbers so it doesnt get messed up in the translation
    to_translate = escape_json(to_translate)
    # Step 2: get language to translate to
    body = get_arguments('!translate', comment.body)
    try:
        language = body.split()[0]  # The first word of body must be a language
    except AttributeError:
        language = 'en'
    # Step 3: Query the translation API
    headers = {'Content-Type': 'application/json', }
    data_pre_encoding = '{"text": ["' + \
        to_translate + '"], "target":"' + language + '"}'
    data = data_pre_encoding.encode('utf-8')
    url = 'https://api.us-east.language-translator.watson.cloud.ibm.com/instances/84903ddb-1980-49f0-9a88-52255104c2af/v3/translate?version=2018-05-01'
    response = requests.post(url, headers=headers,
                             data=data, auth=('apikey', API_KEYS['IBM']))
    response_json = response.json()
    try:
        translation = response_json['translations'][0]['translation']
    # this means that there was no translation in the response, meaning there was an error.
    except KeyError:
        if response_json['code'] == 404:
            return f'Sorry, `{language}` is not a valid 2 letter [ISO 639-1 language code](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes). Try again!'
        if response_json['code'] == 400:
            return f'Sorry, an error occured. Here is the debug information: `{response_json}`\n\nThis is the unencoded data sent to the API: `{data_pre_encoding}`\n\nAnd this is the raw encoded data: `{data}`'

    # Un-escape the newlines

    translation += '''\n
^(By benjixinator. Looking for collaborators, send me a chat message, check out the [Github](https://github.com/benjitusk/AllKnowingRedditBot))
    '''
    return translation


def interact_with_replies():
    global good_bot_count
    global bad_bot_count
    for comment in reddit.inbox.unread():
        if comment.was_comment:
            if comment.body.lower() == '!blacklist subreddit':
                comment.mark_read()
                if comment.author in comment.subreddit.moderator() or comment.author in ['generic_reddit_bot_2', 'benjixinator']:
                    with open('blacklisted_subreddits.txt', 'a') as blacklist:
                        blacklist.write(f'{comment.subreddit.display_name}')
                    reply(
                        comment, 'This subreddit has now been added to the blacklist. If you want to un-blacklist this subreddit, DM u/benjixinator with the name of the subreddit.', f'ADDED r/{comment.subreddit.display_name} TO THE SUBREDDIT BLACKLIST')
                else:
                    reply(
                        comment, f'Sorry {comment.author.name}, you need to be the moderator of r/{comment.subreddit.display_name} to add this subreddit to the blacklist. However, I have added your account to the user blacklist. To undo this action, pm u/benjixinator.', f'ADDED u/{comment.author.name} TO THE USER BLACKLIST')
                    with open('blacklisted_users.txt', 'a') as blacklist:
                        blacklist.write(f'{comment.author.name}\n')
            if comment.body.lower() == '!blacklist':
                comment.mark_read()
                with open('blacklisted_users.txt', 'a') as blacklist:
                    blacklist.write(f'{comment.author.name}\n')
                reply(comment, f'Your username, `{comment.author.name}`, has been added to the user blacklist. To undo this action, pm u/benjixinator.',
                      f'ADDED u/{comment.author.name} TO THE USER BLACKLIST')
            if comment.body.lower() == '!delete':
                comment.mark_read()
                parent = comment.parent()
                if comment.author.name == parent.parent().author.name or comment.author in comment.subreddit.moderator() or comment.author.name == 'benjixinator':
                    try:
                        parent.edit(
                            f'u/{comment.author.name} has requested this comment be **deleted**.')
                        print('Deleted a comment\n')
                    except:
                        comment.author.message(
                            '!delete', f'I tried to delete [this comment](https://www.reddit.com{parent.permalink}), but an error occured. If it is urgent that the comment gets deleted, please DM u/benjixinator. I\'m sorry for the inconvenience.')
                        print(
                            f'Could not delete this comment: https://www.reddit.com{parent.permalink}\n')
                        if DEBUG:
                            raise
                else:
                    reply(
                        comment, f'Sorry, only u/{comment.author.name} or a moderator can `!delete` this comment.',)
            if 'good bot' in comment.body.lower():
                comment.mark_read()
                good_bot_count += 1
                try:
                    comment.upvote()
                    reply(comment,
                          f'Thank you, {comment.author.name}!\n\nThe current rating is {good_bot_count} : {bad_bot_count} with a {round(good_bot_count/(bad_bot_count+good_bot_count)*100)}% approval rate.', 'RATING')
                except Exception as e:
                    print(f'Exception: {e}\n')
                    if DEBUG:
                        raise
            if 'bad bot' in comment.body.lower():
                comment.mark_read()
                bad_bot_count += 1
                try:
                    comment.downvote()
                    reply(comment,
                          f'I\'m sorry you feel that way.\n\nThe current rating is {good_bot_count} : {bad_bot_count} with a {round(good_bot_count/(bad_bot_count+good_bot_count)*100)}% approval rate.', 'RATING')
                except Exception as e:
                    print(f'Exception: {e}\n')
                    if DEBUG:
                        raise


def log(data):
    print(data)
    write_to_log(data)


def main():
    try:
        global good_bot_count
        global bad_bot_count
        global blacklisted_subreddits
        global blacklisted_users
        global background_tasks_stopwatch
        comment_count = 0
        # If we are debugging, we are only watching one subreddit, with a lower traffic. to avoid repeat traffic, skip_existing = true only if debugging
        for comment in reddit.subreddit(subreddit).stream.comments(pause_after=0, skip_existing=DEBUG):
            if time.time() - background_tasks_stopwatch > time_interval:  # Every 2 minutes
                if DEBUG:
                    print('Running background_tasks()\n')
                background_tasks()
                background_tasks_stopwatch = time.time()
            if comment == None or comment.author == None:
                continue
            comment_count += 1
            if comment.author.name in blacklisted_users:
                if DEBUG:
                    print(f'Blacklist: u/{comment.author.name}\n')
                continue
            if comment.subreddit.display_name in blacklisted_subreddits:
                if DEBUG:
                    print(f'Blacklist: r/{comment.subreddit.display_name}\n')
                continue
            if not DEBUG:
                delete_last_line()
            print(f'Scanned {comment_count} comments...')
            process_comments(comment)
            if comment.author.name == 'generic_reddit_bot_2':
                continue
    except KeyboardInterrupt:
        print('\nKeyboardInterrupt: Cleaning up...')
        background_tasks()
        try:
            mydb.commit()
            mydb.close()
        except mysql.connector.InterfaceError:
            # Hmm, seems like the DB timed out.
            pass
        print('Bye!')
        return
    except Exception as e:
        log(e)
        log(traceback.format_exc())
        if DEBUG:
            raise
        else:
            main()


def process_comments(comment):
    global blacklisted_subreddits
    global blacklisted_users
    global auto_generated_replies
    global comment_count
    if comment is None or comment.stickied or comment.distinguished:
        return
    if comment.id in auto_generated_replies:
        return
    if comment.subreddit.display_name in blacklisted_subreddits:
        return
    if comment.author.name in blacklisted_users:
        return
    body = comment.body.lower()

    # ADVICE
    if '!advice' in body:
        reply(comment, get_advice(), 'ADVICE')

    # ZALGO
    if '!cursethis' in body:
        # Step 1: Get the parent object
        parent = comment.parent()

        # Step 2: get content of parent
        try:
            text = parent.body
        except AttributeError:
            try:
                text = parent.selftext
            except AttributeError:
                return

        # Step 3: Zalgo-ify repeatedly
        for _ in range(3):
            text = zalgo.zalgo().zalgofy(text)

        # Step 4: Reply
        reply(comment, f'{text}{get_footer()}', 'ZALGO')

    # DADJOKE
    if '!dadjoke' in body:
        reply(comment, get_dadjoke(), 'DADJOKE')

    # DEFINE
    if '!define' in body:
        arguments = get_arguments('!define', body)
        if arguments == False:
            arguments = 'null'
        word = word_tokenize(arguments)[0]
        definition = get_definition(word)
        reply(comment, definition, 'DEFINITION')

    # FEATURES
    if '!features' in body:
        features = '''
### Current features: (<mandatory arguments> [optional arguments]):

* !gif [search term]

* !lyrics <song name>/<song artist>

* !define <word>

* !youtube <search term> [# <number of results>]

* !joke

* !snapple

* !random

* !cursethis

* !advice

* !insult
---

### Upcoming features:

* Wikipedia Search

* Send a feature request to the developer

* Random quote'''
        reply(comment, features, 'FEATURES')

    # GIF
    if '!gif' in body:
        arguments = get_arguments('!gif', body)
        gif = get_gif(arguments)
        reply(comment, gif, 'GIF')

    # INSULT
    if '!insult' in body:
        reply(comment, get_insult(), 'INSULT')

    # JOKE
    if '!joke' in body:
        reply(comment, get_joke(), 'JOKE')

    # LYRICS
    if '!lyrics' in body:
        lyrics = get_lyrics(body)
        reply(comment, lyrics, 'LYRICS')

    # RANDOM
    if '!random' in body:
        reply(
            comment, f'Your very own random number between 1 and 1,000 is `{random.randint(1, 1000)}`', 'RANDOM')

    # SNAPPLE
    if '!snapple' in body:
        reply(comment, get_random_fact(), 'SNAPPLE')

    # Translate

    if '!translate' in body:
        reply(comment, get_translation(comment), 'TRANSLATE')

    # YOUTUBE
    if '!youtube' in body:
        query = get_arguments('!youtube', body)
        youtube = search_youtube(query)
        reply(comment, youtube, 'YOUTUBE')


def reply(comment, message, type='REPLY'):
    # Make sure not to exclude comments that were automatically generated...
    global auto_generated_replies
    try:
        c = comment.reply(message)
    except Exception as e:
        if e.__class__.__name__ == 'Forbidden':
            print(f'BANNED from r/{comment.subreddit.display_name}\n')
            add_to_blacklist(f'{comment.subreddit.display_name}')
        else:
            print(f'Exception: {e}\n')
        if DEBUG:
            raise
    else:
        print(f'{type}: https://www.reddit.com{c.permalink}\n')
        # Add reply to auto_generated_replies list
        auto_generated_replies.append(c.id)
        with open('auto_generated_replies.txt', 'a') as agr:
            agr.write(f'{c.id}\n')


def save_variables():
    global good_bot_count
    global bad_bot_count
    config['Bot Persistant Storage']['good_bot'] = str(good_bot_count)
    config['Bot Persistant Storage']['bad_bot'] = str(bad_bot_count)
    with open('config.ini', 'w') as configfile:
        config.write(configfile)


def search_youtube(query):
    query = query.split('#')
    max_results = 5
    if len(query) > 1:
        try:
            max_results = int(query[1])
        except ValueError:
            return f'Sorry, I had trouble understanding what you meant when you said that you wanted `{query[1]}` videos.'
        if max_results > 25:
            max_results = 25
    print(
        f'Searching youtube for "{query[0]}" and fetching the first {max_results} result/s')
    url = f'https://youtube.googleapis.com/youtube/v3/search?part=snippet&q={query[0]}&maxResults={max_results}&key={API_KEYS["YOUTUBE"]}\n'
    response = requests.get(url).json()
    total_results = response['pageInfo']['totalResults']
    formatted_response = f'Showing the top {len(response["items"])} of about {total_results} results for `{query[0]}`\n\n---\n\n'
    for result in response['items']:
        if result['id']['kind'] == 'youtube#channel':
            formatted_response += f'* ##[{result["snippet"]["title"]}](https://youtube.com/user/{result["snippet"]["channelTitle"]}) [Channel]\n\n'
        if result['id']['kind'] == 'youtube#video':
            formatted_response += f'* ##[{result["snippet"]["title"]}](https://www.youtube.com/watch?v={result["id"]["videoId"]})\n\n'
        formatted_response += f'    * {result["snippet"]["description"]}\n\n'
        formatted_response += f'    * Uploaded by [{result["snippet"]["channelTitle"]}](https://www.youtube.com/user/{result["snippet"]["channelTitle"]}) at {format_timestamp(result["snippet"]["publishTime"])}\n\n'
    formatted_response += get_footer()
    return formatted_response


def write_to_log(data):
    with open('bot.log', 'a') as log_file:
        log_file.write(f'[{time.ctime()}]:\t{data}\n')


if __name__ == "__main__":
    main()
