# liquipedia-scripts
A collection of scripts to interact with [Liquipedia](https://liquipedia.net/).

## Installing
You may install the scripts like so:

    $ pip install .

## Usage

### lp-ept-cups
This script fetches data regarding the weekly SC2 cups from the [ESL
website](https://play.eslgaming.com) and uses it to update Liquipedia. It can
currenlty update the list of notable participants and the results. The
Liquipedia page needs to exist as this script will not create it.

In order to edit Liquipedia, credentials must be passed to the script:

    $ export LIQUIPEDIA_USERNAME=username
    $ export LIQUIPEDIA_PASSWORD=password

The list of participants can be overriden like so:

    $ lp-ept-cups participants EU 126

The results can be updated like so:

    $ lp-ept-cups results EU 126

You can use the -n/--dry-run flag to run the script without actually modifying
the Liquipedia page:

    $ lp-ept-cups -n participants EU 126

You can also edit a different page (mostly for testing purposes):

    $ lp-ept-cups -p 'User:MyUser/ESL_Open_Cup_${region}/${edition}' results EU 126

## Contributing

### Creating a dev environment
You may create a development environment like this:

    $ tox -edev

Tox also allows you to run commands directly like so:

    $ tox -edev -- lp-ept-cups -n results EU 126

Note that in order to use a page template on the command line, you will need to
escape the opening curly bracket:

    $ tox -edev -- lp-ept-cups -n -p 'User:MyUser/ESL_Open_Cup_$\{region}/$\{edition}' results EU 126

### Testing
All relevant tests can be run like so:

    $ tox -epy3,flake8
