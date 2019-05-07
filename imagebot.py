import argparse
import datetime
import json
import logging
import os
import os.path
import random
import sys
import time
import urllib.request

from bs4 import BeautifulSoup
import magic
from mastodon import Mastodon
from pybooru import Danbooru

DELETE_CMD = '$delete'
DANBOORU_URL = 'https://danbooru.donmai.us'
DANBOORU_MAX_ATTEMPTS = 10
ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif']
PIXIV_SOURCE_PATTERN = 'https://www.pixiv.net/member_illust.php?mode=medium&illust_id=%s'

mime = magic.Magic(mime=True)

logging.basicConfig(level=logging.INFO)

class Config:
    def __init__(self, path):
        self.path = os.path.abspath(os.path.expanduser(path))

        with open(self.path) as f:
            self.from_dict(json.load(f))

    def from_dict(self, json):
        self.base_url = json['base_url']
        self.client_id = json['client_id']
        self.client_secret = json['client_secret']
        self.access_token = json['access_token']

        self.post_interval = json['post_interval']

        self.required_tags = json['required_tags']
        self.forbidden_tags = json['forbidden_tags']

        self.message = json['message'] + ' @' + json['maintainer']
        self.maintainer = json['maintainer']

        self.state_file = json['state_file']


def get_api(config):
    return Mastodon(client_id=config.client_id,
        client_secret=config.client_secret,
        api_base_url=config.base_url,
        access_token=config.access_token)


def html_to_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    lines = []
    for p in soup('p'):
        lines.append(p.text)
    return '\n'.join(lines)


def sanitize_forwarded_toot(text):
    # removing potentially unwanted mentions
    return text.replace('@', '/')


def split_into_toots(prefix, text):
    toot_len = 500
    part_len = toot_len - len(prefix) - 3

    # (len(text) + (part_len - 1)) // part_len
    # == ceil(len(text) / part_len)
    for i in range((len(text) + (part_len - 1)) // part_len):
        if part_len * (i + 1) >= len(text):
            # last part
            yield '{}\n{}'.format(prefix,
                text[part_len*i:part_len*(i+1)])
        else:
            yield '{}\n{}\n…'.format(prefix,
                text[part_len*i:part_len*(i+1)])

class ImageBot:
    def __init__(self, config):
        self.config = config
        self.api = get_api(self.config)

        self.danbooru = Danbooru(site_url=DANBOORU_URL)
        self.image_list = []

        self.last_notification = -1
        if os.path.exists(self.config.state_file):
            with open(self.config.state_file) as f:
                try:
                    self.last_notification = int(f.read())
                    logging.debug('Recovering state, last notification id is %d', self.last_notification)
                except ValueError:
                    logging.debug('No previous state found')

    def handle_notifications(self):
        try:
            notifications = self.api.notifications()
        except Exception as e:
            logging.error('Exception while fetching notifications: %s', e)
            return
        ln_changed = False
                                                
        if isinstance(notifications, dict) and ('error' in notifications):
            raise Exception('API error: {}'.format(notifications['error']))

        if self.last_notification == -1:
            # if this is the first time the bot is running, don't autorespond
            # retroactively
            if len(notifications) > 0:
                self.last_notification = int(notifications[0]['id'])
                logging.debug('Ignoring previous notifications up to %d', self.last_notification)
            else:
                self.last_notification = 0
            ln_changed = True
        else:
            # reversed order to process notification in chronological order
            for notification in notifications[::-1]:
                if int(notification['id']) <= self.last_notification:
                    continue
                if notification['type'] != 'mention':
                    continue

                logging.debug('Handling notification %s', notification['id'])
                self.last_notification = int(notification['id'])
                ln_changed = True

                text = html_to_text(notification['status']['content'])
                text = sanitize_forwarded_toot(text)

                sender = notification['status']['account']['acct']
                sent_by_maintainer = (sender == self.config.maintainer)

                if DELETE_CMD in text:
                    if not sent_by_maintainer:
                        continue
                    try:
                        self.api.status_delete(notification['status']['in_reply_to_id'])
                    except Exception as e:
                        logging.error('exception while deleting status %d: %s', notification['status']['in_reply_to_id'], e)

                if sent_by_maintainer:
                    continue

                if self.config.maintainer in {account['acct'] for account in notification['status']['mentions']}:
                    # maintainer is already mentioned, no need to forward this message
                    continue

                response = '@{} {}'.format(
                    self.config.maintainer,
                    self.config.message)

                response_sent = self.api.status_post(response,
                    in_reply_to_id=notification['status']['id'],
                    visibility='direct')

                if notification['status']['visibility'] != 'public':
                    # the bot was sent a DM, we should forward that too
                    recipient_prefix = ' '.join('@'+x for x in [self.config.maintainer])
                    prev_part_id = response_sent['id']
                    for part in split_into_toots(recipient_prefix, text):
                        part_sent = self.api.status_post(part,
                            in_reply_to_id=prev_part_id,
                            visibility='direct')
                        prev_part_id = part_sent['id']

                logging.info('Responded to status %d from %s',
                            notification['status']['id'],
                            notification['status']['account']['acct'])

        if ln_changed:
            with open(self.config.state_file, 'a') as f:
                f.seek(0)
                f.truncate(0)
                f.write(str(self.last_notification))
                f.flush()


    def post_image(self):
        while not self.image_list:
            try:
                unfiltered_images = self.danbooru.post_list(tags=' '.join(self.config.required_tags), limit=100, random=True)
                self.image_list = [image for image in unfiltered_images
                                   if 'file_url' in image
                                   and image['source']
                                   and 'bad_id' not in image['tag_string_meta']
                                   and not any(tag in image['tag_string'] for tag in self.config.forbidden_tags)]
            except Exception as e:
                logging.error('exception while fetching candidate images: %s', e)
                self.image_list = None

        image = self.image_list.pop()
        source = (PIXIV_SOURCE_PATTERN % image['pixiv_id']) if image['pixiv_id'] else image['source']
        try:
            req = urllib.request.Request(image['file_url'],
                                         headers={"Referer": DANBOORU_URL + "/posts/" + str(image['id']),
                                                  "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0"})
            with urllib.request.urlopen(req) as u:
                image_data = u.read()
            image_type = mime.from_buffer(image_data)
            if image_type not in ALLOWED_MIME_TYPES:
                logging.error('unknown mime type %s for file %s', image_type, image['file_url'])
                return
            media = self.api.media_post(image_data, image_type)
            self.api.status_post('{0}/posts/{1}\nsource: {2}'.format(DANBOORU_URL, image['id'], source), media_ids=[media['id']], visibility='unlisted', sensitive=True)
            logging.info('posted image: %d', image['id'])
        except Exception as e:
            logging.error('exception while posting image %d: %s', image['id'], e)


    def run(self):
        countdown = 0
        while True:
            if countdown <= 0:
                self.post_image()
                countdown = self.config.post_interval
            countdown -= 1
            self.handle_notifications()
            time.sleep(60)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--config', help='File to load the config from.',
        default='config.json')

    args = parser.parse_args()

    config = Config(args.config)

    bot = ImageBot(config)
    bot.run()

if __name__ == '__main__':
    main()
