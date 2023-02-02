# Emperor

The Emperor is a file transfer software, which combines Nostr technology with AES encryption to guarantee secrecy and resistance to censorship of transferred files.

## Install

Create the virtual environment and install the necessary packages.

```bash
sudo apt-get update -y
sudo apt-get install python3 python3-pip -y
pip3 install poetry
python3 -m poetry install
```

## Push file

With this feature, it is possible to send a specific file to nostr relays.
```bash
poetry run emperor push --file <file.txt> --public-key <public-key>
```

## Pull file
This feature makes it possible to search for a specific file in nostr relays.

```bash
poetry run emperor pull --publish-id <publish-id> --public-key <public-key>
```