from nostr.relay_manager import RelayManager
from nostr.message_type import ClientMessageType
from nostr.filter import Filter, Filters
from nostr.event import Event
from nostr.key import PrivateKey, PublicKey
from os.path import exists
from secrets import token_hex
from base64 import b64encode, b64decode

import time
import json
import ssl

import logging
import click

# Initialization logging and setting basic settings.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

@click.group()
@click.pass_context
def cli(ctx: object):
    """This software is designed to transfer files in a decentralized way, without the need for a central server.
    It works through "nostr" relays, that is, you can use multiple relays to guarantee the availability and robustness of the
    file transference.
    """
    if not (exists("keychain.key") == True):
        key = PrivateKey()
        pub = key.public_key
        with open("keychain.key", "w") as w:
            json.dump({"key": key.bech32(), "pub": pub.bech32()}, w)
    else:
        with open("keychain.key", "r") as r:
            data = json.load(r)

        key = PrivateKey.from_nsec(data["key"])
        pub = key.public_key.from_npub(data["pub"])

    with open("data/relays.json", "r") as relaysFile:
        relays = json.load(relaysFile)

    ctx.obj = {"relays": relays, "key": key, "pub": pub.bech32()}
    
@cli.command()
@click.option("--message", help="Message that will be encrypted and sent to the relays.")
@click.option("--file", type=click.File('rb'))
@click.option("--public-key", help="Public key that will be used to encrypt the message.")
@click.pass_context
def push(ctx: object, message: str, file: object, public_key: str) -> dict:
    """Push the file or message to the configured relays."""
    if (file) and not (message):
        message = b64encode(file.read()).decode("utf-8")
    
    relay_manager = RelayManager()
    for relay in ctx.obj["relays"]:
        relay_manager.add_relay(relay)

    logging.info("Opening connection to all relays: " + json.dumps(ctx.obj["relays"]))
    relay_manager.open_connections({"cert_reqs": ssl.CERT_NONE})
    logging.info("Waiting 10s for the client to connect to the websocket.")
    time.sleep(10)
    
    key = ctx.obj["key"]
    
    logging.info("Encrypting the data that will be sent to the relays.")
    message = key.encrypt_message(message=json.dumps(message), public_key_hex=public_key)
    if (file):
        message = json.dumps({"data": message, "type": "file"})
    else:
        message = json.dumps({"data": message, "type": "message"})
    
    event = Event(public_key=key.public_key.hex(), content=message, kind=892)

    logging.info("Signing encrypted message.")
    key.sign_event(event)

    number_of_attempts = 0
    while True:
        number_of_attempts += 1
        logging.info(
            f"This is the #{number_of_attempts} attempt to send messages to the relays.")
        try:
            relay_manager.publish_event(event)
            logging.info(
                f"Encrypted message {event.id} sent to relays with sucess.")
            break
        except KeyboardInterrupt:
            logging.error("CTRL + C goodbye!")
            exit()
        except:
            logging.error(
                "Unable to send the encrypted message to the relays.")
            time.sleep(1)
            continue
    
    relay_manager.close_connections()
    print(json.dumps({"publish_id": event.id, "public_key": ctx.obj["pub"]}, indent=3))

@cli.command()
@click.option("--publish-id", help="Identification referring to the publication of the message in the relays.")
@click.option("--public-key", help="Public key that will be used to encrypt the message.")
@click.pass_context
def pull(ctx: object, publish_id: str, public_key: str):
    """Pull a specific file or message from our relays."""
    
    relay_manager = RelayManager()
    for relay in ctx.obj["relays"]:
        relay_manager.add_relay(relay)

    public_key = PublicKey.from_npub(public_key).hex()
    identity = token_hex(5)
    filters = Filters([Filter(
        authors=[public_key],
        kinds=[892]
    )])
    request = [ClientMessageType.REQUEST, identity]
    request.extend(filters.to_json_array())
    
    relay_manager.add_subscription(identity, filters)

    logging.info("Opening connection to all relays: " + json.dumps(ctx.obj["relays"]))
    relay_manager.open_connections({"cert_reqs": ssl.CERT_NONE})
    logging.info("Waiting 15s for the client to connect to the websocket.")
    time.sleep(15)

    message = json.dumps(request)
    number_of_attempts = 0
    while True:
        number_of_attempts += 1
        logging.info(f"This is the #{number_of_attempts} attempt to send messages to the relays.")
        try:
            relay_manager.publish_message(message)
            logging.info(f"Message {message} sent to relays with sucess.")
            break
        except KeyboardInterrupt:
            logging.error("CTRL + C goodbye!")
            exit()
        except:
            logging.error("Unable to send message to the relays.")
            time.sleep(1)
            pass

    time.sleep(5)
    
    key = ctx.obj["key"]
    logging.info("Fetching messages from relays.")
    while relay_manager.message_pool.has_events():
        event = relay_manager.message_pool.get_event() 
        if (event.event.id != publish_id):
            continue
                          
        content = json.loads(event.event.content)
        content["data"] = key.decrypt_message(content["data"], key.public_key.hex())
        
        filename = token_hex(16) + ".txt"
        if (content.get("type") == "file"):
            content = b64decode(content["data"])
            with open(filename, "wb") as w:
                w.write(content)
            
            logging.info(f"Saved in: {filename}")
        else:
            content = content["data"]
            logging.info("Message: " + content)

        break
    
    relay_manager.close_connections()