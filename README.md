# mastodon image bot

A mastodon bot to post cute fanart at regular intervals.

The bot is written in Python 3 and uses [Mastodon.py](https://github.com/halcy/Mastodon.py), [pybooru](https://github.com/LuqueDaniel/pybooru) and [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/).  It's based on https://github.com/sipb/mastodon-bot-autoresponder and https://gist.github.com/puphime/8ee151ab0c16945aefbd290be20252ff .

The bot will periodically post random images from Danbooru matching a user-defined set of tags.  It also deletes posts when requested to by the maintainer (just reply to a post with the string "$delete"), and forwards any messages it receives to its maintainer as DMs.

# Configuration

The bot is configured in a JSON file that looks like this:

```
{
    "base_url": "https://botsin.space",
    "client_id": "0dd...65d",
    "client_secret": "a7e...6b7",
    "access_token": "9af...d33",

    "post_interval": 30,

    "required_tags": ["rating:s"],
    "forbidden_tags": ["comic", "animated", "sexual_harassment", "nazi"],

    "message": "I'm just a bot, but I'll forward your message in a DM to my human maintainer:",
    "maintainer": "dukhovni@mastodon.mit.edu",

    "state_file": "/home/mastodon/imagebot/state"
}
```

All keys are mandatory.

* The first group contains information about connecting to the API and authenticating to it.
* The second group contains the interval in minutes to wait between posting new images.
* The third group contains a set of tags to search for, and a set of unwanted tags to filter out of the search results.  The `rating:s` tag restricts the search to images that have been tagged as "safe" by Danbooru's users.  In practice, this doesn't always necessarily mean safe-for-work, but the images generally don't have full nudity or explicit sexual content.  If you remove this tag from the search criteria, you'll probably want to tweak the code to mark the images as NSFW on Mastodon.
* The fourth group contains the message to respond with when users toot at the bot, and the mastodon handle of the bot's maintainer for passing on messages.
* The last group contains the path to the state file, which contains informations that lets the bot remember which messages it's already replied to (this cannot be empty, but the file doesn't have to exist the first time you run the bot).

# Installation

This should really be packaged as a proper Python package, but I haven't done that. If you want to run this bot:

```
# 1. clone this repo
git clone git@github.com:sdukhovni/imagebot.git

# 2. set up a virtual environment for Python and activate it
virtualenv -p python3 env
source env/bin/activate

# 3. install the dependencies
pip install Mastodon.py==1.2.2
pip install beautifulsoup4==4.6.0
pip install pybooru==4.1.0
pip install python-magic==0.4.13

# 4. use tokentool to register the bot as an app on your server,
# then authenticate to it (don't worry, it's not hard, there's a nice
# interactive text interface)
python tokentool.py

# 5. create a config file and edit it appropriately
cp sample_config.json config.json
nano config.json

# 6. run the bot!
python imagebot.py -c config.json
```
