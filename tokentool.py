from mastodon import Mastodon

def input_from(prompt, choices):
    choice = None
    while choice not in choices:
        choice = input(prompt)
    return choice

def register_app():
    app_name = input('App name [autoresponder]: ') or 'autoresponder'
    base_url = (input('Instance base URL [https://mastodon.social]: ')
        or 'https://mastodon.social')

    client_id, client_secret = Mastodon.create_app(
        app_name,
        scopes=['read', 'write'],
        api_base_url=base_url)

    print('App registered.')
    print('client_id:', client_id)
    print('client_secret:', client_secret)

    print('While you\'re at it, do you want to also authenticate?')

    if input_from('y/n> ', ['y', 'n']) == 'y':
        authenticate(base_url, client_id, client_secret)

def authenticate(base_url=None, client_id=None, client_secret=None):
    if base_url is None:
        base_url = (input('Instance base URL [https://mastodon.social]: ')
            or 'https://mastodon.social')
    if client_id is None:
        client_id = input('Enter your client id: ')
    if client_secret is None:
        client_secret = input('Enter your client secret: ')

    api_unauth = Mastodon(
        api_base_url=base_url,
        client_id=client_id,
        client_secret=client_secret)

    print('Visit the following link, authenticate, and bring back the code that the page gives you afterwards.')
    print('NB: that code is *not* your access token.')

    print(api_unauth.auth_request_url(scopes=['read', 'write']))

    code = input('> ')

    access_token = api_unauth.log_in(code=code,
        scopes=['read', 'write'])

    print('Got access token:', access_token)
    print('Testing...')

    api_auth = Mastodon(
        api_base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token)

    creds = api_auth.account_verify_credentials()

    print('Success, authenticated as {}.'.format(creds['username']))

def main():
    print('Choose your action:')
    print('[r]: register an app to get client_id and client_secret')
    print('[a]: authenticate to get access_token')
    print('if you\'re setting up a bot for the first time, choose [r].')

    choice = None
    while choice not in ['r', 'a']:
        choice = input('> ')

    if choice == 'r':
        register_app()
    else:
        authenticate()

if __name__ == '__main__':
    main()
