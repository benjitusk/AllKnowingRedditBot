# This class is for isolated actions that don't interact with other components
# such as referencing global variables
import re
import sys
import time
import tswift
import datetime
import requests
import pytesseract  # For transcribing text found in images. See transcribe_image()
import configparser
from PIL import UnidentifiedImageError, Image

config = configparser.ConfigParser()
config.read('config.ini')

API_KEYS = {}

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


# ERASE PREVIOUS LINE IN TERMINAL
def delete_last_line(n=1):
    for _ in range(n):  # do this `n` times (_ is a throwaway variable, like a throwaway reddit account)
        sys.stdout.write('\x1b[1A')  # CURSOR UP ONE LINE
        sys.stdout.write('\x1b[2K')  # REMOVE CONTENTS OF CURRENT LINE
    return


def escape_json(data):
    # This is to remove charaters that break the translation API
    # Any newline char should be replaced with an escaped backslash (\\) and an N (n)
    data = data.replace('\n', '\\n')
    data = data.replace('\"', '\\\"')
    return data


# Take a YouTube timestamp and turn it into DOW MON DOM 24HR YYYY format
def format_timestamp(ts):
    # EXAMPLE RETURN VALUE: Thu Feb 11 19:31:40 2021
    return time.ctime(datetime.datetime.strptime(
        ts, "%Y-%m-%dT%H:%M:%SZ").timestamp())


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


# Query the icanhazdadjoke API and return the dadjoke
def get_dadjoke():
    # Query the API
    response = requests.get('https://icanhazdadjoke.com',
                            headers={'accept': 'application/json'})
    # Get the JSON data
    response_json = response.json()
    # Get the joke from the data
    joke = response_json['joke']
    # return the joke
    return joke


# Get definition from dictionaryapi.com
def get_definition(word='null'):  # If no word is given to define, define the word null
    # Set up the url to call
    url = f'https://api.dictionaryapi.dev/api/v2/entries/en/{word}'
    # Make the request and get the JSON data from it
    data = requests.get(url).json()
    if 'title' in data:
        # This means the response contains an error, presumably a `word not found` err
        # exit the function with the following message:
        return f'''\> Be me

\> Gets asked to look up the definition of the word {word}

\> Whips out Merriam-Webster Dictionary™

\> Can't find the word

\> Panik.jpg'''

    # formatted_response is the response that we slowly build up and format as we parse the JSON response
    formatted_response = ''  # Start off empty
    # set response_object to the first (and usually only) object in the response JSON
    response_object = data[0]
    # Make a markdown formatted title that contains the word being defined
    formatted_response += f"\n\n#{response_object['word'].title()}\n"
    # Add a markdown <hr/>
    formatted_response += '---\n'
    # Subtitle for the pronunciation
    formatted_response += '##Pronunciation:\n\n'
    # For each pronunciation, add it with the written pronunciation, make it a link to a recording of the pronunciation
    for pronunciation in response_object['phonetics']:
        formatted_response += f"\n[{pronunciation['text']}]({pronunciation['audio']})  <-- click here for audio\n\n"
    # For each definition set of the word
    for response_object in data:
        # For each word group in a definition set
        for group in response_object['meanings']:
            # add the partOfSpeech as a <h3>
            formatted_response += f'\n\n###{group["partOfSpeech"].title()}\n\n'
            # For each actual definition of the word
            for d in group['definitions']:
                # Append it as a bullet point
                formatted_response += f'* {d["definition"]}\n'
                if 'example' in d:
                    # For each example of the definition, append it as a sub-bullet point to the definition
                    formatted_response += f'    * Example: {d["example"]}\n'
                if 'synonyms' in d:
                    # After that, make a bullet point that says Synonyms for a list of synonyms
                    formatted_response += '    * Synonyms:\n'
                    for synonym in d['synonyms']:
                        # For each synonym add it as a sub-bullet point to Synonyms
                        formatted_response += f'        * {synonym}\n'
        if 'origin' in response_object:
            # If we have information on the origin of the definition
            # add it under a subtitle 'Origin' with the origin information underneath
            formatted_response += f'\n\n##Origin:\n{response_object["origin"]}\n\n'
        # add a linebreak after each definition set
        formatted_response += '\n\n---\n\n'
    # send the fully reddit-formatted response back to be replied in a comment
    return(formatted_response)


# Get the default footnote that gets appended to most replies
def get_footer():
    # Literally just return this string:
    # and include whatever get_advice() gives us at the end.
    # thats it.
    return '''

---

^(Hey, I'm looking for people to [collaborate](https://github.com/benjitusk/AllKnowingRedditBot) with on this bot, if you're intersted, send a chat message to [benjixinator](https://www.reddit.com/user/benjixinator) [not a PM, use the chat please]!)

^(For a quick overview of what I can do, comment "!features" for a list.)
'''


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
        lyrics_snippet = song_data[0]
        song = tswift.Song.find_song(lyrics_snippet)
        full_lyrics = song.lyrics
        song_name = song.title
        song_artist = song.artist
        # Double the newline chars, because markdown
        full_lyrics = full_lyrics.replace('\n\n', '\n\---\n')
        full_lyrics = full_lyrics.replace('\n', '\n\n')
        return f'The top result for lyrics snippet `{lyrics_snippet}` is {song_name} by {song_artist}:\n\n---\n\n{full_lyrics}\n\n---\n\nLyrics by MetroLyrics {get_footer()}'
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
            return f'Here are the lyrics for {song_name} by {song_artist}:\n\n---\n\n{full_lyrics}\n\n---\n\nLyrics by MetroLyrics {get_footer()}'
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


def image_from_url(url):
    try:
        image = Image.open(requests.get(url, stream=True).raw)
    except UnidentifiedImageError:
        image = None
    return image


def search_youtube(query):
    query = str(query)  # JUST in case...
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


def transcribe_image(comment):
    # We need to get the image to transcribe.
    # Right now, we're assuming the image is in the parent post.
    parent = comment.submission
    image_url = parent.url
    image = image_from_url(image_url)
    # Make sure the url actually points to an image
    if image == None:
        return 'Whoops, I could not find an image containing text at this URL. If this seems like an error, please send a message to benjixinator. Thanks!'
    text = 'The following text was found in this image:\n\n' + \
        pytesseract.image_to_string(image)
    return text
